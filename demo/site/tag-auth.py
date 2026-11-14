#!/usr/bin/env python3
"""TAG on NEAR - X OAuth profile service.
Stdlib only. Binds verified X identity (OAuth 2.0 PKCE) to a NEAR wallet.
Config via env: X_CLIENT_ID, X_CLIENT_SECRET, BASE_URL (default https://tag.trenchesnetwork.xyz)
"""
import base64, hashlib, hmac, json, os, secrets, sqlite3, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen

CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "https://tag.trenchesnetwork.xyz").rstrip("/")
PORT = int(os.environ.get("PORT", "8793"))
DB = os.environ.get("DB", "/var/lib/tag-auth/profiles.db")
X_AUTHORIZE = "https://twitter.com/i/oauth2/authorize"
X_TOKEN = "https://api.x.com/2/oauth2/token"
X_ME = "https://api.x.com/2/users/me"

os.makedirs(os.path.dirname(DB), exist_ok=True)
db = sqlite3.connect(DB, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS flows (state TEXT PRIMARY KEY, verifier TEXT, expires REAL)")
db.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, x_id TEXT, x_handle TEXT, wallet TEXT, expires REAL)")
db.execute("CREATE TABLE IF NOT EXISTS profiles (x_id TEXT PRIMARY KEY, x_handle TEXT, wallet TEXT, updated REAL)")
db.commit()

def http_json(url, payload=None, headers=None, method=None):
    data = None
    if payload is not None:
        data = urlencode(payload).encode()
    req = Request(url, data=data, method=method or ("POST" if data else "GET"))
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def now():
    return time.time()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain", cookies=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200, cookies=None):
        self._send(code, json.dumps(obj).encode(), "application/json", cookies)

    def redirect(self, url, cookies=None):
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Cache-Control", "no-store")
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()

    def session_from_cookie(self):
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("tag_session="):
                token = part.split("=", 1)[1]
                row = db.execute("SELECT x_id, x_handle, wallet, expires FROM sessions WHERE token=?", (token,)).fetchone()
                if row and row[3] > now():
                    return {"token": token, "x_id": row[0], "x_handle": row[1], "wallet": row[2] if isinstance(row[2], str) else None, "expires": row[3]}
        return None

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path == "/healthz":
            return self._json({"ok": True, "configured": bool(CLIENT_ID and CLIENT_SECRET)})
        if path == "/auth/me":
            s = self.session_from_cookie()
            if not s:
                return self._json({"authenticated": False})
            return self._json({"authenticated": True, "x_handle": s["x_handle"], "wallet": s["wallet"]})
        if path == "/auth/x/login":
            if not (CLIENT_ID and CLIENT_SECRET):
                return self.redirect(BASE_URL + "/?auth_error=not_configured")
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            state = secrets.token_urlsafe(16)
            db.execute("INSERT OR REPLACE INTO flows VALUES (?,?,?)", (state, verifier, now() + 600))
            db.commit()
            q = urlencode({
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": BASE_URL + "/auth/x/callback",
                "scope": "users.read tweet.read",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            })
            return self.redirect(X_AUTHORIZE + "?" + q)
        if path == "/auth/x/callback":
            qs = parse_qs(u.query)
            code = (qs.get("code") or [""])[0]
            state = (qs.get("state") or [""])[0]
            denied = (qs.get("denied") or [""])[0]
            if denied or not code:
                return self.redirect(BASE_URL + "/?auth_error=denied")
            row = db.execute("SELECT verifier, expires FROM flows WHERE state=?", (state,)).fetchone()
            db.execute("DELETE FROM flows WHERE state=?", (state,))
            db.commit()
            if not row or row[1] < now():
                return self.redirect(BASE_URL + "/?auth_error=state")
            basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
            try:
                tok = http_json(X_TOKEN, {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": BASE_URL + "/auth/x/callback",
                    "code_verifier": row[0],
                }, {"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"})
                access = tok["access_token"]
                me = http_json(X_ME, headers={"Authorization": "Bearer " + access})
                x_id = me["data"]["id"]
                x_handle = me["data"]["username"]
            except Exception as e:
                return self.redirect(BASE_URL + "/?auth_error=exchange")
            token = secrets.token_urlsafe(32)
            existing = db.execute("SELECT wallet FROM sessions WHERE x_id=?", (x_id,)).fetchone()
            wallet = existing[0] if existing else None
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?)", (token, x_id, x_handle, wallet, now() + 30 * 86400))
            prof = db.execute("SELECT wallet FROM profiles WHERE x_id=?", (x_id,)).fetchone()
            if prof and prof[0]:
                db.execute("UPDATE sessions SET wallet=? WHERE token=?", (prof[0], token))
                db.commit()
            cookie = f"tag_session={token}; Path=/; Max-Age={30*86400}; HttpOnly; Secure; SameSite=Lax"
            return self.redirect(BASE_URL + "/#earn", cookies=[cookie])
        return self._send(404, "not found")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/auth/link":
            s = self.session_from_cookie()
            if not s:
                return self._json({"ok": False, "error": "no session"}, 401)
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length).decode() or "{}")
            except Exception:
                return self._json({"ok": False, "error": "bad json"}, 400)
            wallet = (body.get("wallet") or "").strip().lower()
            if not (wallet.endswith(".testnet") or wallet.endswith(".near")):
                return self._json({"ok": False, "error": "invalid wallet"}, 400)
            db.execute("UPDATE sessions SET wallet=? WHERE token=?", (wallet, s["token"]))
            db.execute("INSERT OR REPLACE INTO profiles VALUES (?,?,?,?)",
                       (s["x_id"], s["x_handle"], wallet, now()))
            db.commit()
            return self._json({"ok": True, "x_handle": s["x_handle"], "wallet": wallet})
        return self._send(404, "not found")

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
