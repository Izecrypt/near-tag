/* TAG on NEAR demo site — reads live state from the testnet contract. */
const CONTRACT_ID = "tagmech-izecube.testnet";
const RPC = "https://rpc.testnet.fastnear.com";
const DEMO_DAY = 20771; // demo epoch day settled on testnet

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
const fmtNear = (y) => (Number(y) / 1e24).toLocaleString("en-US", { maximumFractionDigits: 4 }) + " wNEAR";

function banner(msg, cls) {
  const el = document.getElementById("live-banner");
  el.textContent = msg;
  el.className = "live-banner " + (cls || "");
}

async function main() {
  document.getElementById("contract-chip").textContent = "contract: " + CONTRACT_ID;
  document.getElementById("contract-chip").href =
    "https://testnet.nearblocks.io/address/" + CONTRACT_ID;

  const [params, treasury, pots] = await Promise.all([
    view("get_params"), view("treasury"), view("pots"),
  ]);
  document.getElementById("stat-treasury").textContent = fmtNear(treasury);
  document.getElementById("stat-skim").textContent = fmtNear(pots[0]);
  document.getElementById("stat-nearpot").textContent = fmtNear(pots[1]);

  const tbody = document.querySelector("#params-table tbody");
  for (const [key, label] of Object.entries(PARAM_LABELS)) {
    let v = params[key];
    if (key === "attestor_pk") v = v.map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16) + "…";
    if (key === "validator_threshold" || key === "treasury_seed") v = fmtWhole(v);
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${label}</td><td>${v}</td><td>frozen at launch</td>`;
    tbody.appendChild(tr);
  }

  const day = DEMO_DAY ?? Math.floor(Date.now() / 86400000);
  const epoch = await view("get_epoch", { day });
  if (epoch) {
    document.getElementById("stat-epoch").textContent = "day " + epoch.day;
    document.getElementById("stat-epoch-sub").textContent =
      "pot " + fmtNear(epoch.pot) + " · paid " + fmtNear(epoch.total_entitlement) +
      " · points " + fmtWhole(epoch.total_points);
    banner("live: contract reached, epoch day " + epoch.day + " settled on NEAR testnet", "ok");
  } else {
    document.getElementById("stat-epoch").textContent = "day " + day;
    document.getElementById("stat-epoch-sub").textContent = "not settled yet";
    banner("live: contract reached on NEAR testnet; no epoch for day " + day + " yet", "ok");
  }
}

main().catch(e => banner("could not reach the contract: " + (e.message || e), "err"));
