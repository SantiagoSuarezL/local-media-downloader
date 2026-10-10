#define MyAppName "Local Media Downloader"
; CI passes /DMyAppVersion=<tag> so the installer tracks the release;
; building by hand keeps the fallback below.
#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Local Media Downloader"
#define MyAppURL "https://github.com/SantiagoSuarezL/local-media-downloader"
#define MyAppExeName "Local Media Downloader.exe"

[Setup]
AppId={{8F3A7C2E-1A4B-4D8E-9C6F-3A2B1C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\THIRD_PARTY_NOTICES.md
OutputDir=..\dist\installer
OutputBaseFilename=LocalMediaDownloader-{#MyAppVersion}-win-x64
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\LocalMediaDownloader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Dirs]
Name: "{userappdata}\Local Media Downloader"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
; Checked by default: non-technical users expect the double-click icon.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\Local Media Downloader"
