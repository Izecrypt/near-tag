// TAG on NEAR demo dapp — live contract views + wallet connect + on-chain claim.
// Wallet selector loads lazily: read-only views must work even if the CDN is down.
const CONTRACT_ID = "tagmech-izecube.testnet";
const RPC = "https://rpc.testnet.fastnear.com";

async function view(method, args) {
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 1, method: "query",
      params: { request_type: "call_function", finality: "final",
                account_id: CONTRACT_ID, method_name: method,
                args_base64: btoa(JSON.stringify(args || {})) },
    }),
  });
  const data = await res.json();
  if (data.error) throw new Error(JSON.stringify(data.error));
  const raw = data.result.result;
  const bytes = typeof raw === "string"
    ? Uint8Array.from(atob(raw), c => c.charCodeAt(0))
    : Uint8Array.from(raw);
  return JSON.parse(new TextDecoder().decode(bytes));
}

const fmtWhole = (v) => Number(v).toLocaleString("en-US");
const fmtToken = (y) => (Number(y) / 1e24).toLocaleString("en-US", { maximumFractionDigits: 4 });
function shortAccount(a) { return a.length > 16 ? a.slice(0, 8) + "…" + a.slice(-5) : a; }

/* ---------- wallet + X session ---------- */
let selector, modal, activeAccount = null, walletReady = false, xSession = null;

async function fetchXSession() {
  try {
    const r = await fetch("/auth/me", { credentials: "same-origin" });
    xSession = await r.json();
  } catch (e) {
    xSession = { authenticated: false };
  }
}

async function linkWalletToX() {
  if (!xSession || !xSession.authenticated || !activeAccount) return;
  try {
    await fetch("/auth/link", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wallet: activeAccount }),
    });
    await fetchXSession();
  } catch (e) {}
}

async function initWallet() {
  try {
    const [core, modalUi, mnw, meteor] = await Promise.all([
      import("near-wallet-selector-core"),
      import("near-wallet-selector-modal"),
      import("near-wallet-selector-mnw"),
      import("near-wallet-selector-meteor"),
    ]);
    selector = await core.setupWalletSelector({
      network: "testnet",
      modules: [mnw.setupMyNearWallet(), meteor.setupMeteorWallet()],
    });
    modal = modalUi.setupModal(selector, { contractId: CONTRACT_ID });
    walletReady = true;
    selector.store.observable.subscribe((state) => {
      const acc = (state.accounts || []).find(a => a.active);
      const had = activeAccount;
      activeAccount = acc ? acc.accountId : null;
      if (activeAccount && activeAccount !== had) linkWalletToX();
      renderWallet();
      refreshMyRewards();
    });
  } catch (e) {
    const btn = document.getElementById("connect-btn");
    btn.textContent = "rpc";
    btn.disabled = true;
    return;
  }
  document.getElementById("connect-btn").addEventListener("click", () => modal.show());
  document.getElementById("disconnect-btn").addEventListener("click", async () => {
    const wallet = await selector.wallet();
    await wallet.signOut();
  });
  renderWallet();
}

function renderWallet() {
  const btn = document.getElementById("connect-btn");
  const chip = document.getElementById("wallet-chip");
  if (activeAccount) {
    btn.classList.add("hidden");
    chip.classList.remove("hidden");
    document.getElementById("wallet-account").textContent = shortAccount(activeAccount);
  } else {
    btn.classList.remove("hidden");
    chip.classList.add("hidden");
  }
}

function renderXState() {
  const state = document.getElementById("x-state");
  const xBtn = document.getElementById("connect-x-btn");
  const authed = xSession && xSession.authenticated;
  if (authed) {
    state.textContent = "@" + xSession.x_handle;
    state.classList.add("verified");
    xBtn.textContent = "switch";
    xBtn.classList.remove("btn-primary");
    xBtn.classList.add("btn-ghost");
  } else {
    state.textContent = "not connected";
    xBtn.textContent = "connect X";
    xBtn.classList.add("btn-primary");
    xBtn.classList.remove("btn-ghost");
  }
}

async function refreshMyRewards() {
  const big = document.getElementById("my-entitlement");
  const sub = document.getElementById("my-entitlement-sub");
  const claimBtn = document.getElementById("claim-btn");
  const xAuthed = xSession && xSession.authenticated;
  if (!xAuthed) {
    big.textContent = "—";
    sub.textContent = "sign in with X to start";
    claimBtn.textContent = "connect X first";
    claimBtn.disabled = true;
    renderXState();
    return;
  }
  if (!activeAccount) {
    big.textContent = "—";
    sub.textContent = "@" + xSession.x_handle + " — now connect your wallet";
    claimBtn.textContent = "connect wallet";
    claimBtn.disabled = !walletReady;
    renderXState();
    return;
  }
  sub.textContent = "@" + xSession.x_handle + " · " + activeAccount;
  renderXState();
  try {
    const e = await view("get_entitlement", { account_id: activeAccount });
    const amount = Number(e);
    big.textContent = amount > 0 ? fmtToken(e) + " wNEAR" : "0";
    claimBtn.textContent = "claim";
    claimBtn.disabled = amount <= 0;
  } catch (err) {
    sub.textContent = "could not read entitlement";
    claimBtn.textContent = "claim";
    claimBtn.disabled = true;
  }
}

function initProfile() {
  const handleInput = document.getElementById("x-handle");
  const saveBtn = document.getElementById("save-profile");
  const save = () => {
    if (!activeAccount) return;
    let h = handleInput.value.trim();
    if (h && !h.startsWith("@")) h = "@" + h;
    handleInput.value = h;
    saveProfile(activeAccount, h);
    saveBtn.textContent = "saved";
    setTimeout(() => { saveBtn.textContent = "save"; }, 1500);
    refreshMyRewards();
  };
  saveBtn.addEventListener("click", save);
  handleInput.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); });
}

async function claim() {
  const result = document.getElementById("claim-result");
  const claimBtn = document.getElementById("claim-btn");
  if (!walletReady) return;
  if (!xSession || !xSession.authenticated) { window.location.href = "/auth/x/login"; return; }
  if (!activeAccount) { modal.show(); return; }
  claimBtn.disabled = true;
  result.className = "claim-result";
  result.textContent = "sign in your wallet…";
  try {
    const wallet = await selector.wallet();
    const outcome = await wallet.signAndSendTransaction({
      receiverId: CONTRACT_ID,
      actions: [{
        type: "FunctionCall",
        params: { methodName: "claim", args: {}, gas: "100000000000000", deposit: "0" },
      }],
    });
    const txhash = outcome.transaction.hash || outcome.transactionHash || "";
    result.className = "claim-result ok";
    result.innerHTML = `claimed. <a href="https://testnet.nearblocks.io/txns/${txhash}" target="_blank" rel="noopener">tx</a>`;
    refreshTicker();
    refreshMyRewards();
  } catch (e) {
    const msg = (e && e.message) || String(e);
    result.className = "claim-result err";
    result.textContent = msg.toLowerCase().includes("reject")
      ? "rejected in wallet"
      : "failed: " + msg.slice(0, 120);
    claimBtn.disabled = false;
  }
}

/* ---------- live data ---------- */
async function refreshTicker() {
  const [treasury, pots, epoch] = await Promise.all([
    view("treasury"), view("pots"), view("get_epoch", { day: latestDay }),
  ]);
  document.getElementById("stat-treasury").textContent = fmtToken(treasury);
  document.getElementById("stat-skim").textContent = fmtToken(pots[0]);
  if (epoch) {
    document.getElementById("stat-pot").textContent = fmtToken(epoch.pot);
    document.getElementById("stat-points").textContent = fmtWhole(epoch.total_points);
  }
}

let latestDay = null;

async function loadEpoch() {
  const day = Math.floor(Date.now() / 86400000);
  let epoch = await view("get_epoch", { day });
  if (!epoch) {
    for (let back = 1; back <= 3 && !epoch; back++) {
      epoch = await view("get_epoch", { day: day - back });
    }
  }
  if (!epoch) return false;
  latestDay = epoch.day;
  document.getElementById("chip-day").textContent = "epoch " + epoch.day;
  document.getElementById("board-day").textContent = epoch.day;
  return true;
}

function tickCountdown() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
  const s = Math.max(0, Math.floor((next - now) / 1000));
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  document.getElementById("chip-countdown").textContent = `${h}:${m}:${sec}`;
}

function loadBoard() {
  const demo = window.TAG_DEMO;
  if (!demo) return;
  const tbody = document.querySelector("#board-table tbody");
  const rows = demo.accounts
    .map(a => ({ ...a, tag_points: Number(a.tag_points), hold_points: Number(a.hold_points), entitled: demo.entitlements[a.account] || "0" }))
    .sort((a, b) => Number(b.entitled) - Number(a.entitled));
  rows.forEach((a, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i + 1}</td><td>${a.account}</td><td>${a.tags}</td>` +
      `<td>${fmtWhole(a.tag_points + a.hold_points)}</td><td>${fmtToken(a.entitled)}</td>`;
    tbody.appendChild(tr);
  });
}

/* ---------- boot ---------- */
async function main() {
  document.getElementById("contract-link").href =
    "https://testnet.nearblocks.io/address/" + CONTRACT_ID;
  document.getElementById("claim-btn").addEventListener("click", claim);

  const settled = await loadEpoch().catch(() => false);
  if (settled) await refreshTicker().catch(() => {});
  loadBoard();
  tickCountdown();
  setInterval(tickCountdown, 1000);

  const params = new URLSearchParams(location.search);
  const authError = params.get("auth_error");
  if (authError) {
    const sub = document.getElementById("my-entitlement-sub");
    sub.textContent = authError === "denied" ? "X sign-in cancelled" : "X sign-in failed (" + authError + ")";
    history.replaceState(null, "", "/");
  }

  await fetchXSession();
  await initWallet();
  refreshMyRewards();
}

main().catch(e => {
  const chip = document.getElementById("chip-day");
  if (chip) chip.textContent = "rpc unreachable";
});
