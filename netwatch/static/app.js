"use strict";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const IPV4 = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;

function fmtBytes(n) {
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}
const fmtRate = (n) => fmtBytes(n * 8).replace("B", "b") + "ps";
const fmtTime = (t) => new Date(t * 1000).toLocaleTimeString("en-GB");
const fmtDate = (t) => new Date(t * 1000).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 401 && !path.endsWith("/login")) { showLogin(); throw new Error("unauthorized"); }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.error || r.statusText), { status: r.status });
  return body;
}

/* ---------------- typing effect for prompts ---------------- */
function typePrompt(el, text, cls = "") {
  clearInterval(el._t);
  el.className = "prompt " + cls;
  let i = 0;
  el._t = setInterval(() => {
    el.innerHTML = "&gt; " + esc(text.slice(0, ++i)) + ' <span class="cursor">_</span>';
    if (i >= text.length) clearInterval(el._t);
  }, 18);
}

/* ---------------- login ---------------- */
const loginForm = $("#login-form"), u = $("#u"), p = $("#p"), p2 = $("#p2"), loginBtn = $("#login-btn");
let setupMode = false;
const toggleBtn = () => (loginBtn.disabled = !(u.value.trim() && p.value && (!setupMode || p2.value)));
[u, p, p2].forEach((el) => el.addEventListener("input", toggleBtn));

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (setupMode && p.value !== p2.value) return typePrompt($("#login-prompt"), "Passphrases do not match", "err");
  if (setupMode && p.value.length < 6) return typePrompt($("#login-prompt"), "Passphrase must be at least 6 characters", "err");
  loginBtn.disabled = true;
  typePrompt($("#login-prompt"), setupMode ? "Registering operator…" : "Verifying credentials…");
  try {
    await api(setupMode ? "/api/setup" : "/api/login", { method: "POST", body: JSON.stringify({ username: u.value.trim(), password: p.value }) });
    if (setupMode) showLogin(false);
    typePrompt($("#login-prompt"), "ACCESS GRANTED. Establishing secure link…");
    p.value = ""; p2.value = "";
    setTimeout(showApp, 500);
  } catch (err) {
    typePrompt($("#login-prompt"), err.message, "err");
    loginForm.classList.remove("shake"); void loginForm.offsetWidth; loginForm.classList.add("shake");
    p.value = ""; p.focus(); toggleBtn();
  }
});

function showLogin(setup = false) {
  stopPolling();
  closeSettings();
  setupMode = setup;
  $("#setup-extra").classList.toggle("hidden", !setup);
  $("#login-btn-text").textContent = setup ? "INITIALIZE OPERATOR" : "AUTHENTICATE";
  u.placeholder = setup ? "Choose operator username" : "Enter operator username";
  p.placeholder = setup ? "Choose passphrase (min 6 chars)" : "Enter passphrase";
  if (setup) { u.value ||= "admin"; typePrompt($("#login-prompt"), "No operator registered. Create credentials to initialize this terminal"); }
  toggleBtn();
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  (setup && u.value ? p : u).focus();
}

/* ---------------- app state ---------------- */
const state = { target: null, devices: [], detail: null, lastEvent: 0, tab: "sites", timers: [] };

function showApp() {
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  state.lastEvent = 0; $("#feed").innerHTML = "";
  const fromHash = decodeURIComponent(location.hash.slice(1));
  if (IPV4.test(fromHash)) lockTarget(fromHash);
  startPolling();
}

function startPolling() {
  stopPolling();
  const tick = () => { refreshStatus(); refreshDevices(); refreshDetail(); refreshFeed(); };
  tick();
  state.timers.push(setInterval(tick, 2000));
  state.timers.push(setInterval(() => ($("#clock").textContent = new Date().toLocaleTimeString("en-GB")), 1000));
}
function stopPolling() { state.timers.forEach(clearInterval); state.timers = []; }

$("#logout").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }).catch(() => {}); showLogin(); });

/* ---------------- status ---------------- */
async function refreshStatus() {
  const s = await api("/api/status").catch(() => null); if (!s) return;
  const b = $("#mode-badge");
  b.textContent = s.mode; b.classList.toggle("live", s.mode.startsWith("LIVE"));
  $("#engine-alert").classList.toggle("hidden", !s.error);
  $("#pw-alert").classList.toggle("hidden", !s.default_password);
  if (s.error) $("#engine-alert-text").textContent = s.error;
  const up = Math.floor(s.uptime), h = Math.floor(up / 3600), m = Math.floor((up % 3600) / 60);
  $("#sysline").textContent = `v${s.version} · SUBNET ${s.subnets.join(", ")} · IFACE ${s.iface} · ${s.devices} ASSETS · ${s.packets.toLocaleString()} PKTS · UPTIME ${h}h${String(m).padStart(2, "0")}m`;
}

/* ---------------- device list ---------------- */
async function refreshDevices() {
  state.devices = await api("/api/devices").catch(() => state.devices);
  renderDevices();
}
function renderDevices() {
  const f = $("#asset-filter").value.trim().toLowerCase();
  const list = state.devices.filter((d) => !f || d.ip.includes(f) || (d.hostname || "").toLowerCase().includes(f));
  $("#asset-count").textContent = state.devices.length;
  $("#asset-list").innerHTML = list.map((d) => `
    <li data-ip="${esc(d.ip)}" class="${d.ip === state.target ? "sel" : ""}">
      <span class="dot ${d.online ? "on" : ""}"></span>
      <span class="ip">${esc(d.ip)}</span>
      <span class="rate">↓${fmtRate(d.rate_down)}</span>
      <span></span><span class="host">${esc(d.hostname || d.mac || "unknown host")}</span>
    </li>`).join("") || '<li class="muted" style="display:block">No devices observed yet…</li>';
}
$("#asset-filter").addEventListener("input", renderDevices);
$("#asset-list").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-ip]"); if (li) { $("#target").value = li.dataset.ip; lockTarget(li.dataset.ip); }
});

/* ---------------- target ---------------- */
$("#target-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const ip = $("#target").value.trim();
  if (!IPV4.test(ip)) return typePrompt($("#cmd-prompt"), `INVALID TARGET "${ip}" — expected IPv4 address`, "err");
  lockTarget(ip);
});

function lockTarget(ip) {
  state.target = ip; state.detail = null; state.lastEvent = 0;
  $("#target").value = ip; history.replaceState(null, "", "#" + ip);
  $("#feed").innerHTML = ""; $("#feed-scope").textContent = ip;
  typePrompt($("#cmd-prompt"), `Locking on ${ip}… acquiring traffic signature`);
  renderDevices(); refreshDetail(true); refreshFeed();
}

async function refreshDetail(first = false) {
  if (!state.target) return;
  try {
    const d = await api("/api/device?ip=" + encodeURIComponent(state.target));
    if (first || !state.detail) typePrompt($("#cmd-prompt"), `TARGET LOCKED: ${d.ip}${d.hostname ? " (" + d.hostname + ")" : ""} — live monitoring active`);
    state.detail = d; renderDetail();
  } catch (err) {
    if (err.status === 404) {
      if (first) typePrompt($("#cmd-prompt"), `${state.target}: no traffic observed yet — standing by, will lock when it appears`, "err");
      $("#empty").classList.remove("hidden"); $("#dossier").classList.add("hidden");
      $("#empty .big").textContent = "TARGET NOT YET OBSERVED";
    }
  }
}

function renderDetail() {
  const d = state.detail;
  $("#empty").classList.add("hidden"); $("#dossier").classList.remove("hidden");
  $("#d-ip").textContent = d.ip;
  $("#d-host").textContent = d.hostname || "hostname unresolved";
  $("#d-mac").textContent = d.mac || "—";
  $("#d-first").textContent = fmtDate(d.first_seen);
  $("#d-last").textContent = fmtDate(d.last_seen);
  $("#d-status").innerHTML = d.online ? '<span class="st-on">● ONLINE</span>' : '<span class="st-off">○ IDLE</span>';
  $("#t-down").textContent = fmtBytes(d.bytes_down);
  $("#t-up").textContent = fmtBytes(d.bytes_up);
  $("#t-rate").textContent = `${fmtRate(d.rate_down)} / ${fmtRate(d.rate_up)}`;
  $("#t-sites").textContent = d.sites.length;
  drawChart(d.series);
  renderTables();
}

function renderTables() {
  const d = state.detail; if (!d) return;
  const q = $("#site-filter").value.trim().toLowerCase();
  const sites = d.sites.filter((s) => !q || s.domain.includes(q));
  $("#sites-body").innerHTML = sites.map((s) => `
    <tr><td class="dom" title="${esc(s.domain)}">${esc(s.domain)}${s.paths.length ? `<span class="path">${s.paths.map(esc).join("<br>")}</span>` : ""}</td>
    <td><span class="src src-${esc(s.source)}">${esc(s.source.toUpperCase())}</span></td>
    <td class="r">${s.hits}</td><td class="r">${s.bytes ? fmtBytes(s.bytes) : "—"}</td>
    <td>${fmtTime(s.first)}</td><td>${fmtTime(s.last)}</td></tr>`).join("") ||
    '<tr><td colspan="6" class="muted">No sites intercepted yet.</td></tr>';

  const conns = d.connections.filter((c) => !q || c.remote_ip.includes(q) || (c.domain || "").includes(q) || c.service.toLowerCase().includes(q));
  $("#conns-body").innerHTML = conns.map((c) => `
    <tr><td>${esc(c.remote_ip)}:${c.remote_port}</td><td class="dom">${esc(c.domain || "—")}</td><td>${esc(c.service)}</td>
    <td class="r">${fmtBytes(c.bytes_down)}</td><td class="r">${fmtBytes(c.bytes_up)}</td><td>${fmtTime(c.last)}</td></tr>`).join("") ||
    '<tr><td colspan="6" class="muted">No connections.</td></tr>';

  const max = Math.max(1, ...d.protocols.map((p) => p[1]));
  $("#protos-body").innerHTML = d.protocols.map(([name, b]) => `
    <div class="bar-row"><span>${esc(name)}</span><div class="bar"><i style="width:${(b / max) * 100}%"></i></div><span class="r">${fmtBytes(b)}</span></div>`).join("") ||
    '<p class="muted">No data.</p>';
}
$("#site-filter").addEventListener("input", renderTables);

document.querySelectorAll(".tabs button[data-tab]").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button[data-tab]").forEach((x) => x.classList.toggle("active", x === b));
  ["sites", "conns", "protos"].forEach((t) => $("#tab-" + t).classList.toggle("hidden", t !== b.dataset.tab));
}));

$("#export").addEventListener("click", () => {
  const d = state.detail; if (!d) return;
  const rows = [["domain", "source", "hits", "bytes", "first_seen", "last_seen", "http_paths"],
    ...d.sites.map((s) => [s.domain, s.source, s.hits, s.bytes, new Date(s.first * 1000).toISOString(), new Date(s.last * 1000).toISOString(), s.paths.join(" ")])];
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })), download: `netwatch_${d.ip}_${Date.now()}.csv` });
  a.click(); URL.revokeObjectURL(a.href);
});

/* ---------------- chart ---------------- */
function drawChart(series) {
  const c = $("#chart"), dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth, h = c.clientHeight;
  if (!w) return;
  c.width = w * dpr; c.height = h * dpr;
  const g = c.getContext("2d"); g.scale(dpr, dpr);
  const css = getComputedStyle(document.documentElement);
  const padL = 70, padB = 18, pw = w - padL - 16, ph = h - padB - 8;
  const max = Math.max(1024, ...series.map((s) => Math.max(s[1], s[2])));
  g.font = "10px " + css.getPropertyValue("--mono"); g.fillStyle = css.getPropertyValue("--dim");
  g.strokeStyle = "rgba(31,122,92,.25)"; g.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = 8 + ph - (ph * i) / 4;
    g.beginPath(); g.moveTo(padL, y); g.lineTo(padL + pw, y); g.stroke();
    g.fillText(fmtRate((max * i) / 4), 4, y + 3);
  }
  g.fillText("-120s", padL, h - 4); g.fillText("now", padL + pw - 20, h - 4);
  const line = (idx, color, fill) => {
    g.beginPath();
    series.forEach((s, i) => { const x = padL + (pw * i) / (series.length - 1); const y = 8 + ph - (ph * s[idx]) / max; i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.strokeStyle = color; g.lineWidth = 1.6; g.stroke();
    if (fill) { g.lineTo(padL + pw, 8 + ph); g.lineTo(padL, 8 + ph); g.closePath(); g.fillStyle = fill; g.fill(); }
  };
  line(2, css.getPropertyValue("--accent"), "rgba(52,211,153,.12)");
  line(1, css.getPropertyValue("--up"), null);
}
window.addEventListener("resize", () => state.detail && drawChart(state.detail.series));

/* ---------------- feed ---------------- */
async function refreshFeed() {
  const qs = `since=${state.lastEvent}` + (state.target ? `&ip=${encodeURIComponent(state.target)}` : "");
  const evs = await api("/api/events?" + qs).catch(() => []);
  if (!evs.length) return;
  state.lastEvent = evs[evs.length - 1].id;
  const feed = $("#feed");
  const html = evs.reverse().map((e) => `<li class="fresh k-${esc(e.kind)}"><span class="ts">${fmtTime(e.ts)}</span> <span class="who">${esc(e.ip)}</span> ${esc(e.msg)}</li>`).join("");
  feed.insertAdjacentHTML("afterbegin", html);
  while (feed.children.length > 300) feed.lastElementChild.remove();
}

/* ---------------- settings ---------------- */
const settings = { mode: "live", subnets: [], ifaces: [] };

function closeSettings() { $("#settings").classList.add("hidden"); }
async function openSettings() {
  $("#settings").classList.remove("hidden");
  ["#capture-prompt", "#cred-prompt", "#purge-prompt"].forEach((id) => ($(id).textContent = ""));
  const c = await api("/api/config").catch(() => null);
  if (!c) return;
  settings.mode = c.active.mode || c.mode;
  settings.subnets = [...(c.subnets.length ? c.subnets : c.active.subnets || [])];
  settings.iface = c.active.iface ?? c.iface;
  $("#c-user").value = c.user; $("#c-cur").value = $("#c-new").value = $("#c-new2").value = "";
  renderMode(); renderChips();
  if (c.error) typePrompt($("#capture-prompt"), c.error, "err");
  loadIfaces();
}
$("#open-settings").addEventListener("click", openSettings);
$("#alert-settings").addEventListener("click", openSettings);
$("#pw-alert-btn").addEventListener("click", async () => {
  await openSettings();
  $("#cred-form").scrollIntoView({ behavior: "smooth" }); $("#c-cur").focus();
});
$("#close-settings").addEventListener("click", closeSettings);
$("#settings").addEventListener("click", (e) => { if (e.target.id === "settings") closeSettings(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSettings(); });

function renderMode() {
  document.querySelectorAll("#mode-seg button").forEach((b) => b.classList.toggle("active", b.dataset.mode === settings.mode));
  $("#live-fields").classList.toggle("hidden", settings.mode !== "live");
}
$("#mode-seg").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-mode]"); if (!b) return;
  settings.mode = b.dataset.mode; renderMode();
});

async function loadIfaces() {
  const sel = $("#iface-select");
  sel.innerHTML = "<option>scanning…</option>";
  const r = await api("/api/interfaces").catch(() => ({ interfaces: [], error: "Interface scan failed" }));
  settings.ifaces = r.interfaces;
  const def = r.default;
  sel.innerHTML = `<option value="">AUTO (system default${def ? ": " + esc(def) : ""})</option>` +
    r.interfaces.map((i) => `<option value="${esc(i.name)}">${esc(i.name)}${i.ip ? " — " + esc(i.ip) : " — no IP"}${i.description && i.description !== i.name ? " · " + esc(i.description) : ""}</option>`).join("");
  if (settings.iface && !r.interfaces.some((i) => i.name === settings.iface))
    sel.insertAdjacentHTML("beforeend", `<option value="${esc(settings.iface)}">${esc(settings.iface)} (not found)</option>`);
  sel.value = settings.iface || "";
  $("#iface-hint").textContent = r.error || "Pick the adapter connected to the office network (the one with an office IP).";
}
$("#refresh-ifaces").addEventListener("click", loadIfaces);
$("#iface-select").addEventListener("change", (e) => { settings.iface = e.target.value; });

function renderChips() {
  $("#subnet-chips").innerHTML = settings.subnets.map((s, i) =>
    `<span class="chip">${esc(s)}<button type="button" data-i="${i}" title="Remove">✕</button></span>`).join("") ||
    '<span class="none">none — will auto-detect</span>';
}
$("#subnet-chips").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-i]"); if (!b) return;
  settings.subnets.splice(+b.dataset.i, 1); renderChips();
});
const CIDR = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}\/(3[0-2]|[12]?\d)$/;
function addSubnet() {
  let v = $("#subnet-input").value.trim();
  if (IPV4.test(v)) v += "/24";
  if (!CIDR.test(v)) return typePrompt($("#capture-prompt"), `Invalid subnet "${v}" — use CIDR, e.g. 192.168.1.0/24`, "err");
  if (!settings.subnets.includes(v)) settings.subnets.push(v);
  $("#subnet-input").value = ""; renderChips(); $("#capture-prompt").textContent = "";
}
$("#add-subnet").addEventListener("click", addSubnet);
$("#subnet-input").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addSubnet(); } });
$("#detect-subnet").addEventListener("click", () => {
  const name = settings.iface || null;
  const cands = settings.ifaces.filter((i) => (name ? i.name === name : i.ip && i.subnets.length));
  const nets = [...new Set(cands.flatMap((i) => i.subnets))];
  if (!nets.length) return typePrompt($("#capture-prompt"), "Nothing detected — select an interface with an IP, or type the subnet", "err");
  settings.subnets = name ? nets : nets.slice(0, 1); renderChips();
  typePrompt($("#capture-prompt"), `Detected ${settings.subnets.join(", ")}`, "ok");
});

$("#capture-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#subnet-input").value.trim()) addSubnet();
  const btn = $("#apply-capture"); btn.disabled = true;
  typePrompt($("#capture-prompt"), "Reconfiguring capture engine…");
  try {
    const r = await api("/api/config", { method: "POST", body: JSON.stringify({ mode: settings.mode, iface: settings.iface || "", subnets: settings.subnets }) });
    typePrompt($("#capture-prompt"), `ONLINE · ${r.active.mode.toUpperCase()} · ${r.active.subnets.join(", ")}`, "ok");
    state.lastEvent = 0; state.detail = null; $("#feed").innerHTML = "";
    refreshStatus(); refreshDevices(); refreshDetail(true);
  } catch (err) {
    typePrompt($("#capture-prompt"), err.message, "err");
    refreshStatus();
  } finally { btn.disabled = false; }
});

$("#cred-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#c-new").value !== $("#c-new2").value) return typePrompt($("#cred-prompt"), "New passphrases do not match", "err");
  try {
    await api("/api/credentials", { method: "POST", body: JSON.stringify({ current: $("#c-cur").value, username: $("#c-user").value.trim(), password: $("#c-new").value }) });
    typePrompt($("#cred-prompt"), "Credentials updated. Re-authenticate…", "ok");
    setTimeout(() => { u.value = $("#c-user").value.trim(); showLogin(false); }, 1200);
  } catch (err) { typePrompt($("#cred-prompt"), err.message, "err"); }
});

$("#purge").addEventListener("click", async () => {
  if (!confirm("Erase all collected traffic data? This cannot be undone.")) return;
  await api("/api/purge", { method: "POST" }).catch(() => {});
  state.lastEvent = 0; state.detail = null; $("#feed").innerHTML = "";
  typePrompt($("#purge-prompt"), "All collected data purged", "ok");
  refreshDevices(); refreshDetail(true);
});

/* ---------------- boot ---------------- */
api("/api/session").then((s) => {
  if (s.default_password) $("#login-foot").innerHTML = "Default credentials: <b>admin</b> / <b>admin123</b> — change them in SETTINGS after login.";
  s.authenticated ? showApp() : showLogin(s.setup_required);
}).catch(() => showLogin());
