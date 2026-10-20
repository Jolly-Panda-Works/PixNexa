; The version is passed in at build time: ISCC /DMyAppVersion=2.0.37 installer.iss
; (tools/set_version.py decides it, so the installer matches the app header and the release name).
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-unversioned"
#endif

[Setup]
; Fixed AppId: a newer installer upgrades the installed app instead of installing a second copy.
AppId={{07E7C29D-17D8-44B5-875C-F66CD55D6E3F}
AppName=PixNexa Desktop
AppVersion={#MyAppVersion}
AppVerName=PixNexa Desktop {#MyAppVersion}
AppPublisher=Usef Farahmand
AppPublisherURL=https://usef-farahmand.github.io/image-format-converter/
AppSupportURL=https://github.com/Usef-Farahmand/image-format-converter/issues
AppUpdatesURL=https://github.com/Usef-Farahmand/image-format-converter/releases
DefaultDirName={autopf}\PixNexa
DefaultGroupName=PixNexa Desktop
OutputDir=Output
OutputBaseFilename=PixNexa_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\PixNexa.exe
LicenseFile=LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[InstallDelete]
; Upgrading from "Image Format Converter" (same AppId): remove the old exe and its shortcuts.
Type: files; Name: "{app}\ImageFormatConverter.exe"
Type: files; Name: "{autodesktop}\Image Format Converter.lnk"
Type: files; Name: "{group}\Image Format Converter.lnk"
Type: files; Name: "{autoprograms}\Image Format Converter.lnk"
Type: filesandordirs; Name: "{autoprograms}\Image Format Converter"

[Files]
Source: "dist\PixNexa\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Tasks]
Name: "contextmenu"; Description: "Add ""Convert with PixNexa"" to the right-click menu of images"

[Icons]
Name: "{group}\PixNexa Desktop"; Filename: "{app}\PixNexa.exe"
Name: "{autodesktop}\PixNexa Desktop"; Filename: "{app}\PixNexa.exe"

[Run]
; Adds the Explorer right-click item (current user only); the app does it itself so there is one code path.
Filename: "{app}\PixNexa.exe"; Parameters: "--register-menu"; Tasks: contextmenu; Flags: runhidden
Filename: "{app}\PixNexa.exe"; Description: "Launch PixNexa Desktop"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\PixNexa.exe"; Parameters: "--unregister-menu"; Flags: runhidden; RunOnceId: "RemoveContextMenu"
