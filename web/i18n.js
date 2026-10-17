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
  // --- app messages ---
  "ติดตั้งอัตโนมัติไม่ได้ — กดดูในหน้า Release": "Can't auto-install — see the Release page",
  "ตรวจสอบไฟล์แล้ว กำลังติดตั้ง...": "File verified, installing...",
  "มีอะไรใหม่": "What's new",
  "เครื่องสะอาดอยู่แล้ว ไม่พบไฟล์ขยะ": "Already clean — no junk found",
  "ไม่มีไฟล์ย่อยให้เจาะลึกต่อ": "Nothing further to drill into",
  "ไม่มีข้อมูลให้แสดง": "Nothing to show",
  "กำลังวัดขนาดโฟลเดอร์ในไดรฟ์ C: (อาจใช้เวลา 1-2 นาที)...": "Measuring folders on drive C: (may take 1-2 minutes)...",
  "แผนที่ไดรฟ์ C:": "Drive C: map",
  "ดูว่าโฟลเดอร์ไหนในไดรฟ์ C: ใหญ่ที่สุด": "See which folders on drive C: are largest",
  "กรุณาเลือกรายการที่ต้องการลบก่อน": "Select items to clean first",
  "กำลังลบ...": "Cleaning...",
  "ไม่พบ Windows.old บนเครื่องนี้": "No Windows.old on this PC",
  "ยืนยันลบ Windows.old": "Remove Windows.old?",
  "จะเปิด Disk Cleanup ของ Windows ให้ลบการติดตั้ง Windows ก่อนหน้า หลังลบแล้วจะย้อนกลับไปเวอร์ชันเดิมไม่ได้":
    "Windows Disk Cleanup will remove the previous Windows installation. You won't be able to roll back afterwards",
  "เริ่มลบแล้ว — ดูความคืบหน้าในหน้าต่าง Disk Cleanup": "Started — watch progress in the Disk Cleanup window",
  "เริ่ม Disk Cleanup ไม่สำเร็จ ต้องรันแบบ Administrator": "Couldn't start Disk Cleanup — run as Administrator",
  "ใหญ่ระดับหลายสิบ GB — ลบผ่าน Disk Cleanup ของ Windows (ย้อนกลับไป Windows เวอร์ชันก่อนไม่ได้อีก)":
    "Tens of GB — removed via Windows Disk Cleanup (no rollback to the previous Windows afterwards)",
  "ลบ Windows.old": "Remove Windows.old",
  "เปิดหน้า Storage ไม่สำเร็จ": "Couldn't open Storage settings",
  "เลือก \"การติดตั้ง Windows ก่อนหน้า\" ในหน้าที่เปิดขึ้นมา": "Choose \"Previous Windows installation(s)\" on the page that opened",
  "ไม่พบ Windows.old — เปิดหน้า Storage ให้ล้างไฟล์ชั่วคราวอื่นได้": "No Windows.old — Storage settings opened for other temporary files",
  "กำลังล้าง RAM...": "Freeing RAM...",
  "ยืนยันล้างถังขยะ": "Empty Recycle Bin?",
  "จะลบไฟล์ทั้งหมดในถังขยะอย่างถาวร ไม่สามารถกู้คืนได้": "Every file in the Recycle Bin will be deleted permanently",
  "ล้างถังขยะเรียบร้อยแล้ว": "Recycle Bin emptied",
  "ล้างถังขยะไม่สำเร็จ ลองรันแบบ Administrator": "Couldn't empty the bin — try running as Administrator",
  "กู้คืนไม่สำเร็จ ตำแหน่งเดิมอาจมีไฟล์อยู่แล้ว": "Restore failed — something may already exist at the original location",
  "ยืนยันล้าง Docker Cache": "Clean Docker cache?",
  "จะรัน 'docker system prune -f' เพื่อลบ container/image/network ที่ไม่ได้ใช้งานอยู่ (ปลอดภัย เป็นคำสั่งทางการของ Docker)":
    "Runs 'docker system prune -f' to remove unused containers/images/networks (Docker's own safe command)",
  "ปิดอยู่ — ล้างเฉพาะรายการที่ปลอดภัย 100%": "Off — only ever cleans 100% safe items",
  "เปิดใช้งานไม่สำเร็จ": "Couldn't enable",
  "ปิดล้างอัตโนมัติแล้ว": "Auto Clean turned off",
  "ยังไม่ได้เลือกแอป": "No apps selected",
  "กำลังถอน...": "Removing...",
  "ไม่พบโปรแกรมที่ติดตั้งไว้": "No installed programs found",
  "ยืนยันการถอนการติดตั้ง": "Uninstall?",
  "เปิดตัวถอนการติดตั้งไม่สำเร็จ": "Couldn't launch the uninstaller",
  "ไฟล์ตกค้างหลังถอนโปรแกรม": "Leftovers after uninstall",
  "ตรวจเฉพาะโปรแกรมที่ถอนจากหน้านี้ — ย้ายเข้า Safety Vault (กู้คืนได้) ไม่แตะ Registry":
    "Only programs uninstalled from this page — moved to the Safety Vault (restorable), registry untouched",
  "ตรวจไฟล์ตกค้าง": "Find leftovers",
  "กำลังตรวจ...": "Checking...",
  "ไม่พบไฟล์ตกค้าง": "No leftovers found",
  "ย้ายเข้า Vault": "Move to Vault",
  "ย้ายเข้า Safety Vault แล้ว": "Moved to the Safety Vault",
  "ย้ายไม่สำเร็จ ไฟล์อาจถูกใช้งานอยู่": "Move failed — files may be in use",
  "ตั้งค่า": "Settings",
  "ภาษา / Language": "Language / ภาษา",
  "กดปิดหน้าต่างแล้วย่อลงถาด (tray) แทนการออก": "Closing the window minimizes to the tray instead of quitting",
  "เก็บไฟล์ใน Safety Vault ไว้ (วัน)": "Keep Safety Vault files for (days)",
  "แจ้งเตือนเมื่อมีขยะที่ต้องตรวจเองเกิน (GB, 0 = ปิด)": "Notify when junk needing review exceeds (GB, 0 = off)",
  "ความถี่ของ Auto Clean ตั้งได้ที่การ์ด \"ล้างอัตโนมัติ\" ในหน้าล้างไฟล์ขยะ": "Auto Clean frequency is set on the \"Auto Clean\" card in Junk Cleaner",
  "บันทึก": "Save",
  "บันทึกการตั้งค่าแล้ว": "Settings saved",
  "ไฟล์ใน Vault จะถูกลบถาวรอัตโนมัติเมื่อครบกำหนด — กู้คืนได้ตลอดก่อนหน้านั้น (ตั้งจำนวนวันได้ในหน้าตั้งค่า)":
    "Vault files are deleted permanently when they expire — restore any time before that (days set in Settings)",
  "เปิดใช้งาน": "Enabled",
  "หน่วงเวลา 2 นาที": "Delayed 2 min",
  "กำลังโหลด...": "Loading...",
  "ไม่พบโปรแกรมที่เปิดพร้อม Windows": "No startup programs found",
  "ปิดไม่สำเร็จ": "Couldn't disable",
  "หน่วงเวลา": "Delay",
  "หน่วงเวลาไม่สำเร็จ": "Couldn't delay",
  "เปิดใช้": "Enable",
  "เปิดใช้ไม่สำเร็จ": "Couldn't enable",
  "ยกเลิกหน่วง": "Undo delay",
  "ยกเลิกไม่สำเร็จ": "Couldn't undo",
  "ไม่พบโปรแกรมพื้นหลังที่แช่แข็งได้": "No freezable background programs",
  "กำลังทำงาน": "Active",
  "ปิด Game Mode": "Disable Game Mode",
  "กรุณาเลือกโปรแกรมที่ต้องการแช่แข็งก่อน": "Select programs to freeze first",
  "ยืนยันเปิด Game Mode": "Enable Game Mode?",
  "เลขบัตรประชาชน": "National ID",
  "เลขบัตรเครดิต": "Card number",
  "รหัสผ่านที่เข้ารหัสไม่ได้": "Plain-text password",
  "กำลังสแกน... (เฉพาะไฟล์ข้อความ เช่น .txt .csv .json .log)": "Scanning... (text files only: .txt .csv .json .log)",
  "ไม่พบข้อมูลอ่อนไหวที่ตรงรูปแบบที่ตรวจสอบได้": "No sensitive data matching known patterns",
  "ไฟล์ข้อมูลอ่อนไหว": "Sensitive data file",
  "ยืนยันลบถาวร": "Delete permanently?",
  "ลบไฟล์อย่างถาวรแล้ว": "File deleted permanently",
  "ลบไม่สำเร็จ ไฟล์อาจถูกใช้งานอยู่": "Delete failed — file may be in use",
  "ลบถาวร (Shred)": "Shred",
  "กำลังโหลดรายการไดรเวอร์...": "Loading drivers...",
  "ไม่ทราบ": "unknown",
  "ไม่ทราบอายุ": "Age unknown",
  "กำลังตรวจสอบกับ Windows Update... (อาจใช้เวลาสักครู่)": "Checking Windows Update... (may take a while)",
  "ตรวจสอบไม่สำเร็จ — ตรวจสอบว่า Windows Update service เปิดอยู่และเชื่อมต่ออินเทอร์เน็ต":
    "Check failed — make sure the Windows Update service is running and you're online",
  "ตรวจสอบไม่สำเร็จ": "Check failed",
  "ไม่มีอัปเดตไดรเวอร์ที่รอติดตั้งจาก Windows Update": "No pending driver updates from Windows Update",
  "ปิด Telemetry สำเร็จ": "Telemetry disabled",
  "บางรายการล้มเหลว (ต้องรันแบบ Administrator)": "Some steps failed (run as Administrator)",
  "กำลังค้นหาไฟล์ซ้ำใน C: (อาจใช้เวลานาน)...": "Searching C: for duplicates (may take a long time)...",
  "อัปเดตซอฟต์แวร์เสร็จสิ้น": "Software update finished",
  // --- messages from the Python side ---
  "ปลอดภัย — Windows จะดาวน์โหลดใหม่อัตโนมัติเมื่อมีอัปเดตครั้งถัดไป": "Safe — Windows re-downloads these with the next update",
  "ปลอดภัย — เป็นแค่ไฟล์อัปเดตที่แชร์ให้เครื่องอื่นในเครือข่าย": "Safe — just update files shared with other PCs on the network",
  "ปลอดภัย — เป็น log การติดตั้ง/ซ่อมระบบเก่า ไม่กระทบการทำงาน": "Safe — old setup/repair logs, no effect on the system",
  "ปลอดภัย — ไฟล์วิเคราะห์การแครชที่ไม่ได้ใช้งานแล้ว": "Safe — old crash analysis files",
  "ระวัง — บางโปรแกรมอาจต้องใช้ไฟล์นี้ตอน uninstall/repair": "Careful — some programs need these to uninstall/repair",
  "ปลอดภัย — Windows จะสร้างใหม่เองเพื่อเร่งการเปิดโปรแกรม": "Safe — Windows rebuilds these to speed up app launch",
  "ปลอดภัย — รูปตัวอย่างจะถูกสร้างใหม่เมื่อเปิดโฟลเดอร์อีกครั้ง": "Safe — thumbnails are rebuilt when folders are opened",
  "ปลอดภัย — รายงานข้อผิดพลาดเก่าที่ไม่จำเป็นแล้ว": "Safe — old error reports",
  "เว็บไซต์บางเว็บอาจโหลดช้าลงเล็กน้อยในครั้งถัดไป ไม่กระทบรหัสผ่าน/ประวัติ": "Some sites may load a bit slower next time; passwords/history untouched",
  "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน": "Sites load slower for a while; passwords and logins untouched",
  "โปรแกรมที่กำลังเปิดอยู่และใช้ไฟล์ temp ค้างไว้อาจทำงานผิดพลาดชั่วคราว": "Programs currently using temp files may misbehave briefly",
  "Visual Studio จะสร้างใหม่เองตอนเปิดครั้งถัดไป อาจช้าขึ้นเล็กน้อยครั้งแรก": "Visual Studio rebuilds this next launch; first start may be slower",
  "โปรเจกต์ .NET จะดาวน์โหลด package ใหม่ตอน build ครั้งถัดไป": ".NET projects re-download packages on the next build",
  "ระวัง — Unreal ต้องคำนวณ Derived Data ใหม่ตอนเปิดโปรเจกต์ครั้งถัดไป อาจใช้เวลานานมาก": "Careful — Unreal recomputes Derived Data next time; can take very long",
  "ระวัง — คลิปที่ตัดไว้ใน Premiere Pro/After Effects จะต้อง re-index/re-render cache ใหม่": "Careful — Premiere Pro/After Effects will re-index/re-render caches",
  "ปลอดภัย — การ์ดจอจะ compile shader ใหม่เองตอนเปิดเกม/โปรแกรมครั้งแรก อาจกระตุกสั้นๆ ครั้งเดียว": "Safe — the GPU recompiles shaders on first launch; a brief one-time stutter",
  "ไฟล์ log ของ OneDrive ปลอดภัยที่จะลบ ไม่กระทบไฟล์ที่ sync อยู่": "OneDrive logs are safe to remove; synced files untouched",
  "Dropbox เก็บไฟล์ที่ลบ/แก้ล่าสุดไว้กู้คืนชั่วคราว ลบแล้วกู้คืนผ่าน Dropbox เองไม่ได้ชั่วคราว": "Dropbox keeps recent deletes/edits here; removing it disables that local restore",
  "Google Drive จะดาวน์โหลดไฟล์ใหม่ตามต้องการเมื่อเปิดใช้งานอีกครั้ง": "Google Drive re-downloads files on demand",
  "ปลอดภัย — npm จะดาวน์โหลด package ใหม่ตอน install ครั้งถัดไป": "Safe — npm re-downloads packages on the next install",
  "ปลอดภัย — Yarn จะดาวน์โหลด package ใหม่ตอน install ครั้งถัดไป": "Safe — Yarn re-downloads packages on the next install",
  "ปลอดภัย — pip จะดาวน์โหลด package ใหม่ตอนติดตั้งครั้งถัดไป": "Safe — pip re-downloads packages on the next install",
  "Discord โหลดรูป/สติกเกอร์ช้าลงชั่วคราว ไม่กระทบการล็อกอิน": "Discord loads images/stickers slower for a while; login untouched",
  "Slack โหลดรูป/ไฟล์แนบช้าลงชั่วคราว ไม่กระทบการล็อกอิน": "Slack loads images/attachments slower for a while; login untouched",
  "เพลงที่เคยฟังจะโหลดใหม่จากอินเทอร์เน็ตอีกครั้ง ไม่กระทบเพลย์ลิสต์": "Played songs re-download; playlists untouched",
  "ปลอดภัย — VS Code จะสร้างแคชใหม่เองตอนเปิดครั้งถัดไป": "Safe — VS Code rebuilds its cache next launch",
  "ระวัง — IDE อาจ re-index โปรเจกต์ใหม่ตอนเปิดครั้งถัดไป อาจใช้เวลาสักครู่": "Careful — the IDE may re-index projects next launch",
  "ไม่ทราบผลกระทบแน่ชัด ตรวจสอบก่อนลบหากไม่แน่ใจ": "Impact unknown — check before deleting if unsure",
  "Temp ผู้ใช้ (%TEMP%)": "User Temp (%TEMP%)",
  "Temp ระบบ (Windows\\Temp)": "System Temp (Windows\\Temp)",
  "สร้าง Scheduled Task ไม่สำเร็จ — ต้องรันโปรแกรมแบบ Administrator": "Couldn't create the Scheduled Task — run as Administrator",
  "ไม่ทราบผู้พัฒนา": "Unknown publisher",
  "ต้องรันโปรแกรมแบบ Administrator เพื่อปิดรายการนี้": "Run as Administrator to disable this item",
  "ย้ายไฟล์ shortcut ไม่สำเร็จ": "Couldn't move the shortcut",
  "ไม่รองรับรายการประเภทนี้": "Unsupported item type",
  "ไม่พบข้อมูลสำรองของรายการนี้": "No backup found for this item",
  "ต้องรันโปรแกรมแบบ Administrator เพื่อเปิดรายการนี้": "Run as Administrator to enable this item",
  "ย้ายไฟล์ shortcut กลับไม่สำเร็จ": "Couldn't move the shortcut back",
  "หน่วงเวลาได้เฉพาะรายการจาก Registry Run key เท่านั้น": "Only Registry Run key items can be delayed",
  "ต้องรันโปรแกรมแบบ Administrator เพื่อหน่วงเวลารายการนี้": "Run as Administrator to delay this item",
  "สร้าง Scheduled Task ไม่สำเร็จ": "Couldn't create the Scheduled Task",
  "สร้าง restore point แล้ว": "Restore point created",
  "สร้าง restore point ไม่ได้ (System Protection อาจปิดอยู่ หรือเพิ่งสร้างไปภายใน 24 ชม.)": "Couldn't create a restore point (System Protection may be off, or one was made in the last 24 h)",
};

// Strings the app builds with numbers in them.
const I18N_EN_PATTERNS = [
  [/^พบ (\d+) รายการ · รวม (.+) \(เลือกเพื่อล้าง\)$/, "Found $1 items · $2 total (select to clean)"],
  [/^พบ (\d+) รายการ · รวม (.+)$/, "Found $1 items · $2 total"],
  [/^รวม (.+) · ล่าสุด (.+)$/, "Total $1 · last $2"],
  [/^(\d+) รายการ$/, "$1 items"],
  [/^กำลังลบ\.\.\. (\d+)% \((.+)\)$/, "Cleaning... $1% ($2)"],
  [/^กำลังดาวน์โหลด (\d+)%$/, "Downloading $1%"],
  [/^อัปเดตไม่สำเร็จ: (.*)$/, "Update failed: $1"],
  [/^กำลังสแกน\.\.\. \((.+)\)$/, "Scanning... ($1)"],
  [/^อื่นๆ \((\d+) รายการ\)$/, "Other ($1 items)"],
  [/^จะย้ายไฟล์ (\d+) รายการ รวม (.+?) เข้า Safety Vault \(กู้คืนได้ (\d+) วัน\)([\s\S]*)$/,
    (_, n, size, days, rest) => `Move ${n} items (${size}) to the Safety Vault (restorable for ${days} days)` + rest.replace("ควรตรวจสอบ:", "Review:")],
  [/^ย้ายไปยัง Safety Vault แล้ว ปลดพื้นที่ได้ (.+)$/, "Moved to the Safety Vault, freed $1"],
  [/^(\d+) รายการทำไม่สำเร็จ \(ไฟล์กำลังถูกใช้งานอยู่\)$/, "$1 items failed (files in use)"],
  [/^(\d+) รายการ \((.+)\)$/, "$1 items ($2)"],
  [/^(.+) · (\d+) รายการ$/, "$1 · $2 items"],
  [/^ล้าง Working Set ของ (\d+) โปรเซส คืน RAM ได้ (.+?)(?: \(ข้าม (\d+) โปรเซสที่ไม่มีสิทธิ์ — รัน Admin เพื่อล้างได้ครบขึ้น\))?$/,
    (_, n, freed, k) => `Trimmed ${n} processes, freed ${freed}` + (k ? ` (skipped ${k} without access — run as Admin for more)` : "")],
  [/^กู้คืน (.+) เรียบร้อย$/, "Restored $1"],
  [/^ล้าง Docker cache แล้ว ปลดพื้นที่ (.+)$/, "Docker cache cleaned, freed $1"],
  [/^ล้างไม่สำเร็จ: (.*)$/, "Clean failed: $1"],
  [/^รันล่าสุด (\S+) (\S*) — ล้างได้ (.+)$/, "Last run $1 $2 — freed $3"],
  [/^เปิดล้างอัตโนมัติทุก (\d+) ชม\. แล้ว \(เฉพาะรายการปลอดภัย\)$/, "Auto Clean on, every $1 h (safe items only)"],
  [/^ปรับเป็นล้างทุก (\d+) ชม\. แล้ว$/, "Now cleaning every $1 h"],
  [/^ถอนสำเร็จ (\d+)\/(\d+) รายการ$/, "Removed $1/$2 apps"],
  [/^จะเปิดตัวถอนการติดตั้งของ "(.+)" — ทำตามขั้นตอนในหน้าต่างที่เปิดขึ้นมาให้จบ$/, "This launches the uninstaller for \"$1\" — finish the steps in the window that opens"],
  [/^เปิดตัวถอนการติดตั้งของ (.+) แล้ว$/, "Launched the uninstaller for $1"],
  [/^หน่วงเวลาเปิด (.+) เป็น 2 นาทีหลังล็อกอินแล้ว$/, "$1 now starts 2 minutes after sign-in"],
  [/^ยกเลิกการหน่วงเวลาของ (.+) แล้ว$/, "Removed the delay for $1"],
  [/^เปิดใช้ (.+) แล้ว$/, "Enabled $1"],
  [/^ปิด (.+) แล้ว$/, "Disabled $1"],
  [/^คืนค่าโปรแกรมที่แช่แข็งไว้แล้ว (\d+)\/(\d+) รายการ$/, "Resumed $1/$2 frozen programs"],
  [/^จะแช่แข็ง (\d+) โปรแกรม: (.+)\nโปรแกรมเหล่านี้จะค้าง \(ไม่ตอบสนอง\) จนกว่าจะปิด Game Mode$/, "Freeze $1 programs: $2\nThey stay unresponsive until Game Mode is turned off"],
  [/^แช่แข็งแล้ว (\d+) โปรเซส$/, "Froze $1 processes"],
  [/^(\d+) โปรเซส$/, "$1 processes"],
  [/^กำลังสแกน: (.+)$/, "Scanning: $1"],
  [/^สแกนแล้ว: (.+) — พบ (\d+) จุดที่น่าสงสัย$/, "Scanned: $1 — $2 suspicious matches"],
  [/^พบ: (.+) \((\d+) จุด\) — ตัวอย่าง: (.*)$/, "Found: $1 ($2 matches) — e.g. $3"],
  [/^จะเขียนทับและลบ "(.+)" อย่างถาวร กู้คืนไม่ได้$/, "\"$1\" will be overwritten and deleted permanently"],
  [/^(.+) • v(.+) • ติดตั้งเมื่อ (.+)$/, "$1 • v$2 • installed $3"],
  [/^([\d.?]+) ปี$/, "$1 yrs"],
  [/^พบอัปเดต (\d+) รายการจาก Windows Update$/, "$1 updates found on Windows Update"],
  [/^(.+) • ลบเมื่อ (.+)$/, "$1 • deleted $2"],
  [/^(ไม่ทราบผู้พัฒนา) • v(.+)$/, "Unknown publisher • v$2"],
  [/^ไฟล์ตกค้าง: (.+)$/, "Leftover: $1"],
  [/^สร้าง restore point ไม่ได้: (.*)$/, "Couldn't create a restore point: $1"],
  [/^พบไฟล์ซ้ำ (\d+) กลุ่ม$/, "Found $1 duplicate groups"],
  [/^ล้างเครือข่ายสำเร็จ (\d+)\/(\d+) รายการ \(Winsock ต้องรีสตาร์ทเครื่อง\)$/, "Network flush: $1/$2 done (Winsock needs a restart)"],
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
