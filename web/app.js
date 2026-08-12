"use strict";

const state = {
  items: [],       // {label, path, size, risk, note, checked} — top-level scan targets
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
  $("statusText").textContent = found.length ? `พบ ${found.length} รายการ` : "สแกนเสร็จ";
  $("itemCountText").textContent = found.length ? `พบ ${found.length} รายการ` : "เครื่องสะอาดอยู่แล้ว";
  $("btnCleanAll").disabled = found.length === 0;
}

function iconFor(label) {
  const l = label.toLowerCase();
  if (l.includes("temp")) return "🗑";
  if (l.includes("prefetch")) return "⚡";
  if (l.includes("cache")) return "🌐";
  if (l.includes("report") || l.includes("dump") || l.includes("log")) return "⚠";
  if (l.includes("thumbnail")) return "🖼";
  return "📁";
}

function renderList() {
  const container = $("itemList");
  container.innerHTML = "";
  if (state.items.length === 0) {
    container.innerHTML = `<div class="empty-state">✅ เครื่องสะอาดอยู่แล้ว ไม่พบไฟล์ขยะ</div>`;
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
  let body = `จะย้ายไฟล์ ${selected.length} รายการ รวม ${humanReadable(total)} เข้า Safety Vault (กู้คืนได้ 14 วัน)`;
  if (risky.length) {
    body += "\n\n⚠ ควรตรวจสอบ:\n" + risky.map((it) => `• ${it.label}: ${it.note}`).join("\n");
  }
  const ok = await confirmDialog("ยืนยันการลบ", body);
  if (!ok) return;

  $("btnCleanSelected").disabled = true;
  $("btnCleanAll").disabled = true;
  $("statusText").textContent = "กำลังลบ...";

  const payload = selected.map((it) => ({ label: it.label, path: it.path }));
  const result = await window.pywebview.api.clean(payload);

  toast(`ย้ายไปยัง Safety Vault แล้ว ปลดพื้นที่ได้ ${result.freed_human}`, "success");
  if (result.errors.length) {
    toast(`${result.errors.length} รายการทำไม่สำเร็จ (ไฟล์กำลังถูกใช้งานอยู่)`, "error");
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
      const cmd = app.quiet_uninstall_string || app.uninstall_string;
      const result = await window.pywebview.api.uninstall_app(cmd);
      if (result.success) toast(`เปิดตัวถอนการติดตั้งของ ${app.name} แล้ว`, "info");
      else toast("เปิดตัวถอนการติดตั้งไม่สำเร็จ", "error");
    });
    list.appendChild(row);
  });
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
      <div class="item-icon">🧩</div>
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
  $("gameModeStatus").textContent = active ? "🟢 กำลังทำงาน" : "ปิดอยู่";
  const btn = $("btnGameModeToggle");
  btn.textContent = active ? "⏹ ปิด Game Mode" : "🎮 เปิด Game Mode";
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
    list.innerHTML = `<div class="empty-state">✅ ไม่พบข้อมูลอ่อนไหวที่ตรงรูปแบบที่ตรวจสอบได้</div>`;
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
    $("driverUpdateText").textContent = "✅ ไม่มีอัปเดตไดรเวอร์ที่รอติดตั้งจาก Windows Update";
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
  window.addEventListener("resize", renderTreemap);
  document.querySelectorAll(".tab-btn").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );

  scan();
  refreshRam();
  refreshVaultCount();
  initDocker();
  state.ramTimer = setInterval(refreshRam, 5000);
}

if (window.pywebview) {
  init();
} else {
  window.addEventListener("pywebviewready", init);
}
