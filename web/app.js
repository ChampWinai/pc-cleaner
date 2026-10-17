"use strict";

// Lazy handle on the pywebview bridge: `api.method()` resolves at call time, so
// code that runs before the bridge is ready (or in a plain browser) is safe.
const api = new Proxy({}, { get: (_, k) => window.pywebview && window.pywebview.api && window.pywebview.api[k] });

const state = {
  items: [],       // {label, path, size, risk, note, checked} — top-level scan targets
  ramTimer: null,
  crumbs: [],      // [{label, nodes}] drill-down breadcrumb trail for the treemap
  darkMode: localStorage.getItem('darkMode') === 'true' || window.matchMedia('(prefers-color-scheme: dark)').matches,
  retentionDays: 14,
};

const RISK_COLOR = { safe: "#30D158", low: "#FF9F0A", medium: "#FF6B35", high: "#FF453A" };

const $ = (id) => document.getElementById(id);

// =========================================================================
// THEME MANAGEMENT (DARK MODE / LIGHT MODE)
// =========================================================================
function initTheme() {
  const root = document.documentElement;
  if (state.darkMode) {
    root.setAttribute('data-theme', 'dark');
    document.body.classList.add('dark-mode');
  } else {
    root.setAttribute('data-theme', 'light');
    document.body.classList.remove('dark-mode');
  }
}

// =========================================================================
// CHECK FOR UPDATES
// =========================================================================
async function checkForUpdates(manual = false) {
  if (!api || !api.check_for_updates) return;
  try {
    const r = await api.check_for_updates(manual);
    $("appVersion").textContent = (r.current || "").replace(/^v/, "");
    if (!r.available) {
      if (manual) toast("คุณใช้เวอร์ชันล่าสุดแล้ว", "success");
      return;
    }
    $("updateVersion").textContent = r.version;
    $("updateBanner").classList.remove("hidden");
    $("btnUpdateNow").disabled = !r.can_install;
    if (r.release_notes) {
      $("updateNotes").textContent = r.release_notes;
      $("updateNotesWrap").classList.remove("hidden");
    }
    if (!r.can_install) $("updateSub").textContent = "ติดตั้งอัตโนมัติไม่ได้ — กดดูในหน้า Release";
  } catch (e) {
    console.error("Update check failed:", e);
  }
}

async function startUpdate() {
  const btn = $("btnUpdateNow");
  btn.disabled = true;
  $("updateBanner").classList.add("busy");
  await api.start_update();
  const timer = setInterval(async () => {
    const s = await api.update_state();
    $("updateBarFill").style.width = s.percent + "%";
    $("updateSub").textContent = s.state === "downloading" ? `กำลังดาวน์โหลด ${s.percent}%` : $("updateSub").textContent;
    if (s.state === "ready") {
      clearInterval(timer);
      $("updateSub").textContent = "ตรวจสอบไฟล์แล้ว กำลังติดตั้ง...";
      await api.install_update();
    } else if (s.state === "error") {
      clearInterval(timer);
      $("updateBanner").classList.remove("busy");
      $("updateSub").textContent = `อัปเดตไม่สำเร็จ: ${s.message}`;
      btn.disabled = false;
    }
  }, 400);
}

// Initialize theme on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTheme);
} else {
  initTheme();
}


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
  $("statusText").textContent = `กำลังสแกน... (${label})`;
};

async function scan() {
  $("statusText").textContent = "กำลังสแกน...";
  $("btnCleanSelected").disabled = true;
  $("btnCleanAll").disabled = true;
  const deep = $("deepToggle").checked;
  const found = await window.pywebview.api.scan(deep);
  state.items = found.map((it) => ({ ...it, checked: false }));
  renderList();
  showTreemapRoot();
  updateTotals();
  $("statusText").textContent = found.length ? `พบ ${found.length} รายการ · รวม ${humanReadable(found.reduce((s, it) => s + it.size, 0))}` : "สแกนเสร็จ";
  $("itemCountText").textContent = found.length ? `พบ ${found.length} รายการ · รวม ${humanReadable(found.reduce((s, it) => s + it.size, 0))} (เลือกเพื่อล้าง)` : "เครื่องสะอาดอยู่แล้ว";
  $("btnCleanAll").disabled = found.length === 0;
}

function svgIcon(name) {
  return `<svg class="ico" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function iconFor(label) {
  const l = label.toLowerCase();
  if (l.includes("temp")) return svgIcon("trash");
  if (l.includes("prefetch")) return svgIcon("zap");
  if (l.includes("cache")) return svgIcon("globe");
  if (l.includes("report") || l.includes("dump") || l.includes("log")) return svgIcon("alert");
  if (l.includes("thumbnail")) return svgIcon("image");
  return svgIcon("folder");
}

function renderList() {
  const container = $("itemList");
  container.innerHTML = "";
  if (state.items.length === 0) {
    container.innerHTML = `<div class="empty-state">เครื่องสะอาดอยู่แล้ว ไม่พบไฟล์ขยะ</div>`;
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
// Treemap — simple recursive slice-and-dice layout with lazy drill-down.
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
  if (node.path === null) return "var(--other-color)"; // aggregated "อื่นๆ" bucket
  return node.is_dir ? "var(--accent)" : "var(--file-color)";
}

function showTreemapRoot() {
  const nodes = state.items.map((it) => ({
    label: it.label, size: it.size, risk: it.risk, note: it.note,
    path: it.path, is_dir: true,
  }));
  state.crumbs = [{ label: "ภาพรวม", nodes }];
  renderBreadcrumb();
  paintTreemap(nodes);
}

async function drillInto(node) {
  if (!node.path || !node.is_dir) {
    toast(`${node.label || node.name} — ${humanReadable(node.size)}`, "info", 2200);
    return;
  }
  const children = await window.pywebview.api.get_children(node.path);
  if (children.length === 0) {
    toast("ไม่มีไฟล์ย่อยให้เจาะลึกต่อ", "info", 2000);
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

async function showDiskMap() {
  const btn = $("btnDiskMap");
  btn.disabled = true;
  $("treemap").innerHTML = `<div class="empty-state">กำลังวัดขนาดโฟลเดอร์ในไดรฟ์ C: (อาจใช้เวลา 1-2 นาที)...</div>`;
  try {
    const children = await api.get_children("C:\\");
    const nodes = children.map((c) => ({ label: c.name, size: c.size, risk: null, note: "", path: c.path, is_dir: c.is_dir }));
    state.crumbs = [...state.crumbs.slice(0, 1), { label: "C:", nodes }];
    renderBreadcrumb();
    paintTreemap(nodes);
  } finally {
    btn.disabled = false;
  }
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
      sep.textContent = "›";
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
    container.innerHTML = `<div class="empty-state">ไม่มีข้อมูลให้แสดง</div>`;
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
    block.title = `${node.label} — ${humanReadable(node.size)}${node.note ? "\n" + node.note : ""}`;
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
    toast("กรุณาเลือกรายการที่ต้องการลบก่อน", "error");
    return;
  }
  const total = selected.reduce((s, it) => s + it.size, 0);
  const risky = selected.filter((it) => it.risk === "medium" || it.risk === "high");
  let body = `จะย้ายไฟล์ ${selected.length} รายการ รวม ${humanReadable(total)} เข้า Safety Vault (กู้คืนได้ ${state.retentionDays} วัน)`;
  if (risky.length) {
    body += "\n\nควรตรวจสอบ:\n" + risky.map((it) => `• ${it.label}: ${it.note}`).join("\n");
  }
  const ok = await confirmDialog("ยืนยันการลบ", body);
  if (!ok) return;

  $("btnCleanSelected").disabled = true;
  $("btnCleanAll").disabled = true;
  $("statusText").textContent = "กำลังลบ...";

  const payload = selected.map((it) => ({ label: it.label, path: it.path, size: it.size }));
  const meter = $("cleanMeter");
  meter.classList.remove("hidden");
  const poll = setInterval(async () => {
    const p = await api.clean_progress();
    if (!p.total) return;
    const pct = Math.round((p.done / p.total) * 100);
    $("cleanMeterFill").style.width = pct + "%";
    $("statusText").textContent = `กำลังลบ... ${pct}% (${p.done}/${p.total})`;
  }, 300);
  let result;
  try {
    result = await window.pywebview.api.clean(payload);
  } finally {
    clearInterval(poll);
    meter.classList.add("hidden");
    $("cleanMeterFill").style.width = "0%";
  }

  toast(`ย้ายไปยัง Safety Vault แล้ว ปลดพื้นที่ได้ ${result.freed_human}`, "success");
  if (result.errors.length) {
    toast(`${result.errors.length} รายการทำไม่สำเร็จ (ไฟล์กำลังถูกใช้งานอยู่)`, "error");
  }
  refreshVaultCount();
  refreshHistory();
  scan();
}

// ---------------------------------------------------------------------
// Clean history
// ---------------------------------------------------------------------
async function refreshHistory() {
  const h = await api.clean_history();
  const last = h.recent[0];
  $("historyText").textContent = last
    ? `รวม ${h.stats.total_human} · ล่าสุด ${last.timestamp.slice(0, 16)}`
    : "ยังไม่เคยล้าง";
  return h;
}

async function openHistory() {
  const h = await refreshHistory();
  const list = $("historyList");
  list.innerHTML = h.recent.length ? "" : `<div class="empty-state">ยังไม่มีประวัติ</div>`;
  h.recent.forEach((r) => {
    const row = document.createElement("div");
    row.className = "vault-row";
    row.innerHTML = `<div class="vault-row-info"><div class="vault-row-label"></div><div class="vault-row-meta mono"></div></div><div class="mono">${r.size_human}</div>`;
    row.querySelector(".vault-row-label").textContent = r.scan_type === "auto" ? "Auto Clean" : "ล้างด้วยตัวเอง";
    row.querySelector(".vault-row-meta").textContent = `${r.timestamp.slice(0, 16)} · ${r.items_found} รายการ`;
    list.appendChild(row);
  });
  $("historyModal").classList.remove("hidden");
}

async function cleanWindowsOld() {
  if (!(await api.windows_old_present())) return toast("ไม่พบ Windows.old บนเครื่องนี้", "info");
  const ok = await confirmDialog("ยืนยันลบ Windows.old",
    "จะเปิด Disk Cleanup ของ Windows ให้ลบการติดตั้ง Windows ก่อนหน้า หลังลบแล้วจะย้อนกลับไปเวอร์ชันเดิมไม่ได้");
  if (!ok) return;
  const r = await api.clean_windows_old();
  toast(r.success ? "เริ่มลบแล้ว — ดูความคืบหน้าในหน้าต่าง Disk Cleanup" : "เริ่ม Disk Cleanup ไม่สำเร็จ ต้องรันแบบ Administrator",
        r.success ? "success" : "error");
}

// Run a slow Advanced-tab action with its button disabled, then toast the result.
async function runTool(btnId, call, describe, busyText) {
  const btn = $(btnId);
  btn.disabled = true;
  if (busyText) toast(busyText, "info");
  try {
    const [msg, type] = describe(await call());
    toast(msg, type);
  } catch (e) {
    toast(String(e), "error");
  } finally {
    btn.disabled = false;
  }
}

async function openStorageCleanup() {
  const r = await api.open_storage_cleanup();
  if (!r.success) toast("เปิดหน้า Storage ไม่สำเร็จ", "error");
  else if (r.windows_old) toast("เลือก \"การติดตั้ง Windows ก่อนหน้า\" ในหน้าที่เปิดขึ้นมา", "info");
  else toast("ไม่พบ Windows.old — เปิดหน้า Storage ให้ล้างไฟล์ชั่วคราวอื่นได้", "info");
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
  $("ramText").textContent = "กำลังล้าง RAM...";
  const result = await window.pywebview.api.clean_ram();
  $("btnRam").disabled = false;
  await refreshRam();
  const note = result.skipped > 0 ? ` (ข้าม ${result.skipped} โปรเซสที่ไม่มีสิทธิ์ — รัน Admin เพื่อล้างได้ครบขึ้น)` : "";
  toast(`ล้าง Working Set ของ ${result.trimmed} โปรเซส คืน RAM ได้ ${result.freed_human}${note}`, "success");
}

// ---------------------------------------------------------------------
// Recycle bin
// ---------------------------------------------------------------------
async function cleanBin() {
  const ok = await confirmDialog(
    "ยืนยันล้างถังขยะ",
    "จะลบไฟล์ทั้งหมดในถังขยะอย่างถาวร ไม่สามารถกู้คืนได้"
  );
  if (!ok) return;
  $("btnBin").disabled = true;
  const result = await window.pywebview.api.empty_recycle_bin();
  $("btnBin").disabled = false;
  if (result.success) toast("ล้างถังขยะเรียบร้อยแล้ว", "success");
  else toast("ล้างถังขยะไม่สำเร็จ ลองรันแบบ Administrator", "error");
}

// ---------------------------------------------------------------------
// Safety Vault
// ---------------------------------------------------------------------
async function refreshVaultCount() {
  const entries = await window.pywebview.api.vault_list();
  const total = entries.reduce((s, e) => s + e.size, 0);
  $("vaultText").textContent = `${entries.length} รายการ (${humanReadable(total)})`;
  return entries;
}

async function openVault() {
  const entries = await refreshVaultCount();
  const list = $("vaultList");
  list.innerHTML = "";
  if (entries.length === 0) {
    list.innerHTML = `<div class="empty-state">ยังไม่มีไฟล์ใน Vault</div>`;
  } else {
    entries.forEach((e) => {
      const row = document.createElement("div");
      row.className = "vault-row";
      row.innerHTML = `
        <div class="vault-row-info">
          <div class="vault-row-label">${e.label}</div>
          <div class="vault-row-meta">${e.size_human} • ลบเมื่อ ${e.deleted_date}</div>
        </div>
        <button class="btn btn-accent vault-restore">กู้คืน</button>
        <button class="btn btn-danger vault-purge">ลบถาวร</button>
      `;
      row.querySelector(".vault-restore").addEventListener("click", async () => {
        const r = await window.pywebview.api.vault_restore(e.id);
        if (r.success) toast(`กู้คืน ${e.label} เรียบร้อย`, "success");
        else toast("กู้คืนไม่สำเร็จ ตำแหน่งเดิมอาจมีไฟล์อยู่แล้ว", "error");
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
  $("dockerText").textContent = available ? "ล้าง build cache/image ที่ไม่ได้ใช้" : "ไม่พบ Docker บนเครื่องนี้";
}

async function cleanDocker() {
  const ok = await confirmDialog(
    "ยืนยันล้าง Docker Cache",
    "จะรัน 'docker system prune -f' เพื่อลบ container/image/network ที่ไม่ได้ใช้งานอยู่ (ปลอดภัย เป็นคำสั่งทางการของ Docker)"
  );
  if (!ok) return;
  $("btnDocker").disabled = true;
  const result = await window.pywebview.api.docker_prune();
  $("btnDocker").disabled = false;
  if (result.success) toast(`ล้าง Docker cache แล้ว ปลดพื้นที่ ${result.freed_human}`, "success");
  else toast(`ล้างไม่สำเร็จ: ${result.message}`, "error");
}

// ---------------------------------------------------------------------
// Auto Clean (hourly Scheduled Task)
// ---------------------------------------------------------------------
function formatLastRun(lastRun) {
  if (!lastRun) return "ยังไม่เคยรัน";
  const time = lastRun.ran_at.split("T")[1]?.slice(0, 5) || "";
  return `รันล่าสุด ${lastRun.ran_at_date} ${time} — ล้างได้ ${lastRun.freed_human}`;
}

async function refreshAutoCleanStatus() {
  const status = await window.pywebview.api.auto_clean_status();
  $("autoCleanToggle").checked = status.task_active;
  $("autoCleanInterval").value = String(status.interval_hours || 1);
  $("autoCleanInterval").disabled = !status.task_active;
  $("autoCleanText").textContent = status.task_active
    ? formatLastRun(status.last_run)
    : "ปิดอยู่ — ล้างเฉพาะรายการที่ปลอดภัย 100%";
  return status;
}

async function toggleAutoClean() {
  const toggle = $("autoCleanToggle");
  const wantOn = toggle.checked;
  toggle.disabled = true;
  if (wantOn) {
    const hours = Number($("autoCleanInterval").value);
    const result = await window.pywebview.api.auto_clean_enable(hours, false);
    if (result.success) toast(`เปิดล้างอัตโนมัติทุก ${hours} ชม. แล้ว (เฉพาะรายการปลอดภัย)`, "success");
    else {
      toast(result.message || "เปิดใช้งานไม่สำเร็จ", "error");
      toggle.checked = false;
    }
  } else {
    await window.pywebview.api.auto_clean_disable();
    toast("ปิดล้างอัตโนมัติแล้ว", "info");
  }
  toggle.disabled = false;
  await refreshAutoCleanStatus();
}

async function changeAutoCleanInterval() {
  if (!$("autoCleanToggle").checked) return;
  const hours = Number($("autoCleanInterval").value);
  await window.pywebview.api.auto_clean_enable(hours, false);
  toast(`ปรับเป็นล้างทุก ${hours} ชม. แล้ว`, "success");
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
// Windows Debloat (pick which apps to remove)
// ---------------------------------------------------------------------
async function openDebloat() {
  const list = $("debloatList");
  list.innerHTML = `<div class="empty-state">กำลังตรวจแอปที่ติดตั้ง...</div>`;
  $("debloatModal").classList.remove("hidden");
  const apps = await api.list_bloatware();
  list.innerHTML = apps.length ? "" : `<div class="empty-state">ไม่พบแอปขยะที่รู้จักบนเครื่องนี้</div>`;
  apps.forEach((a) => {
    const row = document.createElement("label");
    row.className = "debloat-row";
    row.innerHTML = `<input type="checkbox" value="${a.package}" ${a.checked ? "checked" : ""}><span></span>`;
    row.querySelector("span").textContent = a.name;
    list.appendChild(row);
  });
}

async function runDebloat() {
  const picked = [...document.querySelectorAll("#debloatList input:checked")].map((i) => i.value);
  if (!picked.length) return toast("ยังไม่ได้เลือกแอป", "info");
  const btn = $("btnDebloatRun");
  btn.disabled = true;
  btn.textContent = "กำลังถอน...";
  const r = await api.debloat_windows(picked, $("debloatRestorePoint").checked);
  btn.disabled = false;
  btn.textContent = "ถอนที่เลือก";
  $("debloatModal").classList.add("hidden");
  const ok = r.results.filter((x) => x.success).length;
  if (r.restore_message) toast(r.restore_message, r.restore_point ? "success" : "info");
  toast(`ถอนสำเร็จ ${ok}/${r.results.length} รายการ`, ok === r.results.length ? "success" : "error");
}

// ---------------------------------------------------------------------
// App Uninstaller
// ---------------------------------------------------------------------
async function loadApps() {
  const list = $("appList");
  list.innerHTML = `<div class="empty-state">กำลังโหลดรายการโปรแกรม...</div>`;
  const apps = await window.pywebview.api.list_apps();
  list.innerHTML = "";
  if (apps.length === 0) {
    list.innerHTML = `<div class="empty-state">ไม่พบโปรแกรมที่ติดตั้งไว้</div>`;
    return;
  }
  apps.forEach((app) => {
    const row = document.createElement("div");
    row.className = "app-row";
    row.innerHTML = `
      <div class="app-row-info">
        <div class="app-row-name">${app.name}</div>
        <div class="app-row-meta">${app.publisher}${app.version ? " • v" + app.version : ""}</div>
      </div>
      <div class="app-row-size">${app.size_human}</div>
      <button class="btn btn-danger">ถอนการติดตั้ง</button>
    `;
    row.querySelector("button").addEventListener("click", async () => {
      const ok = await confirmDialog(
        "ยืนยันการถอนการติดตั้ง",
        `จะเปิดตัวถอนการติดตั้งของ "${app.name}" — ทำตามขั้นตอนในหน้าต่างที่เปิดขึ้นมาให้จบ`
      );
      if (!ok) return;
      const result = await window.pywebview.api.uninstall_app(app.id);
      if (result.success) toast(`เปิดตัวถอนการติดตั้งของ ${app.name} แล้ว`, "info");
      else toast("เปิดตัวถอนการติดตั้งไม่สำเร็จ", "error");
    });
    list.appendChild(row);
  });
}

async function loadLeftovers() {
  const list = $("leftoverList");
  const btn = $("btnLeftovers");
  btn.disabled = true;
  list.innerHTML = `<div class="empty-state">กำลังตรวจ...</div>`;
  const found = await api.find_leftovers();
  btn.disabled = false;
  list.innerHTML = found.length ? "" : `<div class="empty-state">ไม่พบไฟล์ตกค้าง</div>`;
  found.forEach((f) => {
    const row = document.createElement("div");
    row.className = "app-row";
    row.innerHTML = `<div class="app-row-info"><div class="app-row-name"></div><div class="app-row-meta"></div></div>
      <div class="app-row-size">${f.size_human}</div><button class="btn btn-danger">ย้ายเข้า Vault</button>`;
    row.querySelector(".app-row-name").textContent = f.app;
    row.querySelector(".app-row-meta").textContent = f.path;
    row.querySelector("button").addEventListener("click", async () => {
      const r = await api.vault_leftover(f.path);
      if (r.success) { toast("ย้ายเข้า Safety Vault แล้ว", "success"); row.remove(); refreshVaultCount(); }
      else toast("ย้ายไม่สำเร็จ ไฟล์อาจถูกใช้งานอยู่", "error");
    });
    list.appendChild(row);
  });
}

// ---------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------
async function loadAppSettings() {
  const s = await api.get_settings();
  state.retentionDays = s.vault_retention_days;
  return s;
}

async function openSettings() {
  const s = await loadAppSettings();
  $("setCloseToTray").checked = s.close_to_tray;
  $("setRetention").value = s.vault_retention_days;
  $("setJunkGb").value = s.junk_notify_gb;
  $("settingsModal").classList.remove("hidden");
}

async function saveAppSettings() {
  const s = await api.save_settings({
    close_to_tray: $("setCloseToTray").checked,
    vault_retention_days: Number($("setRetention").value) || 14,
    junk_notify_gb: Number($("setJunkGb").value) || 0,
  });
  state.retentionDays = s.vault_retention_days;
  $("settingsModal").classList.add("hidden");
  toast("บันทึกการตั้งค่าแล้ว", "success");
}

// ---------------------------------------------------------------------
// Startup Manager
// ---------------------------------------------------------------------
const STATUS_LABEL = { enabled: "เปิดใช้งาน", disabled: "ปิดอยู่", delayed: "หน่วงเวลา 2 นาที" };

async function loadStartup() {
  const list = $("startupList");
  list.innerHTML = `<div class="empty-state">กำลังโหลด...</div>`;
  const items = await window.pywebview.api.list_startup();
  list.innerHTML = "";
  if (items.length === 0) {
    list.innerHTML = `<div class="empty-state">ไม่พบโปรแกรมที่เปิดพร้อม Windows</div>`;
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
      disableBtn.textContent = "ปิด";
      disableBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.disable_startup(it.id);
        if (r.success) { toast(`ปิด ${it.name} แล้ว`, "success"); loadStartup(); }
        else toast(r.message || "ปิดไม่สำเร็จ", "error");
      });
      actions.appendChild(disableBtn);

      if (it.source === "registry") {
        const delayBtn = document.createElement("button");
        delayBtn.className = "btn btn-accent";
        delayBtn.textContent = "หน่วงเวลา";
        delayBtn.addEventListener("click", async () => {
          const r = await window.pywebview.api.delay_startup(it.id);
          if (r.success) { toast(`หน่วงเวลาเปิด ${it.name} เป็น 2 นาทีหลังล็อกอินแล้ว`, "success"); loadStartup(); }
          else toast(r.message || "หน่วงเวลาไม่สำเร็จ", "error");
        });
        actions.appendChild(delayBtn);
      }
    } else if (it.status === "disabled") {
      const enableBtn = document.createElement("button");
      enableBtn.className = "btn btn-accent";
      enableBtn.textContent = "เปิดใช้";
      enableBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.enable_startup(it.id);
        if (r.success) { toast(`เปิดใช้ ${it.name} แล้ว`, "success"); loadStartup(); }
        else toast(r.message || "เปิดใช้ไม่สำเร็จ", "error");
      });
      actions.appendChild(enableBtn);
    } else if (it.status === "delayed") {
      const cancelBtn = document.createElement("button");
      cancelBtn.className = "btn btn-ghost";
      cancelBtn.textContent = "ยกเลิกหน่วง";
      cancelBtn.addEventListener("click", async () => {
        const r = await window.pywebview.api.undo_delay_startup(it.name);
        if (r.success) { toast(`ยกเลิกการหน่วงเวลาของ ${it.name} แล้ว`, "success"); loadStartup(); }
        else toast("ยกเลิกไม่สำเร็จ", "error");
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
  list.innerHTML = `<div class="empty-state">กำลังโหลดรายการโปรแกรม...</div>`;
  const processes = await window.pywebview.api.list_freezable_processes();
  gameModeState.processes = processes;
  list.innerHTML = "";
  if (processes.length === 0) {
    list.innerHTML = `<div class="empty-state">ไม่พบโปรแกรมพื้นหลังที่แช่แข็งได้</div>`;
    return;
  }
  processes.forEach((p) => {
    const row = document.createElement("div");
    row.className = "item-card";
    row.innerHTML = `
      <div class="item-check ${gameModeState.checked.has(p.name) ? "checked" : ""}"></div>
      <div class="item-icon">${svgIcon("cpu")}</div>
      <div class="item-text">
        <div class="item-label">${p.name}</div>
        <div class="item-note">${p.pids.length} โปรเซส</div>
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
  $("gameModeStatus").textContent = active ? "กำลังทำงาน" : "ปิดอยู่";
  const btn = $("btnGameModeToggle");
  btn.textContent = active ? "ปิด Game Mode" : "เปิด Game Mode";
  btn.className = active ? "btn btn-danger" : "btn btn-accent";
}

async function toggleGameMode() {
  const status = await window.pywebview.api.game_mode_status();
  if (status.active) {
    const result = await window.pywebview.api.disable_game_mode();
    toast(`คืนค่าโปรแกรมที่แช่แข็งไว้แล้ว ${result.resumed}/${result.total} รายการ`, "success");
  } else {
    if (gameModeState.checked.size === 0) {
      toast("กรุณาเลือกโปรแกรมที่ต้องการแช่แข็งก่อน", "error");
      return;
    }
    const names = Array.from(gameModeState.checked);
    const ok = await confirmDialog(
      "ยืนยันเปิด Game Mode",
      `จะแช่แข็ง ${names.length} โปรแกรม: ${names.join(", ")}\nโปรแกรมเหล่านี้จะค้าง (ไม่ตอบสนอง) จนกว่าจะปิด Game Mode`
    );
    if (!ok) return;
    const result = await window.pywebview.api.enable_game_mode(names);
    toast(`แช่แข็งแล้ว ${result.frozen} โปรเซส`, "success");
  }
  loadGameMode();
}

// ---------------------------------------------------------------------
// Privacy / Sensitive Data Scanner
// ---------------------------------------------------------------------
const CATEGORY_LABEL = { thai_id: "เลขบัตรประชาชน", credit_card: "เลขบัตรเครดิต", password: "รหัสผ่านที่เข้ารหัสไม่ได้" };

async function pickFolderAndScan() {
  const folder = await window.pywebview.api.pick_folder();
  if (!folder) return;
  $("privacyFolderText").textContent = `กำลังสแกน: ${folder}`;
  const list = $("sensitiveList");
  list.innerHTML = `<div class="empty-state">กำลังสแกน... (เฉพาะไฟล์ข้อความ เช่น .txt .csv .json .log)</div>`;

  const findings = await window.pywebview.api.scan_sensitive_data(folder);
  $("privacyFolderText").textContent = `สแกนแล้ว: ${folder} — พบ ${findings.length} จุดที่น่าสงสัย`;
  list.innerHTML = "";
  if (findings.length === 0) {
    list.innerHTML = `<div class="empty-state">ไม่พบข้อมูลอ่อนไหวที่ตรงรูปแบบที่ตรวจสอบได้</div>`;
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
        <div class="app-row-meta">พบ: ${categories.join(", ")} (${items.length} จุด) — ตัวอย่าง: ${items[0].snippet}</div>
      </div>
      <button class="btn btn-ghost btn-vault-file">ย้ายเข้า Vault</button>
      <button class="btn btn-danger btn-shred-file">ลบถาวร (Shred)</button>
    `;
    row.querySelector(".btn-vault-file").addEventListener("click", async () => {
      const r = await window.pywebview.api.vault_file(path, "ไฟล์ข้อมูลอ่อนไหว");
      if (r.success) { toast("ย้ายเข้า Safety Vault แล้ว", "success"); row.remove(); }
    });
    row.querySelector(".btn-shred-file").addEventListener("click", async () => {
      const ok = await confirmDialog("ยืนยันลบถาวร", `จะเขียนทับและลบ "${path}" อย่างถาวร กู้คืนไม่ได้`);
      if (!ok) return;
      const r = await window.pywebview.api.shred_file(path);
      if (r.success) { toast("ลบไฟล์อย่างถาวรแล้ว", "success"); row.remove(); }
      else toast("ลบไม่สำเร็จ ไฟล์อาจถูกใช้งานอยู่", "error");
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
  list.innerHTML = `<div class="empty-state">กำลังโหลดรายการไดรเวอร์...</div>`;
  const drivers = await window.pywebview.api.list_drivers();
  list.innerHTML = "";
  drivers.forEach((d) => {
    const years = d.age_days !== null ? (d.age_days / 365).toFixed(1) : "?";
    const row = document.createElement("div");
    row.className = "startup-row";
    row.innerHTML = `
      <div class="startup-row-info">
        <div class="startup-row-name">${d.name}</div>
        <div class="startup-row-meta">${d.manufacturer} • v${d.version || "ไม่ทราบ"} • ติดตั้งเมื่อ ${d.date}</div>
      </div>
      <span class="status-pill ${ageClass(d.age_days)}">${d.age_days !== null ? years + " ปี" : "ไม่ทราบอายุ"}</span>
    `;
    list.appendChild(row);
  });
}

async function checkDriverUpdates() {
  $("btnCheckDrivers").disabled = true;
  $("driverUpdateText").textContent = "กำลังตรวจสอบกับ Windows Update... (อาจใช้เวลาสักครู่)";
  const result = await window.pywebview.api.check_driver_updates();
  $("btnCheckDrivers").disabled = false;

  if (!result.success) {
    $("driverUpdateText").textContent = "ตรวจสอบไม่สำเร็จ — ตรวจสอบว่า Windows Update service เปิดอยู่และเชื่อมต่ออินเทอร์เน็ต";
    toast(result.message || "ตรวจสอบไม่สำเร็จ", "error");
    return;
  }

  if (result.updates.length === 0) {
    $("driverUpdateText").textContent = "ไม่มีอัปเดตไดรเวอร์ที่รอติดตั้งจาก Windows Update";
    $("driverUpdatesPanel").style.display = "none";
    return;
  }

  $("driverUpdateText").textContent = `พบอัปเดต ${result.updates.length} รายการจาก Windows Update`;
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
function savedLang() {
  try { return localStorage.getItem("lang") || "th"; } catch { return "th"; }
}

function toggleLang() {
  const next = i18n.lang === "en" ? "th" : "en";
  try { localStorage.setItem("lang", next); } catch {}
  i18n.apply(next);
}

function init() {
  i18n.watch();
  i18n.apply(savedLang());
  $("btnLang").addEventListener("click", toggleLang);
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
  $("btnDebloat").addEventListener("click", openDebloat);
  $("btnHistory").addEventListener("click", openHistory);
  $("btnCloseHistory").addEventListener("click", () => $("historyModal").classList.add("hidden"));
  $("btnStorageCleanup").addEventListener("click", openStorageCleanup);
  $("btnWindowsOld").addEventListener("click", cleanWindowsOld);
  $("btnTelemetry").addEventListener("click", () => runTool("btnTelemetry", () => api.disable_telemetry(),
    (res) => res.every((r) => r.success) ? ["ปิด Telemetry สำเร็จ", "success"] : ["บางรายการล้มเหลว (ต้องรันแบบ Administrator)", "error"]));
  $("btnRegistry").addEventListener("click", () => runTool("btnRegistry", () => api.clean_registry(),
    (res) => [res.message, res.success === false ? "error" : "success"]));
  $("btnDuplicates").addEventListener("click", () => runTool("btnDuplicates", () => api.find_duplicate_files("C:/"),
    (res) => [`พบไฟล์ซ้ำ ${res.total_groups} กลุ่ม`, "info"], "กำลังค้นหาไฟล์ซ้ำใน C: (อาจใช้เวลานาน)..."));
  $("btnNetFlush").addEventListener("click", () => runTool("btnNetFlush", () => api.network_flush(),
    (res) => [`ล้างเครือข่ายสำเร็จ ${res.filter((r) => r.success).length}/${res.length} รายการ (Winsock ต้องรีสตาร์ทเครื่อง)`, "success"]));
  $("btnWinget").addEventListener("click", () => runTool("btnWinget", () => api.update_software_winget(),
    () => ["อัปเดตซอฟต์แวร์เสร็จสิ้น", "success"]));
  $("btnDiskMap").addEventListener("click", showDiskMap);
  $("btnLeftovers").addEventListener("click", loadLeftovers);
  $("btnSettings").addEventListener("click", openSettings);
  $("btnSettingsSave").addEventListener("click", saveAppSettings);
  const closeSettings = () => $("settingsModal").classList.add("hidden");
  $("btnSettingsCancel").addEventListener("click", closeSettings);
  $("btnCloseSettings").addEventListener("click", closeSettings);
  $("btnDebloatRun").addEventListener("click", runDebloat);
  $("btnDebloatCancel").addEventListener("click", () => $("debloatModal").classList.add("hidden"));
  $("btnCloseDebloat").addEventListener("click", () => $("debloatModal").classList.add("hidden"));
  $("btnUpdateNow").addEventListener("click", startUpdate);
  $("btnUpdateLater").addEventListener("click", () => $("updateBanner").classList.add("hidden"));
  $("btnCheckUpdate").addEventListener("click", () => checkForUpdates(true));
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
  refreshHistory();
  loadAppSettings();
  checkForUpdates();
  state.ramTimer = setInterval(refreshRam, 5000);
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}
