; Build with scripts/build-installer.ps1. All dependencies are local at compile time.
#ifndef AppVersion
  #define AppVersion "2026.10.14"
#endif
#ifndef AppId
  #define AppId "Intext.ED2D377A-87E4-48AF-89A0-A023CB8F62B9"
#endif
#ifndef AppName
  #define AppName "Intext"
#endif
#ifndef PayloadDir
  #error PayloadDir is required (PyInstaller onedir output)
#endif
#ifndef RuntimeInstaller
  #error RuntimeInstaller is required (Microsoft signed bootstrapper)
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\installer"
#endif
#ifndef OutputName
  #define OutputName "Intext-Setup-" + AppVersion
#endif
#ifndef RuntimeKey
  #define RuntimeKey "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
#endif
#ifndef SystemReserveMB
  #define SystemReserveMB 512
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Intext
AppPublisherURL=https://github.com/ACha-xwx/Intext
DefaultDirName={localappdata}\Programs\Intext
DefaultGroupName=Intext
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\resources\ui\workspace\brand\intext.ico
UninstallDisplayIcon={app}\Intext.exe
UninstallDisplayName={#AppName}
CloseApplications=yes
RestartApplications=no
SetupLogging=no

[Languages]
Name: "zhcn"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RuntimeInstaller}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy
Source: "NOTICE.md"; DestDir: "{app}\licenses\InnoSetup"; Flags: ignoreversion
Source: "INNO-LICENSE.txt"; DestDir: "{app}\licenses\InnoSetup"; Flags: ignoreversion
Source: "TRANSLATION-LICENSE.txt"; DestDir: "{app}\licenses\InnoSetup"; Flags: ignoreversion

[Icons]
Name: "{group}\Intext"; Filename: "{app}\Intext.exe"; Parameters: "--renderer web"; WorkingDir: "{app}"
Name: "{group}\卸载 Intext"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Intext"; Filename: "{app}\Intext.exe"; Parameters: "--renderer web"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Intext.exe"; Parameters: "--renderer web"; Description: "启动 Intext"; Flags: nowait postinstall skipifsilent

[Code]
function HasRuntimeVersion(Root: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, '{#RuntimeKey}', 'pv', Version) and
    (Trim(Version) <> '') and (Trim(Version) <> '0.0.0.0');
end;

function HasWebView2: Boolean;
begin
  Result := HasRuntimeVersion(HKCU32) or HasRuntimeVersion(HKLM32) or
    HasRuntimeVersion(HKCU64) or HasRuntimeVersion(HKLM64);
end;

function CheckFreeSpace(Directory: String): String;
var
  FreeMB, TotalMB: Cardinal;
begin
  Result := '';
  if not GetSpaceOnDisk(Directory, True, FreeMB, TotalMB) then
    Result := '无法检查磁盘可用空间，请检查目录权限后重试。'
  else if FreeMB < {#SystemReserveMB} then
    Result := 'Windows、临时目录或用户数据所在磁盘空间不足。请先清理至少 1 GB 空间，再重新安装。程序可安装到其他磁盘，但系统盘仍需要可用空间。';
  if Result <> '' then
    Log('Intext prerequisites: insufficient system space or inaccessible path: ' + Directory);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  DotNetRelease: Cardinal;
  ExitCode: Integer;
begin
  Result := '';
  Log('Intext prerequisites: checking system space and .NET Framework');
  Result := CheckFreeSpace(ExpandConstant('{win}'));
  if Result <> '' then Exit;
  Result := CheckFreeSpace(ExpandConstant('{localappdata}'));
  if Result <> '' then Exit;
  Result := CheckFreeSpace(ExpandConstant('{tmp}'));
  if Result <> '' then Exit;
  if not RegQueryDWordValue(HKLM32, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', DotNetRelease) or
    (DotNetRelease < 461808) then
  begin
    Result := '缺少 .NET Framework 4.7.2 或更高版本。请完成 Windows 更新后重新安装。';
    Log('Intext prerequisites: .NET Framework 4.7.2 unavailable');
    Exit;
  end;
  if HasWebView2 then
  begin
    Log('Intext prerequisites: WebView2 already installed, skipping installer');
    Exit;
  end;
  WizardForm.StatusLabel.Caption := '正在安装 Microsoft Edge WebView2，需要联网，请稍候…';
  Log('Intext prerequisites: starting Microsoft WebView2 bootstrapper');
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '',
    SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := '无法启动 WebView2 安装器，请检查安全软件、网络及磁盘空间后重试。';
    Log('Intext prerequisites: bootstrapper could not start, Windows error=' + IntToStr(ExitCode));
    Exit;
  end;
  Log('Intext prerequisites: bootstrapper exit code=' + IntToStr(ExitCode));
  if (ExitCode <> 0) and (ExitCode <> 3010) then
  begin
    Result := 'WebView2 安装失败（代码 ' + IntToStr(ExitCode) + '）。请检查网络、磁盘空间和安全软件，或从 Microsoft 官网安装 WebView2 后重试。';
    Exit;
  end;
  if not HasWebView2 then
  begin
    Result := 'WebView2 安装后仍未检测到可用运行环境。请重启 Windows，或从 Microsoft 官网安装 WebView2 后重试。';
    Log('Intext prerequisites: bootstrapper exited but Runtime is not registered');
    Exit;
  end;
  NeedsRestart := ExitCode = 3010;
  Log('Intext prerequisites: WebView2 installation verified');
end;
