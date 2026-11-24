; StaRbuSt 의 Windows 설치 파일을 만드는 Inno Setup 스크립트.
; build.py 가 PyInstaller 로 dist\StaRbuSt 폴더를 만든 뒤 이 파일을 iscc 로 돌린다.
; 관리자 권한 없이 사용자 폴더에 설치하고 시작 메뉴와 바탕 화면에 아이콘을 만든다.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\StaRbuSt"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif
#ifndef IconFile
  #define IconFile "icons\StaRbuSt.ico"
#endif

[Setup]
AppId={{7AF021C9-AA53-4D9A-B6F8-956B8624CBE2}
AppName=StaRbuSt
AppVersion={#AppVersion}
AppPublisher=The Society of Rocket Study
DefaultDirName={autopf}\StaRbuSt
DefaultGroupName=StaRbuSt
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=StaRbuSt-{#AppVersion}-windows-setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\StaRbuSt.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 설치창의 그림과 바탕색(앱의 시작 화면과 같은 연두). 그림은 make_installer_art.py 가 만든다
WizardImageFile=installer\wizard_large.png
WizardSmallImageFile=installer\wizard_small.png
WizardBackColor=#F3F8F1
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
#if FileExists(CompilerPath + "Languages\Korean.isl")
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StaRbuSt"; Filename: "{app}\StaRbuSt.exe"
Name: "{autodesktop}\StaRbuSt"; Filename: "{app}\StaRbuSt.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StaRbuSt.exe"; Description: "{cm:LaunchProgram,StaRbuSt}"; Flags: nowait postinstall skipifsilent
; 앱의 업데이트 버튼은 이 설치 파일을 조용히(/SILENT) 돌린다. 그때는 설치가 끝나면 앱을 다시 연다
Filename: "{app}\StaRbuSt.exe"; Flags: nowait; Check: WizardSilent

[UninstallDelete]
; 앱이 사용자 폴더에 만든 로그와 번역 결과, 창 설정
Type: filesandordirs; Name: "{localappdata}\StaRbuSt"
