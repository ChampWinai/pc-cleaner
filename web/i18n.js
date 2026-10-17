"use strict";

// Thai is the source language: every Thai string in the page is its own key.
// English replaces whole text nodes / attributes that exactly match a key, and a
// MutationObserver applies it to text the app inserts later (status lines,
// empty states). Strings built with numbers inside stay Thai.
const I18N_EN = {
  "กำลังสแกน...": "Scanning...",
  "สแกนเสร็จ": "Scan complete",
  "ตรวจอัปเดต": "Check for updates",
  "มีเวอร์ชันใหม่": "New version available",
  "พร้อมอัปเดตอัตโนมัติ — โปรแกรมจะรีสตาร์ทเอง": "Ready to update — the app restarts itself",
  "ภายหลัง": "Later",
  "อัปเดตเลย": "Update now",
  "เมนูหลัก": "Main menu",
  "ล้างไฟล์ขยะ": "Junk Cleaner",
  "ถอนการติดตั้ง": "Uninstall",
  "โปรแกรมเริ่มต้น": "Startup Apps",
  "ความเป็นส่วนตัว": "Privacy",
  "ฮาร์ดแวร์ & ไดรเวอร์": "Hardware & Drivers",
  "เครื่องมือขั้นสูง": "Advanced Tools",
  "พื้นที่ที่จะปลดล็อกได้": "Space to free",
  "พบ 0 รายการ": "0 items found",
  "เครื่องสะอาดอยู่แล้ว": "Already clean",
  "แผนภูมิพื้นที่ (Treemap) — คลิกเพื่อเจาะลึก": "Space map (Treemap) — click to drill down",
  "ภาพรวม": "Overview",
  "ปลอดภัย": "Safe",
  "ควรทราบ": "Note",
  "ควรตรวจสอบ": "Review",
  "โฟลเดอร์": "Folder",
  "ไฟล์": "File",
  "หน่วยความจำ (RAM)": "Memory (RAM)",
  "กำลังตรวจสอบ...": "Checking...",
  "ล้าง RAM": "Free RAM",
  "ถังขยะ (Recycle Bin)": "Recycle Bin",
  "ลบไฟล์ที่ทิ้งไปแล้วอย่างถาวร": "Permanently delete discarded files",
  "ล้างถังขยะ": "Empty bin",
  "0 รายการ": "0 items",
  "เปิดดู": "Open",
  "ล้าง Cache": "Clean cache",
  "ไม่พบ Docker บนเครื่องนี้": "Docker not found on this PC",
  "ล้าง build cache/image ที่ไม่ได้ใช้": "Remove unused build cache/images",
  "ประวัติการล้าง": "Clean history",
  "ยังไม่เคยล้าง": "Never cleaned",
  "ยังไม่มีประวัติ": "No history yet",
  "ดู": "View",
  "ล้างอัตโนมัติ": "Auto Clean",
  "ปิดอยู่": "Off",
  "ยังไม่เคยรัน": "Never run",
  "ทุก 1 ชม.": "Every 1 h",
  "ทุก 3 ชม.": "Every 3 h",
  "ทุก 6 ชม.": "Every 6 h",
  "ทุก 12 ชม.": "Every 12 h",
  "ทุก 24 ชม.": "Every 24 h",
  "โหมดล้างเชิงลึก (Windows Update Cache, Delivery Optimization, Firefox Cache ฯลฯ)":
    "Deep clean mode (Windows Update cache, Delivery Optimization, Firefox cache, etc.)",
  "รายการไฟล์ขยะที่พบ": "Junk found",
  "โปรแกรมที่ติดตั้งไว้ (เรียงตามขนาด)": "Installed programs (by size)",
  "คลิก \"ถอนการติดตั้ง\" เพื่อเปิดตัวถอนการติดตั้งของโปรแกรมนั้นๆ โดยตรง (เหมือนใช้ Apps & Features ของ Windows)":
    "Click \"Uninstall\" to launch that program's own uninstaller (same as Windows Apps & Features)",
  "กำลังโหลดรายการโปรแกรม...": "Loading programs...",
  "โปรแกรมที่เปิดพร้อม Windows": "Programs that start with Windows",
  "ปิดโปรแกรมที่ไม่จำเป็นเพื่อบูตเร็วขึ้น หรือหน่วงเวลาเปิด 2 นาทีแทนการปิดถาวร":
    "Disable unneeded programs for faster boot, or delay them 2 minutes instead",
  "สถานะ Game Mode": "Game Mode status",
  "เลือกโปรแกรมพื้นหลังที่จะ \"แช่แข็ง\" ชั่วคราวตอนเล่นเกม/เรนเดอร์งาน แล้วกดคืนค่าเมื่อเลิกใช้":
    "Pick background programs to \"freeze\" while gaming/rendering, then restore when done",
  "เปิด Game Mode": "Enable Game Mode",
  "โปรแกรมที่กำลังทำงาน (เรียงตามหน่วยความจำ)": "Running programs (by memory)",
  "ติ๊กเลือกโปรแกรมที่ต้องการแช่แข็ง — โปรแกรมระบบสำคัญถูกซ่อนไว้เพื่อความปลอดภัย":
    "Tick programs to freeze — critical system processes are hidden for safety",
  "ตัวสแกนหาข้อมูลอ่อนไหว": "Sensitive data scanner",
  "ยังไม่ได้เลือกโฟลเดอร์": "No folder selected",
  "สแกนหาเลขบัตรประชาชน, เลขบัตรเครดิต, และรหัสผ่านที่อยู่ในไฟล์ข้อความ (heuristic ไม่ใช่ AI จริง — อาจมีทั้ง false positive/negative)":
    "Scans text files for national ID numbers, card numbers and passwords (heuristic, not AI — expect false positives/negatives)",
  "เลือกโฟลเดอร์": "Choose folder",
  "ผลการสแกน": "Scan results",
  "อัปเดตไดรเวอร์": "Driver updates",
  "ยังไม่ได้ตรวจสอบ": "Not checked yet",
  "ตรวจสอบอัปเดต": "Check updates",
  "อัปเดตที่พร้อมติดตั้ง": "Updates ready to install",
  "เปิด Windows Update เพื่อติดตั้ง": "Open Windows Update to install",
  "ไดรเวอร์ที่ติดตั้งอยู่ (เรียงจากเก่าสุด)": "Installed drivers (oldest first)",
  "ไดรเวอร์เก่ามากไม่ได้แปลว่ามีปัญหาเสมอไป — ฮาร์ดแวร์บางตัวไม่จำเป็นต้องอัปเดตบ่อย":
    "An old driver isn't necessarily a problem — some hardware rarely needs updates",
  "เลือกทั้งหมด": "Select all",
  "ยกเลิก": "Cancel",
  "สแกนใหม่": "Rescan",
  "ลบรายการที่เลือก": "Clean selected",
  "ล้างทั้งหมด": "Clean all",
  "ปิด": "Close",
  "ไฟล์เหล่านี้จะถูกลบถาวรอัตโนมัติหลัง 14 วัน — กู้คืนได้ตลอดก่อนหน้านั้น":
    "These files are permanently deleted after 14 days — restore any time before that",
  "ยังไม่มีไฟล์ใน Vault": "Vault is empty",
  "กู้คืน": "Restore",
  "ลบถาวร": "Delete forever",
  "ขนาดเป็นค่าประมาณจากตอนสแกน": "Sizes are estimates from scan time",
  "ล้างด้วยตัวเอง": "Manual clean",
  "เลือกแอปที่จะถอน — แอปที่คนใช้บ่อยไม่ได้ติ๊กไว้ การถอนแอป Store ย้อนกลับไม่ได้เสมอไป":
    "Pick apps to remove — commonly used apps start unticked. Store app removal can't always be undone",
  "กำลังตรวจแอปที่ติดตั้ง...": "Checking installed apps...",
  "ไม่พบแอปขยะที่รู้จักบนเครื่องนี้": "No known bloatware found",
  "สร้าง restore point ก่อน (แนะนำ)": "Create a restore point first (recommended)",
  "ถอนที่เลือก": "Remove selected",
  "ยืนยันการลบ": "Confirm clean",
  "ยืนยัน": "Confirm",
  "เครื่องมือขั้นสูง (Advanced Tools)": "Advanced Tools",
  "ปรับแต่ง Windows และจัดการไฟล์ซ้ำ": "Tune Windows and manage duplicate files",
  "ลบแอปขยะที่มาพร้อมกับ Windows (เช่น Xbox, Candy Crush)": "Remove apps bundled with Windows (Xbox, Candy Crush, ...)",
  "เลือกแอปที่จะถอน": "Choose apps",
  "Windows.old / ไฟล์อัปเดตเก่า": "Windows.old / old update files",
  "ใหญ่ระดับหลายสิบ GB และ Windows ล็อกไว้ — เปิด Storage Sense ของ Windows เพื่อลบอย่างปลอดภัย":
    "Tens of GB and locked by Windows — open Windows Storage Sense to remove safely",
  "เปิด Storage Sense": "Open Storage Sense",
  "บล็อก Telemetry (ความเป็นส่วนตัว)": "Block telemetry (privacy)",
  "ปิดการส่งข้อมูลการใช้งานกลับไปยัง Microsoft": "Stop sending usage data to Microsoft",
  "ปิด Telemetry": "Disable telemetry",
  "ปรับปรุง Registry": "Registry cleanup",
  "เคลียร์แคชและค่าที่ตกค้างในระบบอย่างปลอดภัย": "Safely clear leftover cache entries",
  "ปรับปรุงตอนนี้": "Clean now",
  "ค้นหาไฟล์ซ้ำ (Duplicate Finder)": "Duplicate Finder",
  "ค้นหาไฟล์ที่ซ้ำกันเพื่อประหยัดพื้นที่": "Find duplicate files to save space",
  "เริ่มค้นหา": "Start",
  "ล้างเครือข่าย (Network Flush)": "Network flush",
  "รีเซ็ต DNS และ Winsock เพื่อแก้ปัญหาเน็ตหลุด": "Reset DNS and Winsock to fix dropped connections",
  "ล้างแคชเน็ต": "Flush network",
  "อัปเดตโปรแกรม (Winget)": "Update programs (Winget)",
  "เช็คและอัปเดตโปรแกรมในเครื่องทั้งหมดรวดเดียว": "Check and update all installed programs at once",
  "อัปเดตทั้งหมด": "Update all",
  "คุณใช้เวอร์ชันล่าสุดแล้ว": "You're on the latest version",
};

// Strings the app builds with numbers in them.
const I18N_EN_PATTERNS = [
  [/^พบ (\d+) รายการ · รวม (.+) \(เลือกเพื่อล้าง\)$/, "Found $1 items · $2 total (select to clean)"],
  [/^พบ (\d+) รายการ · รวม (.+)$/, "Found $1 items · $2 total"],
  [/^รวม (.+) · ล่าสุด (.+)$/, "Total $1 · last $2"],
  [/^(\d+) รายการ$/, "$1 items"],
  [/^กำลังลบ\.\.\. (\d+)% \((.+)\)$/, "Cleaning... $1% ($2)"],
];

function toEnglish(key) {
  if (key in I18N_EN) return I18N_EN[key];
  for (const [re, out] of I18N_EN_PATTERNS) if (re.test(key)) return key.replace(re, out);
  return null;
}

const i18n = {
  lang: "th",
  _orig: new WeakMap(), // node -> original Thai text, so switching back is exact

  _translateNode(node) {
    let src = this._orig.get(node);
    // The app rewrote this node since we last saw it: its new text is the source.
    if (src === undefined || (node.nodeValue !== src && node.nodeValue !== src.replace(src.trim(), toEnglish(src.trim())))) {
      src = node.nodeValue;
      this._orig.delete(node);
    }
    const key = src.trim();
    const en = key && toEnglish(key);
    if (!en) return;
    this._orig.set(node, src);
    const want = this.lang === "en" ? src.replace(key, en) : src;
    if (node.nodeValue !== want) node.nodeValue = want;
  },

  _translateTree(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) this._translateNode(n);
    const els = root.querySelectorAll ? root.querySelectorAll("[title],[aria-label]") : [];
    els.forEach((el) => {
      for (const attr of ["title", "aria-label"]) {
        const store = `data-i18n-${attr}`;
        const src = el.getAttribute(store) || el.getAttribute(attr);
        if (!src || !(src in I18N_EN)) continue;
        el.setAttribute(store, src);
        el.setAttribute(attr, this.lang === "en" ? I18N_EN[src] : src);
      }
    });
  },

  apply(lang) {
    this.lang = lang;
    document.documentElement.lang = lang;
    this._translateTree(document.body);
    const btn = document.getElementById("btnLang");
    if (btn) btn.textContent = lang === "en" ? "TH" : "EN";
  },

  watch() {
    new MutationObserver((muts) => {
      if (this.lang !== "en") return;
      for (const m of muts) {
        if (m.type === "characterData") this._translateNode(m.target);
        m.addedNodes.forEach((n) => (n.nodeType === 3 ? this._translateNode(n) : this._translateTree(n)));
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  },
};
