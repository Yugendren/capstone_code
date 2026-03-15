; PressureMat Inno Setup Script
; Produces PressureMatSetup.exe from PyInstaller dist/PressureMat/ output

[Setup]
AppName=PressureMat
AppVersion=1.0.0
AppPublisher=Capstone Team
DefaultDirName={autopf}\PressureMat
DefaultGroupName=PressureMat
OutputBaseFilename=PressureMatSetup
Compression=lzma2
SolidCompression=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\PressureMat.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; Main application (PyInstaller onedir output)
Source: "dist\PressureMat\*"; DestDir: "{app}"; Flags: recursesubdirs

; WebView2 bootstrapper (optional — runs if WebView2 is not installed)
; Download from https://developer.microsoft.com/en-us/microsoft-edge/webview2/
; and place as webview2setup.exe next to this .iss file
Source: "webview2setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsWebView2Installed

[Icons]
Name: "{group}\PressureMat"; Filename: "{app}\PressureMat.exe"
Name: "{commondesktop}\PressureMat"; Filename: "{app}\PressureMat.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"

[Run]
; Install WebView2 if missing
Filename: "{tmp}\webview2setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Edge WebView2 runtime..."; Check: not IsWebView2Installed; Flags: waituntilterminated
; Launch app after install
Filename: "{app}\PressureMat.exe"; Description: "Launch PressureMat"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2Installed: Boolean;
var
  RegValue: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEF-10A5538025B6}', 'pv', RegValue)
         or RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BEF-10A5538025B6}', 'pv', RegValue);
end;
