"""PC Cleaner - disk cleanup utility with a modern dark-themed Tkinter GUI.

Scans common junk locations (user/Windows Temp, browser caches, etc.), shows
what was found and how large it is, and only deletes items the user has
explicitly checked and confirmed.
"""

import ctypes
import json
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

import psutil

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
BG = "#14141f"
BG_CARD = "#1d1d2c"
BG_CARD_HOVER = "#24243a"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#9179ff"
DANGER = "#ff5c7a"
DANGER_HOVER = "#ff7a93"
TEXT = "#f0f0fa"
TEXT_DIM = "#8a8aa3"
BORDER = "#2a2a3d"
FONT = "Segoe UI"

CATEGORY_ICONS = {
    "Temp": "🗑",
    "Prefetch": "⚡",
    "Cache": "🌐",
    "Report": "⚠",
    "Thumbnail": "🖼",
}


def icon_for(label):
    for key, icon in CATEGORY_ICONS.items():
        if key.lower() in label.lower():
            return icon
    return "📁"


# Impact notes shown to the user before deletion, keyed by a substring match
# against the target label. Ordered from safest to most impactful; the first
# match wins so more specific labels should stay near the top.
IMPACT_NOTES = [
    ("Windows Update Cache", "safe", "ปลอดภัย — Windows จะดาวน์โหลดใหม่อัตโนมัติเมื่อมีอัปเดตครั้งถัดไป"),
    ("Delivery Optimization", "safe", "ปลอดภัย — เป็นแค่ไฟล์อัปเดตที่แชร์ให้เครื่องอื่นในเครือข่าย"),
    ("CBS/DISM", "safe", "ปลอดภัย — เป็น log การติดตั้ง/ซ่อมระบบเก่า ไม่กระทบการทำงาน"),
    ("Crash Dumps", "safe", "ปลอดภัย — ไฟล์วิเคราะห์การแครชที่ไม่ได้ใช้งานแล้ว"),
    ("Windows Installer Patch", "medium", "ระวัง — บางโปรแกรมอาจต้องใช้ไฟล์นี้ตอน uninstall/repair"),
    ("Prefetch", "safe", "ปลอดภัย — Windows จะสร้างใหม่เองเพื่อเร่งการเปิดโปรแกรม"),
    ("Thumbnail", "safe", "ปลอดภัย — รูปตัวอย่างจะถูกสร้างใหม่เมื่อเปิดโฟลเดอร์อีกครั้ง"),
    ("Windows Error Reports", "safe", "ปลอดภัย — รายงานข้อผิดพลาดเก่าที่ไม่จำเป็นแล้ว"),
    ("Internet Cache", "low", "เว็บไซต์บางเว็บอาจโหลดช้าลงเล็กน้อยในครั้งถัดไป ไม่กระทบรหัสผ่าน/ประวัติ"),
    ("Chrome Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Edge Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Firefox Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Temp", "low", "โปรแกรมที่กำลังเปิดอยู่และใช้ไฟล์ temp ค้างไว้อาจทำงานผิดพลาดชั่วคราว"),
]


def get_impact(label):
    for key, risk, note in IMPACT_NOTES:
        if key.lower() in label.lower():
            return risk, note
    return "medium", "ไม่ทราบผลกระทบแน่ชัด ตรวจสอบก่อนลบหากไม่แน่ใจ"


RISK_COLORS = {"safe": "#4ade80", "low": "#facc15", "medium": "#ff9f5c", "high": DANGER}


# ---------------------------------------------------------------------------
# Safety Vault — quarantines deleted items for a retention window instead of
# deleting them immediately, so an accidental clean can still be undone.
# ---------------------------------------------------------------------------
VAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PCCleanerVault")
VAULT_INDEX_PATH = os.path.join(VAULT_DIR, "index.json")
VAULT_RETENTION_DAYS = 14


def _load_vault_index():
    if not os.path.isfile(VAULT_INDEX_PATH):
        return []
    try:
        with open(VAULT_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_vault_index(entries):
    os.makedirs(VAULT_DIR, exist_ok=True)
    with open(VAULT_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def move_to_vault(original_path, batch_id, label):
    """Move a file/folder into the vault, returns the new vault entry dict."""
    os.makedirs(os.path.join(VAULT_DIR, batch_id), exist_ok=True)
    size = os.path.getsize(original_path) if os.path.isfile(original_path) else dir_size(original_path)
    vault_name = f"{uuid.uuid4().hex}_{os.path.basename(original_path)}"
    vault_path = os.path.join(VAULT_DIR, batch_id, vault_name)
    shutil.move(original_path, vault_path)

    entry = {
        "id": uuid.uuid4().hex,
        "label": label,
        "original_path": original_path,
        "vault_path": vault_path,
        "size": size,
        "deleted_at": datetime.now().isoformat(),
    }
    entries = _load_vault_index()
    entries.append(entry)
    _save_vault_index(entries)
    return entry


def restore_from_vault(entry_id):
    entries = _load_vault_index()
    match = next((e for e in entries if e["id"] == entry_id), None)
    if not match:
        return False
    os.makedirs(os.path.dirname(match["original_path"]), exist_ok=True)
    if os.path.exists(match["original_path"]):
        return False
    shutil.move(match["vault_path"], match["original_path"])
    entries.remove(match)
    _save_vault_index(entries)
    return True


def purge_vault_entry(entry_id):
    entries = _load_vault_index()
    match = next((e for e in entries if e["id"] == entry_id), None)
    if not match:
        return
    if os.path.isdir(match["vault_path"]):
        shutil.rmtree(match["vault_path"], ignore_errors=True)
    elif os.path.isfile(match["vault_path"]):
        try:
            os.remove(match["vault_path"])
        except OSError:
            pass
    entries.remove(match)
    _save_vault_index(entries)


def purge_expired_vault_entries():
    """Permanently delete vault items older than the retention window."""
    cutoff = datetime.now() - timedelta(days=VAULT_RETENTION_DAYS)
    entries = _load_vault_index()
    still_valid = []
    for entry in entries:
        try:
            deleted_at = datetime.fromisoformat(entry["deleted_at"])
        except (KeyError, ValueError):
            still_valid.append(entry)
            continue
        if deleted_at < cutoff:
            path = entry["vault_path"]
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        else:
            still_valid.append(entry)
    _save_vault_index(still_valid)
    return still_valid


def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def get_targets(deep=False):
    """Return list of (label, path) candidate cleanup locations that exist.

    When deep=True, also include heavier/riskier locations (Windows Update
    download cache, Delivery Optimization cache, Firefox cache, old log
    files) that a "deep clean" pass should sweep in addition to the basics.
    """
    env = os.environ
    candidates = [
        ("Temp ผู้ใช้ (%TEMP%)", env.get("TEMP")),
        ("Temp ระบบ (Windows\\Temp)", os.path.join(env.get("WINDIR", r"C:\Windows"), "Temp")),
        ("Prefetch", os.path.join(env.get("WINDIR", r"C:\Windows"), "Prefetch")),
        ("Internet Cache (INetCache)",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "INetCache")),
        ("Chrome Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data",
                       "Default", "Cache")),
        ("Edge Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data",
                       "Default", "Cache")),
        ("Windows Error Reports",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "WER")),
        ("Thumbnail Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")),
    ]

    if deep:
        candidates += [
            ("Firefox Cache",
             os.path.join(env.get("LOCALAPPDATA", ""), "Mozilla", "Firefox", "Profiles")),
            ("Windows Update Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "SoftwareDistribution", "Download")),
            ("Delivery Optimization Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "ServiceProfiles", "NetworkService",
                           "AppData", "Local", "Microsoft", "Windows", "DeliveryOptimization",
                           "Cache")),
            ("CBS/DISM Logs",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "Logs", "CBS")),
            ("Windows Installer Patch Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "Installer", "$PatchCache$")),
            ("Crash Dumps",
             os.path.join(env.get("LOCALAPPDATA", ""), "CrashDumps")),
        ]

    return [(label, path) for label, path in candidates if path and os.path.isdir(path)]


def empty_recycle_bin():
    """Empty the Windows Recycle Bin for all drives. Returns True on success."""
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    # S_OK (0) or S_FALSE-ish "already empty" codes are both fine.
    return result in (0, -2147418113, 0x8000FFFF) or result == 0x80070002


# ---------------------------------------------------------------------------
# RAM cleaning
# ---------------------------------------------------------------------------
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA = 0x0100


def ram_status():
    vm = psutil.virtual_memory()
    return vm.total, vm.used, vm.available, vm.percent


def trim_process_working_sets():
    """Ask Windows to trim the working set of every reachable process.

    This doesn't reduce total commit, but it pushes each process's private
    working set back to the OS, which is what most "RAM cleaner" tools do
    under the hood. Processes we don't have permission to touch are skipped
    silently (system/protected processes require elevation).
    """
    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    trimmed = 0
    skipped = 0

    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        if pid == 0:
            continue
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid
        )
        if not handle:
            skipped += 1
            continue
        try:
            if psapi.EmptyWorkingSet(handle):
                trimmed += 1
            else:
                skipped += 1
        finally:
            kernel32.CloseHandle(handle)

    return trimmed, skipped


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class PillButton(tk.Canvas):
    """A flat, rounded-look button drawn on a canvas so it fits the dark theme."""

    def __init__(self, master, text, command=None, bg=ACCENT, hover=ACCENT_HOVER,
                 fg="#ffffff", width=140, height=36, font_size=10):
        super().__init__(master, width=width, height=height, bg=BG_CARD,
                          highlightthickness=0, bd=0)
        self.command = command
        self.bg_color = bg
        self.hover_color = hover
        self.disabled_color = "#3a3a4d"
        self.enabled = True
        self.width = width
        self.height = height
        self.text = text
        self.fg = fg
        self.font_size = font_size
        self._draw(bg)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw(self, color):
        self.delete("all")
        color = color if self.enabled else self.disabled_color
        self._round_rect(1, 1, self.width - 1, self.height - 1, 10, fill=color, outline="")
        self.create_text(self.width / 2, self.height / 2, text=self.text,
                          fill=self.fg if self.enabled else TEXT_DIM,
                          font=(FONT, self.font_size, "bold"))

    def _on_enter(self, _e):
        if self.enabled:
            self._draw(self.hover_color)

    def _on_leave(self, _e):
        if self.enabled:
            self._draw(self.bg_color)

    def _on_click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self._draw(self.bg_color)


class ItemCard(tk.Frame):
    def __init__(self, master, label, path, size, on_toggle):
        super().__init__(master, bg=BG_CARD, cursor="hand2")
        self.var = tk.BooleanVar(value=False)
        self.on_toggle = on_toggle
        self.size = size
        self._build(label, path, size)
        for widget in (self, *self.winfo_children()):
            widget.bind("<Button-1>", self._toggle)
            widget.bind("<Enter>", lambda e: self.config(bg=BG_CARD_HOVER))
            widget.bind("<Leave>", lambda e: self.config(bg=BG_CARD))

    def _build(self, label, path, size):
        self.pack_propagate(False)
        self.config(height=64)
        risk, note = get_impact(label)
        self.risk = risk

        self.check_lbl = tk.Label(self, text="☐", font=(FONT, 14), fg=TEXT_DIM,
                                   bg=BG_CARD, width=2)
        self.check_lbl.pack(side="left", padx=(14, 4))

        icon_lbl = tk.Label(self, text=icon_for(label), font=(FONT, 14), bg=BG_CARD)
        icon_lbl.pack(side="left", padx=(4, 10))

        text_frame = tk.Frame(self, bg=BG_CARD)
        text_frame.pack(side="left", fill="both", expand=True, pady=8)
        name_row = tk.Frame(text_frame, bg=BG_CARD)
        name_row.pack(anchor="w", fill="x")
        tk.Label(name_row, text=label, anchor="w", font=(FONT, 10, "bold"),
                 fg=TEXT, bg=BG_CARD).pack(side="left")
        tk.Label(name_row, text="●", font=(FONT, 8), fg=RISK_COLORS.get(risk, TEXT_DIM),
                 bg=BG_CARD).pack(side="left", padx=(6, 0))
        tk.Label(text_frame, text=note, anchor="w", font=(FONT, 8),
                 fg=TEXT_DIM, bg=BG_CARD, wraplength=340, justify="left").pack(anchor="w")

        tk.Label(self, text=human_size(size), font=(FONT, 10, "bold"),
                 fg=ACCENT, bg=BG_CARD, width=10, anchor="e").pack(side="right", padx=16)

    def _toggle(self, _e=None):
        self.var.set(not self.var.get())
        self.check_lbl.config(text="☑" if self.var.get() else "☐",
                               fg=ACCENT if self.var.get() else TEXT_DIM)
        self.on_toggle()

    def set_checked(self, value):
        self.var.set(value)
        self.check_lbl.config(text="☑" if value else "☐",
                               fg=ACCENT if value else TEXT_DIM)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class CleanerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PC Cleaner")
        self.geometry("620x600")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.items = []  # list of dict: label, path, size, card
        self.deep_var = tk.BooleanVar(value=False)
        purge_expired_vault_entries()
        self._build_ui()
        self.after(200, self.scan)
        self.after(400, self.refresh_ram)

    # -- UI construction ---------------------------------------------------
    def _build_ui(self):
        self._build_header()
        self._build_tools_row()
        self._build_vault_link()
        self._build_summary()
        self._build_deep_toggle()
        self._build_list()
        self._build_footer()

    def _build_tools_row(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=20, pady=(0, 14))

        ram_card = tk.Frame(row, bg=BG_CARD, height=78)
        ram_card.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ram_card.pack_propagate(False)

        ram_left = tk.Frame(ram_card, bg=BG_CARD)
        ram_left.pack(side="left", padx=16, pady=10, fill="both", expand=True)
        tk.Label(ram_left, text="🧠 หน่วยความจำ (RAM)", font=(FONT, 9, "bold"),
                 fg=TEXT_DIM, bg=BG_CARD).pack(anchor="w")
        self.ram_var = tk.StringVar(value="กำลังตรวจสอบ...")
        tk.Label(ram_left, textvariable=self.ram_var, font=(FONT, 13, "bold"),
                 fg=TEXT, bg=BG_CARD).pack(anchor="w")
        self.ram_bar = tk.Canvas(ram_left, height=6, bg=BORDER, highlightthickness=0)
        self.ram_bar.pack(fill="x", pady=(6, 0))

        self.ram_btn = PillButton(ram_card, "ล้าง RAM", command=self.clean_ram,
                                   bg=ACCENT, hover=ACCENT_HOVER, width=110, height=36)
        self.ram_btn.pack(side="right", padx=12)

        bin_card = tk.Frame(row, bg=BG_CARD, height=78)
        bin_card.pack(side="left", fill="x", expand=True, padx=(6, 0))
        bin_card.pack_propagate(False)

        bin_left = tk.Frame(bin_card, bg=BG_CARD)
        bin_left.pack(side="left", padx=16, pady=10, fill="both", expand=True)
        tk.Label(bin_left, text="🧺 ถังขยะ (Recycle Bin)", font=(FONT, 9, "bold"),
                 fg=TEXT_DIM, bg=BG_CARD).pack(anchor="w")
        tk.Label(bin_left, text="ล้างไฟล์ที่ลบไปแล้วถาวร", font=(FONT, 9),
                 fg=TEXT_DIM, bg=BG_CARD).pack(anchor="w", pady=(2, 0))

        self.bin_btn = PillButton(bin_card, "ล้างถังขยะ", command=self.clean_recycle_bin,
                                   bg=DANGER, hover=DANGER_HOVER, width=110, height=36)
        self.bin_btn.pack(side="right", padx=12)

    def _build_vault_link(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=20, pady=(0, 10))
        self.vault_var = tk.StringVar(value="🗄 Safety Vault: 0 รายการ")
        lbl = tk.Label(row, textvariable=self.vault_var, font=(FONT, 9, "underline"),
                        fg=ACCENT, bg=BG, cursor="hand2")
        lbl.pack(side="left")
        lbl.bind("<Button-1>", lambda e: self.open_vault_window())
        tk.Label(row, text=f"  (ไฟล์ที่ลบจะถูกกักไว้ {VAULT_RETENTION_DAYS} วันก่อนลบถาวรจริง — กู้คืนได้จากที่นี่)",
                 font=(FONT, 9), fg=TEXT_DIM, bg=BG).pack(side="left")
        self.refresh_vault_count()

    def _build_deep_toggle(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=20, pady=(0, 8))
        self.deep_lbl = tk.Label(row, text="☐  โหมดล้างเชิงลึก (รวม Windows Update Cache, "
                                            "Delivery Optimization, Firefox Cache, ไฟล์ log เก่า)",
                                  font=(FONT, 9), fg=TEXT_DIM, bg=BG, cursor="hand2")
        self.deep_lbl.pack(anchor="w")
        self.deep_lbl.bind("<Button-1>", self._toggle_deep)

    def _toggle_deep(self, _e=None):
        self.deep_var.set(not self.deep_var.get())
        prefix = "☑" if self.deep_var.get() else "☐"
        text = self.deep_lbl.cget("text")
        self.deep_lbl.config(text=prefix + text[1:],
                              fg=ACCENT if self.deep_var.get() else TEXT_DIM)
        self.scan()

    def _build_header(self):
        header = tk.Frame(self, bg=BG, pady=18)
        header.pack(fill="x", padx=20)
        tk.Label(header, text="✨ PC Cleaner", font=(FONT, 20, "bold"),
                 fg=TEXT, bg=BG).pack(side="left")
        self.status_var = tk.StringVar(value="กำลังสแกน...")
        tk.Label(header, textvariable=self.status_var, font=(FONT, 10),
                 fg=TEXT_DIM, bg=BG).pack(side="right")

    def _build_summary(self):
        card = tk.Frame(self, bg=BG_CARD, height=90)
        card.pack(fill="x", padx=20, pady=(0, 14))
        card.pack_propagate(False)

        left = tk.Frame(card, bg=BG_CARD)
        left.pack(side="left", padx=20, pady=14)
        tk.Label(left, text="พื้นที่ที่จะปลดล็อก", font=(FONT, 9), fg=TEXT_DIM,
                 bg=BG_CARD).pack(anchor="w")
        self.total_var = tk.StringVar(value="0 B")
        tk.Label(left, textvariable=self.total_var, font=(FONT, 22, "bold"),
                 fg=ACCENT, bg=BG_CARD).pack(anchor="w")

        right = tk.Frame(card, bg=BG_CARD)
        right.pack(side="right", padx=20)
        self.progress_canvas = tk.Canvas(right, width=56, height=56, bg=BG_CARD,
                                          highlightthickness=0)
        self.progress_canvas.pack()
        self._draw_ring(0)

    def _draw_ring(self, fraction):
        c = self.progress_canvas
        c.delete("all")
        c.create_oval(4, 4, 52, 52, outline=BORDER, width=6)
        if fraction > 0:
            extent = -360 * fraction
            c.create_arc(4, 4, 52, 52, start=90, extent=extent,
                         outline=ACCENT, width=6, style="arc")
        c.create_text(28, 28, text=f"{int(fraction * 100)}%", fill=TEXT,
                       font=(FONT, 9, "bold"))

    def _build_list(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=20)

        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>",
                         lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw", width=580)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>",
                              lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

    def _build_footer(self):
        footer = tk.Frame(self, bg=BG, pady=16)
        footer.pack(fill="x", padx=20)

        left_btns = tk.Frame(footer, bg=BG)
        left_btns.pack(side="left")
        PillButton(left_btns, "เลือกทั้งหมด", command=self.select_all, bg=BG_CARD,
                   hover=BG_CARD_HOVER, fg=TEXT, width=110).pack(side="left", padx=(0, 8))
        PillButton(left_btns, "ยกเลิก", command=self.select_none, bg=BG_CARD,
                   hover=BG_CARD_HOVER, fg=TEXT, width=90).pack(side="left", padx=(0, 8))
        PillButton(left_btns, "⟳ สแกนใหม่", command=self.scan, bg=BG_CARD,
                   hover=BG_CARD_HOVER, fg=TEXT, width=110).pack(side="left")

        right_btns = tk.Frame(footer, bg=BG)
        right_btns.pack(side="right")
        self.clean_btn = PillButton(right_btns, "🗑 ลบรายการที่เลือก", command=self.clean_selected,
                                    bg=DANGER, hover=DANGER_HOVER, width=180)
        self.clean_btn.pack(side="left", padx=(0, 8))
        self.clean_btn.set_enabled(False)

        self.clean_all_btn = PillButton(right_btns, "🚀 ล้างทั้งหมด", command=self.clean_all,
                                        bg=ACCENT, hover=ACCENT_HOVER, width=150)
        self.clean_all_btn.pack(side="left")
        self.clean_all_btn.set_enabled(False)

    # -- Scanning ------------------------------------------------------------
    def scan(self):
        self.status_var.set("กำลังสแกน...")
        self.clean_btn.set_enabled(False)
        self.clean_all_btn.set_enabled(False)
        for widget in self.inner.winfo_children():
            widget.destroy()
        self.items = []
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        found = []
        for label, path in get_targets(deep=self.deep_var.get()):
            size = dir_size(path)
            if size > 0:
                found.append((label, path, size))
        self.after(0, self._populate, found)

    def _populate(self, found):
        if not found:
            tk.Label(self.inner, text="✅ เครื่องสะอาดอยู่แล้ว ไม่พบไฟล์ขยะ",
                     font=(FONT, 11), fg=TEXT_DIM, bg=BG).pack(pady=40)
            self.status_var.set("สแกนเสร็จ")
            return

        found.sort(key=lambda t: t[2], reverse=True)
        for label, path, size in found:
            card = ItemCard(self.inner, label, path, size, on_toggle=self.update_total)
            card.pack(fill="x", pady=3)
            self.items.append({"label": label, "path": path, "size": size, "card": card})

        self.status_var.set(f"พบ {len(found)} รายการ")
        self.clean_btn.set_enabled(True)
        self.clean_all_btn.set_enabled(True)
        self.update_total()

    # -- Selection -------------------------------------------------------
    def update_total(self):
        total = sum(it["size"] for it in self.items if it["card"].var.get())
        grand_total = sum(it["size"] for it in self.items) or 1
        self.total_var.set(human_size(total))
        self._draw_ring(total / grand_total)

    def select_all(self):
        for it in self.items:
            it["card"].set_checked(True)
        self.update_total()

    def select_none(self):
        for it in self.items:
            it["card"].set_checked(False)
        self.update_total()

    # -- Cleaning ----------------------------------------------------------
    def clean_selected(self):
        selected = [it for it in self.items if it["card"].var.get()]
        self._start_clean(selected)

    def clean_all(self):
        if not self.items:
            return
        self._start_clean(list(self.items))

    def _start_clean(self, selected):
        if not selected:
            messagebox.showinfo("ไม่มีรายการ", "กรุณาเลือกรายการที่ต้องการลบก่อน")
            return

        total = sum(it["size"] for it in selected)
        risky = [it for it in selected if get_impact(it["label"])[0] in ("medium", "high")]

        lines = [
            f"จะลบไฟล์ขยะ {len(selected)} รายการ รวม {human_size(total)}",
            "",
            f"ไฟล์จะถูกย้ายไปเก็บใน Safety Vault ก่อน {VAULT_RETENTION_DAYS} วัน "
            "(กู้คืนได้) แล้วค่อยลบถาวรอัตโนมัติ",
        ]
        if risky:
            lines.append("")
            lines.append("⚠ รายการที่ควรตรวจสอบก่อน:")
            for it in risky:
                _, note = get_impact(it["label"])
                lines.append(f"  • {it['label']}: {note}")
        lines.append("")
        lines.append("ต้องการดำเนินการต่อหรือไม่?")

        ok = messagebox.askyesno("ยืนยันการลบ", "\n".join(lines))
        if not ok:
            return

        self.clean_btn.set_enabled(False)
        self.clean_all_btn.set_enabled(False)
        self.status_var.set("กำลังลบ...")
        threading.Thread(target=self._clean_worker, args=(selected,), daemon=True).start()

    def _clean_worker(self, selected):
        errors = []
        freed = 0
        batch_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        for it in selected:
            path = it["path"]
            for entry in os.listdir(path) if os.path.isdir(path) else []:
                full = os.path.join(path, entry)
                try:
                    size_before = os.path.getsize(full) if os.path.isfile(full) else dir_size(full)
                    move_to_vault(full, batch_id, it["label"])
                    freed += size_before
                except OSError as e:
                    errors.append(f"{full}: {e}")

        self.after(0, self._clean_done, freed, errors)

    def _clean_done(self, freed, errors):
        msg = (f"ย้ายไฟล์ไปยัง Safety Vault แล้ว ปลดพื้นที่ได้ประมาณ {human_size(freed)}\n"
               f"กู้คืนได้ภายใน {VAULT_RETENTION_DAYS} วัน จากลิงก์ Safety Vault ด้านบน")
        if errors:
            msg += f"\n\n{len(errors)} รายการทำไม่สำเร็จ (ไฟล์กำลังถูกใช้งานอยู่ หรือไม่มีสิทธิ์เข้าถึง)"
        messagebox.showinfo("เสร็จสิ้น", msg)
        self.refresh_vault_count()
        self.scan()

    # -- Safety Vault ----------------------------------------------------
    def refresh_vault_count(self):
        entries = _load_vault_index()
        total = sum(e["size"] for e in entries)
        self.vault_var.set(f"🗄 Safety Vault: {len(entries)} รายการ ({human_size(total)})")

    def open_vault_window(self):
        win = tk.Toplevel(self)
        win.title("Safety Vault")
        win.geometry("560x420")
        win.configure(bg=BG)

        tk.Label(win, text="🗄 Safety Vault", font=(FONT, 14, "bold"), fg=TEXT, bg=BG)\
            .pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(win, text=f"ไฟล์เหล่านี้จะถูกลบถาวรอัตโนมัติหลัง {VAULT_RETENTION_DAYS} วัน",
                 font=(FONT, 9), fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=16, pady=(0, 10))

        list_area = tk.Frame(win, bg=BG)
        list_area.pack(fill="both", expand=True, padx=16)

        entries = _load_vault_index()
        if not entries:
            tk.Label(list_area, text="ยังไม่มีไฟล์ใน Vault", fg=TEXT_DIM, bg=BG,
                     font=(FONT, 10)).pack(pady=30)
        else:
            for entry in sorted(entries, key=lambda e: e["deleted_at"], reverse=True):
                self._build_vault_row(list_area, win, entry)

    def _build_vault_row(self, parent, win, entry):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=3)
        info = tk.Frame(row, bg=BG_CARD)
        info.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        tk.Label(info, text=entry["label"], font=(FONT, 10, "bold"), fg=TEXT,
                  bg=BG_CARD, anchor="w").pack(anchor="w")
        deleted_at = entry["deleted_at"].split("T")[0]
        tk.Label(info, text=f"{human_size(entry['size'])}  •  ลบเมื่อ {deleted_at}",
                  font=(FONT, 8), fg=TEXT_DIM, bg=BG_CARD, anchor="w").pack(anchor="w")

        def do_restore():
            if restore_from_vault(entry["id"]):
                messagebox.showinfo("กู้คืนแล้ว", f"กู้คืน {entry['label']} เรียบร้อย")
            else:
                messagebox.showwarning("กู้คืนไม่สำเร็จ", "ตำแหน่งเดิมมีไฟล์อยู่แล้ว หรือไฟล์หายไป")
            win.destroy()
            self.refresh_vault_count()
            self.open_vault_window()

        def do_purge():
            purge_vault_entry(entry["id"])
            win.destroy()
            self.refresh_vault_count()
            self.open_vault_window()

        PillButton(row, "กู้คืน", command=do_restore, bg=ACCENT, hover=ACCENT_HOVER,
                   width=80, height=30, font_size=9).pack(side="right", padx=(4, 12), pady=8)
        PillButton(row, "ลบถาวร", command=do_purge, bg=DANGER, hover=DANGER_HOVER,
                   width=80, height=30, font_size=9).pack(side="right", pady=8)

    # -- RAM -----------------------------------------------------------
    def refresh_ram(self):
        total, used, available, percent = ram_status()
        self.ram_var.set(f"{human_size(used)} / {human_size(total)}  ({percent:.0f}%)")
        self._draw_ram_bar(percent / 100)

    def _draw_ram_bar(self, fraction):
        self.ram_bar.delete("all")
        w = self.ram_bar.winfo_width() or 200
        color = DANGER if fraction > 0.85 else ACCENT
        self.ram_bar.create_rectangle(0, 0, w, 6, fill=BORDER, outline="")
        self.ram_bar.create_rectangle(0, 0, w * fraction, 6, fill=color, outline="")

    def clean_ram(self):
        self.ram_btn.set_enabled(False)
        self.ram_var.set("กำลังล้าง RAM...")
        threading.Thread(target=self._clean_ram_worker, daemon=True).start()

    def _clean_ram_worker(self):
        _, used_before, _, _ = ram_status()
        trimmed, skipped = trim_process_working_sets()
        _, used_after, _, _ = ram_status()
        freed = max(0, used_before - used_after)
        self.after(0, self._clean_ram_done, trimmed, skipped, freed)

    def _clean_ram_done(self, trimmed, skipped, freed):
        self.ram_btn.set_enabled(True)
        self.refresh_ram()
        note = "" if skipped == 0 else f"\n(ข้าม {skipped} โปรเซสที่ไม่มีสิทธิ์เข้าถึง — รันแบบ Admin เพื่อล้างได้ครบขึ้น)"
        messagebox.showinfo(
            "ล้าง RAM เสร็จสิ้น",
            f"ล้าง Working Set ของ {trimmed} โปรเซสแล้ว\nคืนหน่วยความจำได้ประมาณ {human_size(freed)}{note}",
        )

    # -- Recycle Bin -----------------------------------------------------
    def clean_recycle_bin(self):
        ok = messagebox.askyesno(
            "ยืนยันล้างถังขยะ",
            "จะลบไฟล์ทั้งหมดในถังขยะอย่างถาวร ไม่สามารถกู้คืนได้\n"
            "ต้องการดำเนินการต่อหรือไม่?",
        )
        if not ok:
            return
        self.bin_btn.set_enabled(False)
        threading.Thread(target=self._clean_bin_worker, daemon=True).start()

    def _clean_bin_worker(self):
        success = empty_recycle_bin()
        self.after(0, self._clean_bin_done, success)

    def _clean_bin_done(self, success):
        self.bin_btn.set_enabled(True)
        if success:
            messagebox.showinfo("เสร็จสิ้น", "ล้างถังขยะเรียบร้อยแล้ว")
        else:
            messagebox.showwarning("ไม่สำเร็จ", "ล้างถังขยะไม่สำเร็จ ลองรันโปรแกรมแบบ Administrator")


if __name__ == "__main__":
    app = CleanerApp()
    app.mainloop()
