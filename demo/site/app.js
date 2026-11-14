// TAG on NEAR demo dapp — live contract views + wallet connect + on-chain claim.
// Wallet selector loads lazily: the read-only views must work even if the CDN is down.
const CONTRACT_ID = "tagmech-izecube.testnet";
const RPC = "https://rpc.testnet.fastnear.com";
const DEMO_DAY = 20771;

const PARAM_LABELS = {
  token_id: "reward token (NEP-141)",
  daily_pot_bps: "daily pot, basis points of treasury",
  skim_bps: "claim skim, basis points returned to pool",
  validator_cut_bps: "validator cut of the daily pot",
  validator_threshold: "validator token threshold",
  validator_confirmations: "net confirmations a tag needs",
  hold_pts_per_token_day: "holding points per token per day",
  cap_originals: "daily cap, original posts",
  cap_quotes: "daily cap, quotes",
  cap_replies: "daily cap, replies",
  multiplier_reply_to_token_bps: "reply-to-token multiplier, bps",
  attestor_pk: "attestor public key (Ed25519)",
  treasury_seed: "treasury seed at launch",
};

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

function banner(msg, cls) {
  const el = document.getElementById("live-banner");
  el.textContent = msg;
  el.className = "live-banner " + (cls || "");
}

function shortAccount(a) {
  return a.length > 18 ? a.slice(0, 10) + "…" + a.slice(-6) : a;
}

/* ---------- wallet ---------- */
let selector, modal, activeAccount = null, walletReady = false;

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
      activeAccount = acc ? acc.accountId : null;
      renderWallet();
      refreshMyRewards();
    });
  } catch (e) {
    const btn = document.getElementById("connect-btn");
    btn.textContent = "wallet unavailable (rpc)";
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

async function refreshMyRewards() {
  const big = document.getElementById("my-entitlement");
  const sub = document.getElementById("my-entitlement-sub");
  const claimBtn = document.getElementById("claim-btn");
  if (!activeAccount) {
    big.textContent = "—";
    sub.textContent = "connect wallet to check";
    claimBtn.disabled = true;
    return;
  }
  sub.textContent = activeAccount;
  try {
    const e = await view("get_entitlement", { account_id: activeAccount });
    const amount = Number(e);
    big.textContent = amount > 0 ? fmtToken(e) + " wNEAR" : "0";
    sub.textContent = amount > 0
      ? `${activeAccount} — ready to claim`
      : `${activeAccount} — nothing claimable this epoch`;
    claimBtn.disabled = amount <= 0;
  } catch (err) {
    sub.textContent = "could not read entitlement";
  }
}

async function claim() {
  const result = document.getElementById("claim-result");
  const claimBtn = document.getElementById("claim-btn");
  if (!activeAccount || !walletReady) return;
  claimBtn.disabled = true;
  result.className = "claim-result";
  result.textContent = "sign the claim in your wallet…";
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
    result.innerHTML = `claimed. <a href="https://testnet.nearblocks.io/txns/${txhash}" target="_blank" rel="noopener">view tx</a>`;
    refreshStats();
    refreshMyRewards();
  } catch (e) {
    const msg = (e && e.message) || String(e);
    result.className = "claim-result err";
    result.textContent = msg.toLowerCase().includes("user rejected") || msg.toLowerCase().includes("rejected")
      ? "claim rejected in wallet"
      : "claim failed: " + msg.slice(0, 140);
    claimBtn.disabled = false;
  }
}

/* ---------- live data ---------- */
async function refreshStats() {
  const [treasury, pots] = await Promise.all([view("treasury"), view("pots")]);
  document.getElementById("stat-treasury").textContent = fmtToken(treasury) + " wNEAR";
  document.getElementById("stat-skim").textContent = fmtToken(pots[0]) + " wNEAR";
  document.getElementById("stat-nearpot").textContent = fmtToken(pots[1]) + " NEAR";
}

async function loadEpoch() {
  const epoch = await view("get_epoch", { day: DEMO_DAY });
  if (!epoch) return false;
  document.getElementById("epoch-day").textContent = "day " + epoch.day;
  document.getElementById("epoch-pot").textContent = fmtToken(epoch.pot) + " wNEAR";
  document.getElementById("epoch-paid").textContent = fmtToken(epoch.total_entitlement) + " wNEAR";
  document.getElementById("epoch-points").textContent = fmtWhole(epoch.total_points);
  return true;
}

function tickCountdown() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
  const s = Math.max(0, Math.floor((next - now) / 1000));
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  document.getElementById("countdown").textContent = `next epoch in ${h}:${m}:${sec}`;
}

async function loadParams() {
  const params = await view("get_params");
  const tbody = document.querySelector("#params-table tbody");
  for (const [key, label] of Object.entries(PARAM_LABELS)) {
    let v = params[key];
    if (key === "attestor_pk") v = v.map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16) + "…";
    if (key === "validator_threshold" || key === "treasury_seed") v = fmtWhole(v);
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${label}</td><td>${v}</td><td>frozen at launch</td>`;
    tbody.appendChild(tr);
  }
}

function loadBoard() {
  const demo = window.TAG_DEMO;
  if (!demo) return;
  const tbody = document.querySelector("#board-table tbody");
  const rows = demo.accounts
    .map(a => ({ ...a, entitled: demo.entitlements[a.account] || "0" }))
    .sort((a, b) => Number(b.entitled) - Number(a.entitled));
  rows.forEach((a, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${i + 1}</td><td>${a.account}</td><td>${a.x || "—"}</td>` +
      `<td>${a.tags}</td><td>${fmtWhole(a.tag_points)}</td><td>${fmtWhole(a.hold_points)}</td>` +
      `<td>${fmtToken(a.entitled)}</td>`;
    tbody.appendChild(tr);
  });
}

/* ---------- boot ---------- */
async function main() {
  document.getElementById("contract-link").href =
    "https://testnet.nearblocks.io/address/" + CONTRACT_ID;
  document.getElementById("claim-btn").addEventListener("click", claim);

  const settled = await loadEpoch().catch(() => false);
  banner(settled
    ? "live: contract reached, epoch day " + DEMO_DAY + " settled on NEAR testnet"
    : "live: contract reached on NEAR testnet", settled ? "ok" : "err");

  await Promise.all([refreshStats(), loadParams()]);
  loadBoard();
  tickCountdown();
  setInterval(tickCountdown, 1000);
  await initWallet();
}

main().catch(e => banner("could not reach the contract: " + (e.message || e), "err"));
