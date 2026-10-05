; Inno Setup script for PC Cleaner — builds a one-click Windows installer
; that puts a signed-looking uninstall entry in "Apps & Features", a Start
; Menu shortcut, and an optional Desktop shortcut.

#define MyAppName "PC Cleaner"
#define MyAppVersion "1.1.0"
#define MyAppExeName "PCCleaner.exe"

[Setup]
AppId={{B7C2E4A0-6C3E-4B1F-9C2A-3F5D8E1A9C40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=PCCleaner-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
WizardStyle=modern

[Languages]
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "สร้างไอคอนบนหน้าจอ (Desktop)"; GroupDescription: "ทางลัด:"

[Files]
Source: "dist\PCCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\ถอนการติดตั้ง {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "เปิด {#MyAppName} ทันที"; Flags: nowait postinstall skipifsilent runascurrentuser
