"""Headless UI smoke test: loads web/index.html with a stubbed pywebview
bridge, clicks through every tab and modal, and checks that nothing throws
and that English mode leaves no Thai text on screen.

Skipped when Playwright isn't installed (the release build doesn't need it;
CI installs it in tests.yml).
"""

import os
import pathlib

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

INDEX = pathlib.Path(__file__).resolve().parent.parent / "web" / "index.html"

STUB = r"""
const canned = {
  scan: [{label: "Temp ผู้ใช้ (%TEMP%)", path: "C:\\t", size: 5e8, risk: "safe",
          note: "ปลอดภัย — รายงานข้อผิดพลาดเก่าที่ไม่จำเป็นแล้ว"}],
  ram_status: {used: 4e9, total: 16e9, percent: 25},
  vault_list: [],
  docker_available: false,
  auto_clean_status: {task_active: false, interval_hours: 1},
  clean_history: {recent: [{scan_type: "auto", timestamp: "2026-10-18T10:00", items_found: 3, size_human: "1 GB"}],
                  stats: {total_human: "1 GB"}},
  get_settings: {close_to_tray: true, vault_retention_days: 14, junk_notify_gb: 1},
  save_settings: {close_to_tray: false, vault_retention_days: 30, junk_notify_gb: 2},
  check_for_updates: {available: true, current: "1.3.0", version: "v9.9.9", release_notes: "Fixed things", can_install: true},
  list_apps: [{id: "a", name: "Foo", publisher: "ไม่ทราบผู้พัฒนา", version: "1", size_human: "1 MB"}],
  list_startup: [{id: "x", name: "Bar", source: "registry", status: "enabled"}],
  game_mode_status: {active: false},
  list_freezable_processes: [{name: "p.exe", pids: [1], memory_human: "1 MB"}],
  list_drivers: [{name: "D", manufacturer: "M", version: "1", date: "2020-01-01", age_days: 900}],
  find_leftovers: [{app: "Foo", path: "C:\\x", size_human: "1 MB"}],
  list_bloatware: [{package: "a", name: "A", checked: true}],
  get_children: [{name: "Windows", path: "C:\\Windows", size: 1e10, is_dir: true}],
  windows_old_present: false,
};
window.__calls = [];
window.pywebview = {api: new Proxy({}, {get: (_, k) => (...args) => {
  window.__calls.push([k, args]);
  return Promise.resolve(k in canned ? JSON.parse(JSON.stringify(canned[k])) : {});
}})};
"""

THAI = "/[\\u0E00-\\u0E7F]/"


@pytest.fixture
def page():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1100, "height": 900})
        pg.add_init_script(STUB)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(INDEX.as_uri())
        pg.wait_for_selector(".item-card")
        yield pg
        assert errors == []
        browser.close()


def thai_lines(pg):
    return pg.evaluate(f"document.body.innerText.split('\\n').filter(l => {THAI}.test(l))")


def test_every_tab_and_modal_opens(page):
    for tab in ["uninstall", "startup", "gamemode", "privacy", "drivers", "advanced", "clean"]:
        page.click(f'.tab-btn[data-tab="{tab}"]')
        assert page.is_visible(f"#tab-{tab}")
    page.click("#btnSettings")
    assert page.is_visible("#settingsModal")
    page.click("#btnSettingsCancel")
    page.click("#btnHistory")
    assert page.is_visible("#historyModal")
    page.click("#btnCloseHistory")
    assert page.is_visible("#updateNotesWrap")


def test_settings_save_sends_numbers(page):
    page.click("#btnSettings")
    page.fill("#setRetention", "30")
    page.fill("#setJunkGb", "2")
    page.uncheck("#setCloseToTray")
    page.click("#btnSettingsSave")
    page.wait_for_function("window.__calls.some(c => c[0] === 'save_settings')")
    sent = page.evaluate("window.__calls.find(c => c[0] === 'save_settings')[1][0]")
    assert sent == {"close_to_tray": False, "vault_retention_days": 30, "junk_notify_gb": 2}


def test_english_mode_leaves_no_thai(page):
    page.click("#btnLang")
    leftovers = []
    page.click("#btnDiskMap")
    page.wait_for_selector(".treemap-block")
    leftovers += thai_lines(page)
    for tab in ["uninstall", "startup", "gamemode", "privacy", "drivers", "advanced"]:
        page.click(f'.tab-btn[data-tab="{tab}"]')
        if tab == "uninstall":
            page.click("#btnLeftovers")
        page.wait_for_timeout(150)
        leftovers += thai_lines(page)
    for btn, close in [("#btnSettings", "#btnSettingsCancel"), ("#btnDebloat", "#btnDebloatCancel")]:
        page.click(btn)
        page.wait_for_timeout(150)
        leftovers += thai_lines(page)
        page.click(close)
    assert leftovers == []
