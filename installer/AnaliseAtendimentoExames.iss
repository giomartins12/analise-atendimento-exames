#define AppName "Análise de Atendimento e Exames"
#define AppVersion "0.1.2"
#define AppExeName "AnaliseAtendimentoExames.exe"
#define SourceRoot SourcePath + ".."

[Setup]
AppId={{7E8D58C3-A6C8-45A9-83A3-22B98141523C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Giovanni Martins
DefaultDirName={localappdata}\Programs\AnaliseAtendimentoExames
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SourceRoot}\installer\output
OutputBaseFilename=AnaliseAtendimentoExames-Setup-{#AppVersion}-win64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\dist\AnaliseAtendimentoExames\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Diagnóstico - {#AppName}"; Filename: "{app}\AnaliseAtendimentoExames-Diagnostico.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
