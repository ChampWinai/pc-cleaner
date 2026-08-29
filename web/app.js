"use strict";

const state = {
  items: [],       // {label, path, size, risk, note, checked} โ€” top-level scan targets
  ramTimer: null,
  crumbs: [],      // [{label, nodes}] drill-down breadcrumb trail for the treemap
};

const RISK_COLOR = { safe: "#30D158", low: "#FF9F0A", medium: "#FF6B35", high: "#FF453A" };

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------
// Toasts (non-intrusive corner notifications instead of blocking dialogs)
// ---------------------------------------------------------------------
function toast(message, type = "info", timeout = 3800) {
  const stack = $("toast-stack");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
    el.style.transition = "all 0.25s ease";
    setTimeout(() => el.remove(), 250);
  }, timeout);
}

// ---------------------------------------------------------------------
// Number count-up animation
// ---------------------------------------------------------------------
function humanParts(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return { value: n, unit: units[i] };
}

function animateValue(el, unitEl, toBytes, duration = 700) {
  const target = humanParts(toBytes);
  const start = performance.now();
  const from = 0;
  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    const current = from + (target.value - from) * eased;
    el.textContent = current.toFixed(target.value < 10 ? 1 : 0);
    unitEl.textContent = target.unit;
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------------
// Confirm modal (promise-based, replaces window.confirm)
// ---------------------------------------------------------------------
function confirmDialog(title, body) {
  return new Promise((resolve) => {
    $("confirmTitle").textContent = title;
    $("confirmBody").textContent = body;
    const modal = $("confirmModal");
    modal.classList.remove("hidden");
    const cleanup = (result) => {
      modal.classList.add("hidden");
      $("btnConfirmOk").onclick = null;
      $("btnConfirmCancel").onclick = null;
      resolve(result);
    };
    $("btnConfirmOk").onclick = () => cleanup(true);
    $("btnConfirmCancel").onclick = () => cleanup(false);
  });
}

// ---------------------------------------------------------------------
// Scan + list rendering
// ---------------------------------------------------------------------
window.onScanProgress = (label) => {
  $("statusText").textContent = `เธเธณเธฅเธฑเธเธชเนเธเธ... (${label})`;
};

async function scan() {
  $("statusText").textContent = "เธเธณเธฅเธฑเธเธชเนเธเธ...";
  $("btnCleanSelected").disabled = true;
  $("btnCleanAll").disabled = true;
  const deep = $("deepToggle").checked;
  const found = await window.pywebview.api.scan(deep);
  state.items = found.map((it) => ({ ...it, checked: false }));
  renderList();
  showTreemapRoot();
  updateTotals();
  $("statusText").textContent = found.length ? `เธเธ ${found.length} เธฃเธฒเธขเธเธฒเธฃ` : "เธชเนเธเธเน€เธชเธฃเนเธ";
  $("itemCountText").textContent = found.length ? `เธเธ ${found.length} เธฃเธฒเธขเธเธฒเธฃ` : "เน€เธเธฃเธทเนเธญเธเธชเธฐเธญเธฒเธ”เธญเธขเธนเนเนเธฅเนเธง";
  $("btnCleanAll").disabled = found.length === 0;
}

function iconFor(label) {
  const l = label.toLowerCase();
  if (l.includes("temp")) return "๐—‘";
  if (l.includes("prefetch")) return "โก";
  if (l.includes("cache")) return "๐";
  if (l.includes("report") || l.includes("dump") || l.includes("log")) return "โ ";
  if (l.includes("thumbnail")) return "๐–ผ";
  return "๐“";
}

function renderList() {
  const container = $("itemList");
  container.innerHTML = "";
  if (state.items.length === 0) {
    container.innerHTML = `<div class="empty-state">โ… เน€เธเธฃเธทเนเธญเธเธชเธฐเธญเธฒเธ”เธญเธขเธนเนเนเธฅเนเธง เนเธกเนเธเธเนเธเธฅเนเธเธขเธฐ</div>`;
    return;
  }
  state.items.forEach((it, idx) => {
    const row = document.createElement("div");
    row.className = "item-card";
    row.innerHTML = `
      <div class="item-check ${it.checked ? "checked" : ""}"></div>
      <div class="item-icon">${iconFor(it.label)}</div>
      <div class="item-text">
        <div class="item-label">${it.label} <span class="risk-dot" style="background:${RISK_COLOR[it.risk] || "#999"}"></span></div>
        <div class="item-note">${it.note}</div>
      </div>
      <div class="item-size">${humanReadable(it.size)}</div>
    `;
    row.addEventListener("click", () => {
      it.checked = !it.checked;
      row.querySelector(".item-check").classList.toggle("checked", it.checked);
      updateTotals();
    });
    container.appendChild(row);
  });
}

function humanReadable(bytes) {
  const p = humanParts(bytes);
  return `${p.value.toFixed(p.value < 10 ? 1 : 0)} ${p.unit}`;
}

function updateTotals() {
  const selected = state.items.filter((it) => it.checked);
  const total = selected.reduce((s, it) => s + it.size, 0);
  const grand = state.items.reduce((s, it) => s + it.size, 0) || 1;
  animateValue($("totalValue"), $("totalUnit"), total);

  const fraction = total / grand;
  const circumference = 326.7;
  $("ringFill").style.strokeDashoffset = String(circumference * (1 - fraction));
  $("ringLabel").textContent = `${Math.round(fraction * 100)}%`;

  $("btnCleanSelected").disabled = selected.length === 0;
}

// ---------------------------------------------------------------------
// Treemap โ€” simple recursive slice-and-dice layout with lazy drill-down.
// The top level mirrors the scan result cards; clicking a folder block
// fetches its immediate children on demand (backend.list_children) and
// pushes a breadcrumb level, so we never eagerly walk the whole disk.
// ---------------------------------------------------------------------
function layoutTreemap(nodes, x, y, w, h, out) {
  if (nodes.length === 0) return;
  if (nodes.length === 1) {
    out.push({ node: nodes[0], x, y, w, h });
    return;
  }
  const total = nodes.reduce((s, n) => s + n.size, 0);
  let acc = 0;
  let splitIndex = 0;
  for (let i = 0; i < nodes.length; i++) {
    acc += nodes[i].size;
    if (acc >= total / 2) {
      splitIndex = i + 1;
      break;
    }
  }
  splitIndex = Math.max(1, Math.min(nodes.length - 1, splitIndex));
  const left = nodes.slice(0, splitIndex);
  const right = nodes.slice(splitIndex);
  const leftTotal = left.reduce((s, n) => s + n.size, 0);
  const frac = leftTotal / total;

  if (w >= h) {
    const splitW = w * frac;
    layoutTreemap(left, x, y, splitW, h, out);
    layoutTreemap(right, x + splitW, y, w - splitW, h, out);
  } else {
    const splitH = h * frac;
    layoutTreemap(left, x, y, w, splitH, out);
    layoutTreemap(right, x, y + splitH, w, h - splitH, out);
  }
}

function colorForNode(node) {
  if (node.risk) return RISK_COLOR[node.risk] || "#888";
  if (node.path === null) return "var(--other-color)"; // aggregated "เธญเธทเนเธเน" bucket
  return node.is_dir ? "var(--accent)" : "var(--file-color)";
}

function showTreemapRoot() {
  const nodes = state.items.map((it) => ({
    label: it.label, size: it.size, risk: it.risk, note: it.note,
    path: it.path, is_dir: true,
  }));
  state.crumbs = [{ label: "เธ เธฒเธเธฃเธงเธก", nodes }];
  renderBreadcrumb();
  paintTreemap(nodes);
}

async function drillInto(node) {
  if (!node.path || !node.is_dir) {
    toast(`${node.label || node.name} โ€” ${humanReadable(node.size)}`, "info", 2200);
    return;
  }
  const children = await window.pywebview.api.get_children(node.path);
  if (children.length === 0) {
    toast("เนเธกเนเธกเธตเนเธเธฅเนเธขเนเธญเธขเนเธซเนเน€เธเธฒเธฐเธฅเธถเธเธ•เนเธญ", "info", 2000);
    return;
  }
  const nodes = children.map((c) => ({
    label: c.name, size: c.size, risk: null, note: "",
    path: c.path, is_dir: c.is_dir,
  }));
  state.crumbs.push({ label: node.label, nodes });
  renderBreadcrumb();
  paintTreemap(nodes);
}

function goToCrumb(index) {
  state.crumbs = state.crumbs.slice(0, index + 1);
  renderBreadcrumb();
  paintTreemap(state.crumbs[index].nodes);
}

function renderBreadcrumb() {
  const bar = $("breadcrumb");
  bar.innerHTML = "";
  state.crumbs.forEach((crumb, i) => {
    if (i > 0) {
      const sep = document.createElement("span");
      sep.className = "breadcrumb-sep";
      sep.textContent = "โ€บ";
      bar.appendChild(sep);
    }
    const el = document.createElement("span");
    const isCurrent = i === state.crumbs.length - 1;
    el.className = "breadcrumb-item" + (isCurrent ? " current" : "");
    el.textContent = crumb.label;
    if (!isCurrent) el.addEventListener("click", () => goToCrumb(i));
    bar.appendChild(el);
  });
}

function paintTreemap(nodes) {
  const container = $("treemap");
  container.innerHTML = "";
  if (nodes.length === 0) {
    container.innerHTML = `<div class="empty-state">เนเธกเนเธกเธตเธเนเธญเธกเธนเธฅเนเธซเนเนเธชเธ”เธ</div>`;
    return;
  }
  const w = container.clientWidth || 600;
  const h = container.clientHeight || 220;
  const rects = [];
  layoutTreemap(nodes, 0, 0, w, h, rects);

  rects.forEach(({ node, x, y, w: rw, h: rh }) => {
    const block = document.createElement("div");
    block.className = "treemap-block";
    block.style.left = `${x}px`;
    block.style.top = `${y}px`;
    block.style.width = `${Math.max(0, rw - 2)}px`;
    block.style.height = `${Math.max(0, rh - 2)}px`;
    block.style.background = colorForNode(node);
    block.style.cursor = node.is_dir && node.path ? "pointer" : "default";
    if (rw > 60 && rh > 28) {
      block.innerHTML = `${node.label}<span class="tm-size">${humanReadable(node.size)}</span>`;
    }
    block.title = `${node.label} โ€” ${humanReadable(node.size)}${node.note ? "\n" + node.note : ""}`;
    block.addEventListener("click", () => drillInto(node));
    container.appendChild(block);
  });
}

function renderTreemap() {
  // Re-paint whatever level is currently active (used on window resize).
  if (state.crumbs.length === 0) return;
  paintTreemap(state.crumbs[state.crumbs.length - 1].nodes);
}

// ---------------------------------------------------------------------
// Cleaning actions
// ---------------------------------------------------------------------
async function cleanSelected() {
  await performClean(state.items.filter((it) => it.checked));
}

async function cleanAll() {
  await performClean(state.items.slice());
}

async function performClean(selected) {
  if (selected.length === 0) {
    toast("เธเธฃเธธเธ“เธฒเน€เธฅเธทเธญเธเธฃเธฒเธขเธเธฒเธฃเธ—เธตเนเธ•เนเธญเธเธเธฒเธฃเธฅเธเธเนเธญเธ", "error");
    return;
  }
  const total = selected.reduce((s, it) => s + it.size, 0);
  const risky = selected.filter((it) => it.risk === "medium" || it.risk === "high");
  let body = `เธเธฐเธขเนเธฒเธขเนเธเธฅเน ${selected.length} เธฃเธฒเธขเธเธฒเธฃ เธฃเธงเธก ${humanReadable(total)} เน€เธเนเธฒ Safety Vault (เธเธนเนเธเธทเธเนเธ”เน 14 เธงเธฑเธ)`;
  if (risky.length) {
    body += "\n\nโ  เธเธงเธฃเธ•เธฃเธงเธเธชเธญเธ:\n" + risky.map((it) => `โ€ข ${it.label}: ${it.note}`).join("\n");
  }
  const ok = await confirmDialog("เธขเธทเธเธขเธฑเธเธเธฒเธฃเธฅเธ", body);
  if (!ok) return;

  $("btnCleanSelected").disabled = true;
  $("btnCleanAll").disabled = true;
  $("statusText").textContent = "เธเธณเธฅเธฑเธเธฅเธ...";

  const payload = selected.map((it) => ({ label: it.label, path: it.path }));
  const result = await window.pywebview.api.clean(payload);

  toast(`เธขเนเธฒเธขเนเธเธขเธฑเธ Safety Vault เนเธฅเนเธง เธเธฅเธ”เธเธทเนเธเธ—เธตเนเนเธ”เน ${result.freed_human}`, "success");
  if (result.errors.length) {
    toast(`${result.errors.length} เธฃเธฒเธขเธเธฒเธฃเธ—เธณเนเธกเนเธชเธณเน€เธฃเนเธ (เนเธเธฅเนเธเธณเธฅเธฑเธเธ–เธนเธเนเธเนเธเธฒเธเธญเธขเธนเน)`, "error");
  }
  refreshVaultCount();
  scan();
}

// ---------------------------------------------------------------------
// RAM
// ---------------------------------------------------------------------
async function refreshRam() {
  const status = await window.pywebview.api.ram_status();
  $("ramText").textContent = `${humanReadable(status.used)} / ${humanReadable(status.total)} (${Math.round(status.percent)}%)`;
  const bar = $("ramBar");
  bar.style.width = `${status.percent}%`;
  bar.style.background = status.percent > 85 ? "var(--danger)" : "var(--accent)";
}

async function cleanRam() {
  $("btnRam").disabled = true;
  $("ramText").textContent = "เธเธณเธฅเธฑเธเธฅเนเธฒเธ RAM...";
  const result = await window.pywebview.api.clean_ram();
  $("btnRam").disabled = false;
  await refreshRam();
  const note = result.skipped > 0 ? ` (เธเนเธฒเธก ${result.skipped} เนเธเธฃเน€เธเธชเธ—เธตเนเนเธกเนเธกเธตเธชเธดเธ—เธเธดเน โ€” เธฃเธฑเธ Admin เน€เธเธทเนเธญเธฅเนเธฒเธเนเธ”เนเธเธฃเธเธเธถเนเธ)` : "";
  toast(`เธฅเนเธฒเธ Working Set เธเธญเธ ${result.trimmed} เนเธเธฃเน€เธเธช เธเธทเธ RAM เนเธ”เน ${result.freed_human}${note}`, "success");
}

// ---------------------------------------------------------------------
// Recycle bin
// ---------------------------------------------------------------------
async function cleanBin() {
  const ok = await confirmDialog(
    "เธขเธทเธเธขเธฑเธเธฅเนเธฒเธเธ–เธฑเธเธเธขเธฐ",
    "เธเธฐเธฅเธเนเธเธฅเนเธ—เธฑเนเธเธซเธกเธ”เนเธเธ–เธฑเธเธเธขเธฐเธญเธขเนเธฒเธเธ–เธฒเธงเธฃ เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เธเธนเนเธเธทเธเนเธ”เน"
  );
  if (!ok) return;
  $("btnBin").disabled = true;
  const result = await window.pywebview.api.empty_recycle_bin();
  $("btnBin").disabled = false;
  if (result.success) toast("เธฅเนเธฒเธเธ–เธฑเธเธเธขเธฐเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง", "success");
  else toast("เธฅเนเธฒเธเธ–เธฑเธเธเธขเธฐเนเธกเนเธชเธณเน€เธฃเนเธ เธฅเธญเธเธฃเธฑเธเนเธเธ Administrator", "error");
}

// ---------------------------------------------------------------------
// Safety Vault
// ---------------------------------------------------------------------
async function refreshVaultCount() {
  const entries = await window.pywebview.api.vault_list();
  const total = entries.reduce((s, e) => s + e.size, 0);
  $("vaultText").textContent = `${entries.length} เธฃเธฒเธขเธเธฒเธฃ (${humanReadable(total)})`;
  return entries;
}

async function openVault() {
  const entries = await refreshVaultCount();
  const list = $("vaultList");
  list.innerHTML = "";
  if (entries.length === 0) {
    list.innerHTML = `<div class="empty-state">เธขเธฑเธเนเธกเนเธกเธตเนเธเธฅเนเนเธ Vault</div>`;
  } else {
    entries.forEach((e) => {
      const row = document.createElement("div");
      row.className = "vault-row";
      row.innerHTML = `
        <div class="vault-row-info">
          <div class="vault-row-label">${e.label}</div>
          <div class="vault-row-meta">${e.size_human} โ€ข เธฅเธเน€เธกเธทเนเธญ ${e.deleted_date}</div>
        </div>
        <button class="btn btn-accent vault-restore">เธเธนเนเธเธทเธ</button>
        <button class="btn btn-danger vault-purge">เธฅเธเธ–เธฒเธงเธฃ</button>
      `;
      row.querySelector(".vault-restore").addEventListener("click", async () => {
        const r = await window.pywebview.api.vault_restore(e.id);
        if (r.success) toast(`เธเธนเนเธเธทเธ ${e.label} เน€เธฃเธตเธขเธเธฃเนเธญเธข`, "success");
        else toast("เธเธนเนเธเธทเธเนเธกเนเธชเธณเน€เธฃเนเธ เธ•เธณเนเธซเธเนเธเน€เธ”เธดเธกเธญเธฒเธเธกเธตเนเธเธฅเนเธญเธขเธนเนเนเธฅเนเธง", "error");
        openVault();
      });
      row.querySelector(".vault-purge").addEventListener("click", async () => {
        await window.pywebview.api.vault_purge(e.id);
        openVault();
      });
      list.appendChild(row);
    });
  }
  $("vaultModal").classList.remove("hidden");
}

// ---------------------------------------------------------------------
// Docker cache
// ---------------------------------------------------------------------
async function initDocker() {
  const available = await window.pywebview.api.docker_available();
  $("btnDocker").disabled = !available;
  $("dockerText").textContent = available ? "เธฅเนเธฒเธ build cache/image เธ—เธตเนเนเธกเนเนเธ”เนเนเธเน" : "เนเธกเนเธเธ Docker เธเธเน€เธเธฃเธทเนเธญเธเธเธตเน";
}

async function cleanDocker() {
  const ok = await confirmDialog(
    "เธขเธทเธเธขเธฑเธเธฅเนเธฒเธ Docker Cache",
    "เธเธฐเธฃเธฑเธ 'docker system prune -f' เน€เธเธทเนเธญเธฅเธ container/image/network เธ—เธตเนเนเธกเนเนเธ”เนเนเธเนเธเธฒเธเธญเธขเธนเน (เธเธฅเธญเธ”เธ เธฑเธข เน€เธเนเธเธเธณเธชเธฑเนเธเธ—เธฒเธเธเธฒเธฃเธเธญเธ Docker)"
  );
  if (!ok) return;
  $("btnDocker").disabled = true;
  const result = await window.pywebview.api.docker_prune();
  $("btnDocker").disabled = false;
  if (result.success) toast(`เธฅเนเธฒเธ Docker cache เนเธฅเนเธง เธเธฅเธ”เธเธทเนเธเธ—เธตเน ${result.freed_human}`, "success");
  else toast(`เธฅเนเธฒเธเนเธกเนเธชเธณเน€เธฃเนเธ: ${result.message}`, "error");
}

// ---------------------------------------------------------------------
// Auto Clean (hourly Scheduled Task)
// ---------------------------------------------------------------------
function formatLastRun(lastRun) {
  if (!lastRun) return "เธขเธฑเธเนเธกเนเน€เธเธขเธฃเธฑเธ";
  const time = lastRun.ran_at.split("T")[1]?.slice(0, 5) || "";
  return `เธฃเธฑเธเธฅเนเธฒเธชเธธเธ” ${lastRun.ran_at_date} ${time} โ€” เธฅเนเธฒเธเนเธ”เน ${lastRun.freed_human}`;
}

async function refreshAutoCleanStatus() {
  const status = await window.pywebview.api.auto_clean_status();
  $("autoCleanToggle").checked = status.task_active;
  $("autoCleanInterval").value = String(status.interval_hours || 1);
  $("autoCleanInterval").disabled = !status.task_active;
  $("autoCleanText").textContent = status.task_active
    ? formatLastRun(status.last_run)
    : "เธเธดเธ”เธญเธขเธนเน โ€” เธฅเนเธฒเธเน€เธเธเธฒเธฐเธฃเธฒเธขเธเธฒเธฃเธ—เธตเนเธเธฅเธญเธ”เธ เธฑเธข 100%";
  return status;
}

async function toggleAutoClean() {
  const toggle = $("autoCleanToggle");
  const wantOn = toggle.checked;
  toggle.disabled = true;
  if (wantOn) {
    const hours = Number($("autoCleanInterval").value);
    const result = await window.pywebview.api.auto_clean_enable(hours, false);
    if (result.success) toast(`เน€เธเธดเธ”เธฅเนเธฒเธเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเธ—เธธเธ ${hours} เธเธก. เนเธฅเนเธง (เน€เธเธเธฒเธฐเธฃเธฒเธขเธเธฒเธฃเธเธฅเธญเธ”เธ เธฑเธข)`, "success");
    else {
      toast(result.message || "เน€เธเธดเธ”เนเธเนเธเธฒเธเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
      toggle.checked = false;
    }
  } else {
    await window.pywebview.api.auto_clean_disable();
    toast("เธเธดเธ”เธฅเนเธฒเธเธญเธฑเธ•เนเธเธกเธฑเธ•เธดเนเธฅเนเธง", "info");
  }
  toggle.disabled = false;
  await refreshAutoCleanStatus();
}

async function changeAutoCleanInterval() {
  if (!$("autoCleanToggle").checked) return;
  const hours = Number($("autoCleanInterval").value);
  await window.pywebview.api.auto_clean_enable(hours, false);
  toast(`เธเธฃเธฑเธเน€เธเนเธเธฅเนเธฒเธเธ—เธธเธ ${hours} เธเธก. เนเธฅเนเธง`, "success");
  await refreshAutoCleanStatus();
}

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------
function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
  $("footerClean").classList.toggle("hidden", name !== "clean");
  if (name === "uninstall") loadApps();
  if (name === "startup") loadStartup();
  if (name === "gamemode") loadGameMode();
  if (name === "drivers") loadDrivers();
}

// ---------------------------------------------------------------------
// App Uninstaller
// ---------------------------------------------------------------------
async function loadApps() {
  const list = $("appList");
  list.innerHTML = `<div class="empty-state">เธเธณเธฅเธฑเธเนเธซเธฅเธ”เธฃเธฒเธขเธเธฒเธฃเนเธเธฃเนเธเธฃเธก...</div>`;
  const apps = await window.pywebview.api.list_apps();
  list.innerHTML = "";
  if (apps.length === 0) {
    list.innerHTML = `<div class="empty-state">เนเธกเนเธเธเนเธเธฃเนเธเธฃเธกเธ—เธตเนเธ•เธดเธ”เธ•เธฑเนเธเนเธงเน</div>`;
    return;
  }
  apps.forEach((app) => {
    const row = document.createElement("div");
    row.className = "app-row";
    row.innerHTML = `
      <div class="app-row-info">
        <div class="app-row-name">${app.name}</div>
        <div class="app-row-meta">${app.publisher}${app.version ? " โ€ข v" + app.version : ""}</div>
      </div>
      <div class="app-row-size">${app.size_human}</div>
      <button class="btn btn-danger">เธ–เธญเธเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธ</button>
    `;
    row.querySelector("button").addEventListener("click", async () => {
      const ok = await confirmDialog(
        "เธขเธทเธเธขเธฑเธเธเธฒเธฃเธ–เธญเธเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธ",
        `เธเธฐเน€เธเธดเธ”เธ•เธฑเธงเธ–เธญเธเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธเธเธญเธ "${app.name}" โ€” เธ—เธณเธ•เธฒเธกเธเธฑเนเธเธ•เธญเธเนเธเธซเธเนเธฒเธ•เนเธฒเธเธ—เธตเนเน€เธเธดเธ”เธเธถเนเธเธกเธฒเนเธซเนเธเธ`
      );
      if (!ok) return;
      const cmd = app.quiet_uninstall_string || app.uninstall_string;
      const result = await window.pywebview.api.uninstall_app(cmd);
      if (result.success) toast(`เน€เธเธดเธ”เธ•เธฑเธงเธ–เธญเธเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธเธเธญเธ ${app.name} เนเธฅเนเธง`, "info");
      else toast("เน€เธเธดเธ”เธ•เธฑเธงเธ–เธญเธเธเธฒเธฃเธ•เธดเธ”เธ•เธฑเนเธเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
    });
    list.appendChild(row);
  });
}

// ---------------------------------------------------------------------
// Startup Manager
// ---------------------------------------------------------------------
const STATUS_LABEL = { enabled: "เน€เธเธดเธ”เนเธเนเธเธฒเธ", disabled: "เธเธดเธ”เธญเธขเธนเน", delayed: "เธซเธเนเธงเธเน€เธงเธฅเธฒ 2 เธเธฒเธ—เธต" };

async function loadStartup() {
  const list = $("startupList");
  list.innerHTML = `<div class="empty-state">เธเธณเธฅเธฑเธเนเธซเธฅเธ”...</div>`;
  const items = await window.pywebview.api.list_startup();
  list.innerHTML = "";
  if (items.length === 0) {
    list.innerHTML = `<div class="empty-state">เนเธกเนเธเธเนเธเธฃเนเธเธฃเธกเธ—เธตเนเน€เธเธดเธ”เธเธฃเนเธญเธก Windows</div>`;
    return;
  }
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "startup-row";
    const sourceLabel = it.source === "registry" ? "Registry" : it.source === "folder" ? "Startup Folder" : "Scheduled Task";
    row.innerHTML = `
      <div class="startup-row-info">
        <div class="startup-row-name">${it.name}</div>
        <div class="startup-row-meta">${sourceLabel}</div>
      </div>
      <span class="status-pill status-${it.status}">${STATUS_LABEL[it.status]}</span>
      <div class="startup-row-actions"></div>
    `;
    const actions = row.querySelector(".startup-row-actions");

    if (it.status === "enabled") {
      const disableBtn = document.createElement("button");
      disableBtn.className = "btn btn-ghost";
      disableBtn.textContent = "เธเธดเธ”";
      disableBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.disable_startup(it.id);
        if (r.success) { toast(`เธเธดเธ” ${it.name} เนเธฅเนเธง`, "success"); loadStartup(); }
        else toast(r.message || "เธเธดเธ”เนเธกเนเธชเธณเน€เธฃเนเธ", "error");
      });
      actions.appendChild(disableBtn);

      if (it.source === "registry") {
        const delayBtn = document.createElement("button");
        delayBtn.className = "btn btn-accent";
        delayBtn.textContent = "เธซเธเนเธงเธเน€เธงเธฅเธฒ";
        delayBtn.addEventListener("click", async () => {
          const r = await window.pywebview.api.delay_startup(it.id);
          if (r.success) { toast(`เธซเธเนเธงเธเน€เธงเธฅเธฒเน€เธเธดเธ” ${it.name} เน€เธเนเธ 2 เธเธฒเธ—เธตเธซเธฅเธฑเธเธฅเนเธญเธเธญเธดเธเนเธฅเนเธง`, "success"); loadStartup(); }
          else toast(r.message || "เธซเธเนเธงเธเน€เธงเธฅเธฒเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
        });
        actions.appendChild(delayBtn);
      }
    } else if (it.status === "disabled") {
      const enableBtn = document.createElement("button");
      enableBtn.className = "btn btn-accent";
      enableBtn.textContent = "เน€เธเธดเธ”เนเธเน";
      enableBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.enable_startup(it.id);
        if (r.success) { toast(`เน€เธเธดเธ”เนเธเน ${it.name} เนเธฅเนเธง`, "success"); loadStartup(); }
        else toast(r.message || "เน€เธเธดเธ”เนเธเนเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
      });
      actions.appendChild(enableBtn);
    } else if (it.status === "delayed") {
      const cancelBtn = document.createElement("button");
      cancelBtn.className = "btn btn-ghost";
      cancelBtn.textContent = "เธขเธเน€เธฅเธดเธเธซเธเนเธงเธ";
      cancelBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.undo_delay_startup(it.name);
        if (r.success) { toast(`เธขเธเน€เธฅเธดเธเธเธฒเธฃเธซเธเนเธงเธเน€เธงเธฅเธฒเธเธญเธ ${it.name} เนเธฅเนเธง`, "success"); loadStartup(); }
        else toast("เธขเธเน€เธฅเธดเธเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
      });
      actions.appendChild(cancelBtn);
    }

    list.appendChild(row);
  });
}

// ---------------------------------------------------------------------
// Game Mode
// ---------------------------------------------------------------------
const gameModeState = { processes: [], checked: new Set() };

async function loadGameMode() {
  const status = await window.pywebview.api.game_mode_status();
  renderGameModeStatus(status.active);

  const list = $("processList");
  list.innerHTML = `<div class="empty-state">เธเธณเธฅเธฑเธเนเธซเธฅเธ”เธฃเธฒเธขเธเธฒเธฃเนเธเธฃเนเธเธฃเธก...</div>`;
  const processes = await window.pywebview.api.list_freezable_processes();
  gameModeState.processes = processes;
  list.innerHTML = "";
  if (processes.length === 0) {
    list.innerHTML = `<div class="empty-state">เนเธกเนเธเธเนเธเธฃเนเธเธฃเธกเธเธทเนเธเธซเธฅเธฑเธเธ—เธตเนเนเธเนเนเธเนเธเนเธ”เน</div>`;
    return;
  }
  processes.forEach((p) => {
    const row = document.createElement("div");
    row.className = "item-card";
    row.innerHTML = `
      <div class="item-check ${gameModeState.checked.has(p.name) ? "checked" : ""}"></div>
      <div class="item-icon">๐งฉ</div>
      <div class="item-text">
        <div class="item-label">${p.name}</div>
        <div class="item-note">${p.pids.length} เนเธเธฃเน€เธเธช</div>
      </div>
      <div class="item-size">${p.memory_human}</div>
    `;
    row.addEventListener("click", () => {
      if (gameModeState.checked.has(p.name)) gameModeState.checked.delete(p.name);
      else gameModeState.checked.add(p.name);
      row.querySelector(".item-check").classList.toggle("checked");
    });
    list.appendChild(row);
  });
}

function renderGameModeStatus(active) {
  $("gameModeStatus").textContent = active ? "๐ข เธเธณเธฅเธฑเธเธ—เธณเธเธฒเธ" : "เธเธดเธ”เธญเธขเธนเน";
  const btn = $("btnGameModeToggle");
  btn.textContent = active ? "โน เธเธดเธ” Game Mode" : "๐ฎ เน€เธเธดเธ” Game Mode";
  btn.className = active ? "btn btn-danger" : "btn btn-accent";
}

async function toggleGameMode() {
  const status = await window.pywebview.api.game_mode_status();
  if (status.active) {
    const result = await window.pywebview.api.disable_game_mode();
    toast(`เธเธทเธเธเนเธฒเนเธเธฃเนเธเธฃเธกเธ—เธตเนเนเธเนเนเธเนเธเนเธงเนเนเธฅเนเธง ${result.resumed}/${result.total} เธฃเธฒเธขเธเธฒเธฃ`, "success");
  } else {
    if (gameModeState.checked.size === 0) {
      toast("เธเธฃเธธเธ“เธฒเน€เธฅเธทเธญเธเนเธเธฃเนเธเธฃเธกเธ—เธตเนเธ•เนเธญเธเธเธฒเธฃเนเธเนเนเธเนเธเธเนเธญเธ", "error");
      return;
    }
    const names = Array.from(gameModeState.checked);
    const ok = await confirmDialog(
      "เธขเธทเธเธขเธฑเธเน€เธเธดเธ” Game Mode",
      `เธเธฐเนเธเนเนเธเนเธ ${names.length} เนเธเธฃเนเธเธฃเธก: ${names.join(", ")}\nเนเธเธฃเนเธเธฃเธกเน€เธซเธฅเนเธฒเธเธตเนเธเธฐเธเนเธฒเธ (เนเธกเนเธ•เธญเธเธชเธเธญเธ) เธเธเธเธงเนเธฒเธเธฐเธเธดเธ” Game Mode`
    );
    if (!ok) return;
    const result = await window.pywebview.api.enable_game_mode(names);
    toast(`เนเธเนเนเธเนเธเนเธฅเนเธง ${result.frozen} เนเธเธฃเน€เธเธช`, "success");
  }
  loadGameMode();
}

// ---------------------------------------------------------------------
// Privacy / Sensitive Data Scanner
// ---------------------------------------------------------------------
const CATEGORY_LABEL = { thai_id: "เน€เธฅเธเธเธฑเธ•เธฃเธเธฃเธฐเธเธฒเธเธ", credit_card: "เน€เธฅเธเธเธฑเธ•เธฃเน€เธเธฃเธ”เธดเธ•", password: "เธฃเธซเธฑเธชเธเนเธฒเธเธ—เธตเนเน€เธเนเธฒเธฃเธซเธฑเธชเนเธกเนเนเธ”เน" };

async function pickFolderAndScan() {
  const folder = await window.pywebview.api.pick_folder();
  if (!folder) return;
  $("privacyFolderText").textContent = `เธเธณเธฅเธฑเธเธชเนเธเธ: ${folder}`;
  const list = $("sensitiveList");
  list.innerHTML = `<div class="empty-state">เธเธณเธฅเธฑเธเธชเนเธเธ... (เน€เธเธเธฒเธฐเนเธเธฅเนเธเนเธญเธเธงเธฒเธก เน€เธเนเธ .txt .csv .json .log)</div>`;

  const findings = await window.pywebview.api.scan_sensitive_data(folder);
  $("privacyFolderText").textContent = `เธชเนเธเธเนเธฅเนเธง: ${folder} โ€” เธเธ ${findings.length} เธเธธเธ”เธ—เธตเนเธเนเธฒเธชเธเธชเธฑเธข`;
  list.innerHTML = "";
  if (findings.length === 0) {
    list.innerHTML = `<div class="empty-state">โ… เนเธกเนเธเธเธเนเธญเธกเธนเธฅเธญเนเธญเธเนเธซเธงเธ—เธตเนเธ•เธฃเธเธฃเธนเธเนเธเธเธ—เธตเนเธ•เธฃเธงเธเธชเธญเธเนเธ”เน</div>`;
    return;
  }

  // Group by file so the user acts on a whole file at once.
  const byFile = {};
  findings.forEach((f) => {
    (byFile[f.path] = byFile[f.path] || []).push(f);
  });

  Object.entries(byFile).forEach(([path, items]) => {
    const row = document.createElement("div");
    row.className = "app-row";
    const categories = [...new Set(items.map((i) => CATEGORY_LABEL[i.category] || i.category))];
    row.innerHTML = `
      <div class="app-row-info">
        <div class="app-row-name">${path.split("\\").pop()}</div>
        <div class="app-row-meta">${path}</div>
        <div class="app-row-meta">เธเธ: ${categories.join(", ")} (${items.length} เธเธธเธ”) โ€” เธ•เธฑเธงเธญเธขเนเธฒเธ: ${items[0].snippet}</div>
      </div>
      <button class="btn btn-ghost btn-vault-file">เธขเนเธฒเธขเน€เธเนเธฒ Vault</button>
      <button class="btn btn-danger btn-shred-file">เธฅเธเธ–เธฒเธงเธฃ (Shred)</button>
    `;
    row.querySelector(".btn-vault-file").addEventListener("click", async () => {
      const r = await window.pywebview.api.vault_file(path, "เนเธเธฅเนเธเนเธญเธกเธนเธฅเธญเนเธญเธเนเธซเธง");
      if (r.success) { toast("เธขเนเธฒเธขเน€เธเนเธฒ Safety Vault เนเธฅเนเธง", "success"); row.remove(); }
    });
    row.querySelector(".btn-shred-file").addEventListener("click", async () => {
      const ok = await confirmDialog("เธขเธทเธเธขเธฑเธเธฅเธเธ–เธฒเธงเธฃ", `เธเธฐเน€เธเธตเธขเธเธ—เธฑเธเนเธฅเธฐเธฅเธ "${path}" เธญเธขเนเธฒเธเธ–เธฒเธงเธฃ เธเธนเนเธเธทเธเนเธกเนเนเธ”เน`);
      if (!ok) return;
      const r = await window.pywebview.api.shred_file(path);
      if (r.success) { toast("เธฅเธเนเธเธฅเนเธญเธขเนเธฒเธเธ–เธฒเธงเธฃเนเธฅเนเธง", "success"); row.remove(); }
      else toast("เธฅเธเนเธกเนเธชเธณเน€เธฃเนเธ เนเธเธฅเนเธญเธฒเธเธ–เธนเธเนเธเนเธเธฒเธเธญเธขเธนเน", "error");
    });
    list.appendChild(row);
  });
}

// ---------------------------------------------------------------------
// Hardware & Driver update check
// ---------------------------------------------------------------------
function ageClass(days) {
  if (days === null || days === undefined) return "age-fresh";
  if (days < 365) return "age-fresh";
  if (days < 365 * 3) return "age-aging";
  return "age-old";
}

async function loadDrivers() {
  const list = $("driverList");
  list.innerHTML = `<div class="empty-state">เธเธณเธฅเธฑเธเนเธซเธฅเธ”เธฃเธฒเธขเธเธฒเธฃเนเธ”เธฃเน€เธงเธญเธฃเน...</div>`;
  const drivers = await window.pywebview.api.list_drivers();
  list.innerHTML = "";
  drivers.forEach((d) => {
    const years = d.age_days !== null ? (d.age_days / 365).toFixed(1) : "?";
    const row = document.createElement("div");
    row.className = "startup-row";
    row.innerHTML = `
      <div class="startup-row-info">
        <div class="startup-row-name">${d.name}</div>
        <div class="startup-row-meta">${d.manufacturer} โ€ข v${d.version || "เนเธกเนเธ—เธฃเธฒเธ"} โ€ข เธ•เธดเธ”เธ•เธฑเนเธเน€เธกเธทเนเธญ ${d.date}</div>
      </div>
      <span class="status-pill ${ageClass(d.age_days)}">${d.age_days !== null ? years + " เธเธต" : "เนเธกเนเธ—เธฃเธฒเธเธญเธฒเธขเธธ"}</span>
    `;
    list.appendChild(row);
  });
}

async function checkDriverUpdates() {
  $("btnCheckDrivers").disabled = true;
  $("driverUpdateText").textContent = "เธเธณเธฅเธฑเธเธ•เธฃเธงเธเธชเธญเธเธเธฑเธ Windows Update... (เธญเธฒเธเนเธเนเน€เธงเธฅเธฒเธชเธฑเธเธเธฃเธนเน)";
  const result = await window.pywebview.api.check_driver_updates();
  $("btnCheckDrivers").disabled = false;

  if (!result.success) {
    $("driverUpdateText").textContent = "เธ•เธฃเธงเธเธชเธญเธเนเธกเนเธชเธณเน€เธฃเนเธ โ€” เธ•เธฃเธงเธเธชเธญเธเธงเนเธฒ Windows Update service เน€เธเธดเธ”เธญเธขเธนเนเนเธฅเธฐเน€เธเธทเนเธญเธกเธ•เนเธญเธญเธดเธเน€เธ—เธญเธฃเนเน€เธเนเธ•";
    toast(result.message || "เธ•เธฃเธงเธเธชเธญเธเนเธกเนเธชเธณเน€เธฃเนเธ", "error");
    return;
  }

  if (result.updates.length === 0) {
    $("driverUpdateText").textContent = "โ… เนเธกเนเธกเธตเธญเธฑเธเน€เธ”เธ•เนเธ”เธฃเน€เธงเธญเธฃเนเธ—เธตเนเธฃเธญเธ•เธดเธ”เธ•เธฑเนเธเธเธฒเธ Windows Update";
    $("driverUpdatesPanel").style.display = "none";
    return;
  }

  $("driverUpdateText").textContent = `เธเธเธญเธฑเธเน€เธ”เธ• ${result.updates.length} เธฃเธฒเธขเธเธฒเธฃเธเธฒเธ Windows Update`;
  $("driverUpdatesPanel").style.display = "block";
  const list = $("driverUpdateList");
  list.innerHTML = "";
  result.updates.forEach((u) => {
    const row = document.createElement("div");
    row.className = "app-row";
    row.innerHTML = `
      <div class="app-row-info">
        <div class="app-row-name">${u.title}</div>
        <div class="app-row-meta">${u.description}</div>
      </div>
      <div class="app-row-size">${u.size_mb} MB</div>
    `;
    list.appendChild(row);
  });
}

async function openWindowsUpdate() {
  await window.pywebview.api.open_windows_update();
}

// ---------------------------------------------------------------------
// Wire up
// ---------------------------------------------------------------------
function init() {
  $("btnRescan").addEventListener("click", scan);
  $("btnSelectAll").addEventListener("click", () => {
    state.items.forEach((it) => (it.checked = true));
    renderList();
    updateTotals();
  });
  $("btnSelectNone").addEventListener("click", () => {
    state.items.forEach((it) => (it.checked = false));
    renderList();
    updateTotals();
  });
  $("btnCleanSelected").addEventListener("click", cleanSelected);
  $("btnCleanAll").addEventListener("click", cleanAll);
  $("btnRam").addEventListener("click", cleanRam);
  $("btnBin").addEventListener("click", cleanBin);
  $("btnVault").addEventListener("click", openVault);
  $("btnCloseVault").addEventListener("click", () => $("vaultModal").classList.add("hidden"));
  $("btnDocker").addEventListener("click", cleanDocker);
  $("btnGameModeToggle").addEventListener("click", toggleGameMode);
  $("btnPickFolder").addEventListener("click", pickFolderAndScan);
  $("btnCheckDrivers").addEventListener("click", checkDriverUpdates);
  $("btnOpenWU").addEventListener("click", openWindowsUpdate);
  $("deepToggle").addEventListener("change", scan);
  $("autoCleanToggle").addEventListener("change", toggleAutoClean);
  $("autoCleanInterval").addEventListener("change", changeAutoCleanInterval);
  window.addEventListener("resize", renderTreemap);
  document.querySelectorAll(".tab-btn").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );

  scan();
  refreshRam();
  refreshVaultCount();
  initDocker();
  refreshAutoCleanStatus();
  state.ramTimer = setInterval(refreshRam, 5000);
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}
