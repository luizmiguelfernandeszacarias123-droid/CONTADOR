; Script do Inno Setup (https://jrsoftware.org/isinfo.php) que cria o instalador
; InstalarContadorGado.exe a partir da pasta dist\ContadorGado gerada pelo PyInstaller.

[Setup]
AppName=Contador de Gado
AppVersion=1.0
AppPublisher=Contador de Gado
DefaultDirName={autopf}\ContadorGado
DefaultGroupName=Contador de Gado
OutputDir=instalador
OutputBaseFilename=InstalarContadorGado
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
; instala só para o usuário atual (não pede senha de administrador)
PrivilegesRequired=lowest
UninstallDisplayName=Contador de Gado

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\ContadorGado\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Contador de Gado"; Filename: "{app}\ContadorGado.exe"
Name: "{group}\Desinstalar Contador de Gado"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Contador de Gado"; Filename: "{app}\ContadorGado.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ContadorGado.exe"; Description: "Abrir o Contador de Gado agora"; Flags: postinstall nowait skipifsilent
