; The version is passed in at build time: ISCC /DMyAppVersion=2.0.37 installer.iss
; (tools/set_version.py decides it, so the installer matches the app header and the release name).
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-unversioned"
#endif

[Setup]
; Fixed AppId: a newer installer upgrades the installed app instead of installing a second copy.
AppId={{07E7C29D-17D8-44B5-875C-F66CD55D6E3F}
AppName=Image Format Converter
AppVersion={#MyAppVersion}
AppVerName=Image Format Converter {#MyAppVersion}
AppPublisher=Usef Farahmand
AppPublisherURL=https://www.useffarahmand.com/
AppSupportURL=https://github.com/Usef-Farahmand/image-format-converter/issues
AppUpdatesURL=https://github.com/Usef-Farahmand/image-format-converter/releases
DefaultDirName={autopf}\ImageFormatConverter
DefaultGroupName=Image Format Converter
OutputDir=Output
OutputBaseFilename=ImageFormatConverter_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\ImageFormatConverter.exe
LicenseFile=LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "dist\ImageFormatConverter\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Tasks]
Name: "contextmenu"; Description: "Add ""Convert with Image Format Converter"" to the right-click menu of images"

[Icons]
Name: "{group}\Image Format Converter"; Filename: "{app}\ImageFormatConverter.exe"
Name: "{autodesktop}\Image Format Converter"; Filename: "{app}\ImageFormatConverter.exe"

[Run]
; Adds the Explorer right-click item (current user only); the app does it itself so there is one code path.
Filename: "{app}\ImageFormatConverter.exe"; Parameters: "--register-menu"; Tasks: contextmenu; Flags: runhidden
Filename: "{app}\ImageFormatConverter.exe"; Description: "Launch Image Format Converter"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\ImageFormatConverter.exe"; Parameters: "--unregister-menu"; Flags: runhidden; RunOnceId: "RemoveContextMenu"
