<div align="center">

# ✦ PC Cleaner

**โปรแกรมทำความสะอาดและเพิ่มประสิทธิภาพเครื่อง Windows ของคุณ**

โปรแกรม Windows แบบ native พร้อม UI ที่ทันสมัย ล้างไฟล์ขยะ จัดการโปรแกรมเริ่มต้น ปกป้องความเป็นส่วนตัว และดูแล PC ของคุณให้ลื่นไหลอยู่เสมอ — ทั้งหมดในโปรแกรมเดียว

[![Build & Release](https://img.shields.io/github/actions/workflow/status/ChampWinai/pc-cleaner/build-release.yml?label=build&style=flat-square)](../../actions/workflows/build-release.yml)
[![Latest Release](https://img.shields.io/github/v/release/ChampWinai/pc-cleaner?style=flat-square&color=blue)](../../releases/latest)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey?style=flat-square)](#-license)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](#)
[![Python](https://img.shields.io/badge/python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](#)

[ดาวน์โหลด](#-ดาวน์โหลด) · [ฟีเจอร์](#-ฟีเจอร์) · [เริ่มต้นใช้งาน](#-เริ่มต้นใช้งานพัฒนา) · [Build เป็น .exe](#-build-เป็น-exe)

</div>

---

## 📥 ดาวน์โหลด

ไปที่หน้า **[Releases](../../releases/latest)** แล้วดาวน์โหลดไฟล์ที่ต้องการ:

| ไฟล์ | เหมาะสำหรับ |
|---|---|
| 🛠 **PCCleaner-Setup.exe** | ผู้ใช้ทั่วไป — ติดตั้งแบบคลิกเดียว มี Start Menu / Desktop shortcut และถอนการติดตั้งได้ผ่าน Apps & Features |
| 📦 **PCCleaner-portable.zip** | ต้องการรันแบบพกพา ไม่ต้องติดตั้ง แตกไฟล์แล้วรัน `PCCleaner.exe` ได้ทันที |

> ต้องรันด้วยสิทธิ์ **Administrator** เพื่อให้ฟีเจอร์บางอย่าง (ล้าง Registry, จัดการ Scheduled Task, Startup items) ทำงานได้เต็มรูปแบบ

---

## ✨ ฟีเจอร์

<table>
<tr>
<td width="50%" valign="top">

### 🧹 ล้างไฟล์ขยะ
สแกนไฟล์ temp, cache, log ทั่วเครื่อง — รวมถึง shader cache ของ GPU, cache ของเครื่องมือ dev, และ cloud-sync cache ที่เครื่องมือทั่วไปมักมองข้าม พร้อม deep scan และแสดงผลแบบ treemap ให้เห็นว่าอะไรกินพื้นที่มากที่สุด

### 🗄 Vault ปลอดภัย
ไฟล์ที่ลบจะถูกย้ายเข้า **Vault** ก่อนเสมอ (ไม่ลบถาวรทันที) กู้คืนได้ภายใน 14 วัน ป้องกันการลบผิดพลาด

### ⏱ Auto Clean
ตั้งเวลาให้ล้างไฟล์ขยะอัตโนมัติทุกชั่วโมงผ่าน Windows Scheduled Task โดยไม่ต้องเปิดโปรแกรมทิ้งไว้

### 📦 ถอนการติดตั้งแอป
ดูรายชื่อโปรแกรมที่ติดตั้งพร้อมขนาดไฟล์ และถอนการติดตั้งได้จากที่เดียว

### 🚀 จัดการโปรแกรมเริ่มต้น (Startup Manager)
ปิด/เปิด/หน่วงเวลาโปรแกรมที่รันตอนเปิดเครื่อง ลดเวลาบูตโดยไม่ต้องลบการตั้งค่าถาวร

</td>
<td width="50%" valign="top">

### 🎮 Game Mode
เลือก freeze โปรเซสพื้นหลังที่ไม่จำเป็นชั่วคราวตอนเล่นเกม แล้วค่อย resume ทีหลังด้วยคลิกเดียว — ควบคุมเองทุกครั้ง ไม่ auto-detect แบบเสี่ยงบั๊ก

### 🔒 สแกนความเป็นส่วนตัว
ค้นหาไฟล์ที่มีข้อมูลอ่อนไหว (เลขบัตรประชาชน, เลขบัตรเครดิต, รหัสผ่านที่หลุด) พร้อม shred (ลบแบบเขียนทับ) หรือย้ายเข้า Vault

### 🔧 ฮาร์ดแวร์ & ไดรเวอร์
ตรวจสอบไดรเวอร์ที่ติดตั้งอยู่ เรียงจากเก่าสุด และเช็คอัปเดตผ่าน Windows Update Agent

### 💾 RAM & Recycle Bin
Trim working set ของโปรเซสเพื่อคืน RAM และล้างถังขยะ (Recycle Bin) ได้ในคลิกเดียว

### 🐳 Docker Prune
ล้าง image/container/volume ที่ไม่ใช้แล้วของ Docker (ถ้าติดตั้งไว้)

</td>
</tr>
</table>

---

## 🖥 เริ่มต้นใช้งาน (พัฒนา)

### ความต้องการของระบบ
- Windows 10/11
- Python 3.11+

### ติดตั้งและรัน

```powershell
git clone https://github.com/ChampWinai/pc-cleaner.git
cd pc-cleaner
pip install -r requirements.txt
python app_web.py
```

โปรแกรมจะเปิดเป็นหน้าต่าง native (ผ่าน [pywebview](https://pywebview.flowrl.com/)) เรนเดอร์ UI จาก `web/` (HTML/CSS/JS ล้วน ไม่มี framework)

### รัน Auto Clean แบบ headless

```powershell
python app_web.py --auto-clean --deep
```

ใช้เป็น command ที่ผูกกับ Scheduled Task — ไม่เปิดหน้าต่างใด ๆ สแกนและล้างเฉพาะเป้าหมายที่ปลอดภัยแล้วออก

### รันเทส

```powershell
pip install pytest
pytest tests/ -v
```

---

## 📦 Build เป็น .exe

โปรเจกต์นี้มี GitHub Actions workflow ([`.github/workflows/build-release.yml`](.github/workflows/build-release.yml)) ที่ build และ publish ให้อัตโนมัติ:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

เมื่อ push tag ที่ขึ้นต้นด้วย `v` ระบบจะ:
1. Build `.exe` ด้วย [PyInstaller](https://pyinstaller.org/) ตาม `PCCleaner.spec`
2. แพ็กเป็นตัวติดตั้งด้วย [Inno Setup](https://jrsoftware.org/isinfo.php) ตาม `installer.iss`
3. สร้าง **GitHub Release** พร้อมแนบทั้ง `PCCleaner-Setup.exe` และ `PCCleaner-portable.zip`

ต้องการ build ทดสอบก่อนโดยไม่ publish release ให้ไปที่แท็บ **Actions → Build and release PC Cleaner → Run workflow**

### Build มือ (local)

```powershell
pip install pyinstaller
pyinstaller PCCleaner.spec
# ผลลัพธ์อยู่ที่ dist\PCCleaner\PCCleaner.exe

# (ต้องติดตั้ง Inno Setup 6 ก่อน)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
# ผลลัพธ์อยู่ที่ installer_output\PCCleaner-Setup.exe
```

---

## 🗂 โครงสร้างโปรเจกต์

```
pc-cleaner/
├── app_web.py           # entry point — สร้างหน้าต่าง pywebview
├── api.py               # bridge ระหว่าง JS (web/) กับ backend.py
├── backend.py           # core logic ทั้งหมด (scan, clean, vault, startup ฯลฯ)
├── logging_setup.py     # rotating file logger
├── web/                 # UI (HTML/CSS/JS ล้วน)
├── tests/                # pytest test suite
├── PCCleaner.spec       # PyInstaller build config
├── installer.iss        # Inno Setup installer script
└── .github/workflows/   # CI: build + release .exe อัตโนมัติ
```

---

## 🔐 ความปลอดภัย

- ไฟล์ที่ "ลบ" จะถูกย้ายเข้า Vault ก่อนเสมอ ไม่มีการลบถาวรทันทีจากหน้า UI หลัก
- การ shred ไฟล์ (privacy scanner) เป็นการเขียนทับแบบ best-effort ก่อนลบจริง
- ไม่มีการเชื่อมต่อเครือข่ายขาเข้าหรือควบคุมเครื่องระยะไกลใด ๆ ในตัวแอป

---

## 📄 License

สงวนสิทธิ์ © ChampWinai — สำหรับใช้งานภายในองค์กร/ตามข้อตกลงที่กำหนด

