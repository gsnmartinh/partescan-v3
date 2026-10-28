; Instalador de ParteScan (Inno Setup). Se compila en GitHub Actions: iscc /DVersion=v1.x.x instalador\ParteScan.iss
; Instala solo para el usuario (no pide permisos de administrador). Los datos (perfil, sesiones, registro) viven en
; %APPDATA%\ParteScan, así que actualizar o desinstalar NO los borra.
#ifndef Version
  #define Version "dev"
#endif

[Setup]
AppId={{6B1E5C0A-4D3F-4A8E-9C27-7A5B0D2F9E11}
AppName=ParteScan
AppVersion={#Version}
AppPublisher=2° Juzgado de Policía Local de Valdivia
DefaultDirName={localappdata}\Programs\ParteScan
DefaultGroupName=ParteScan
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\salida
OutputBaseFilename=ParteScan-Instalador-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\ParteScan.exe
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: checkedonce

[Files]
Source: "..\dist\ParteScan\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\ParteScan"; Filename: "{app}\ParteScan.exe"
Name: "{autodesktop}\ParteScan"; Filename: "{app}\ParteScan.exe"; Tasks: escritorio

[Run]
Filename: "{app}\ParteScan.exe"; Description: "Abrir ParteScan"; Flags: nowait postinstall skipifsilent
