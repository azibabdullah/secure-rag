; SecureRAG installer (Inno Setup 6). Built by scripts\build_release.ps1, which passes the version:
;   ISCC.exe /DAppVersion=1.0.0 installer\SecureRAG.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId=SecureRAG
AppName=SecureRAG
AppVersion={#AppVersion}
AppVerName=SecureRAG {#AppVersion}
AppPublisher=Muhammad Abdullah Azib
AppPublisherURL=https://github.com/azibabdullah/SecureRAG
AppSupportURL=https://github.com/azibabdullah/SecureRAG/issues
AppComments=Local zero-trust RAG assistant with prompt-injection screening
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\SecureRAG
DefaultGroupName=SecureRAG
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=SecureRAG-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
DiskSpanning=no
WizardStyle=modern
SetupIconFile=..\assets\securerag.ico
; Close a running copy before files are replaced on upgrade.
CloseApplications=yes
; Documents, settings and the encrypted library live in %LOCALAPPDATA%\SecureRAG
; and are kept on uninstall, so reinstalling does not lose anything.
UninstallDisplayIcon={app}\SecureRAG.exe
UninstallDisplayName=SecureRAG {#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\SecureRAG\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\SecureRAG"; Filename: "{app}\SecureRAG.exe"
Name: "{group}\Uninstall SecureRAG"; Filename: "{uninstallexe}"
Name: "{userdesktop}\SecureRAG"; Filename: "{app}\SecureRAG.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SecureRAG.exe"; Description: "Launch SecureRAG"; Flags: nowait postinstall skipifsilent
