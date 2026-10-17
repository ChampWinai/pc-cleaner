; Inno Setup script for PC Cleaner — builds a one-click Windows installer
; that puts a signed-looking uninstall entry in "Apps & Features", a Start
; Menu shortcut, and an optional Desktop shortcut.

#define MyAppName "PC Cleaner"
#define MyAppVersion "1.1.6"
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
CloseApplications=force
RestartApplications=no

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

[Code]
// PCCleaner.exe is often still running (the window, or the hourly headless
// --auto-clean run) which makes "DeleteFile failed; code 5". Stop it first.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\schtasks.exe'), '/end /tn PCCleaner_AutoClean', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(800);
  Result := '';
end;
