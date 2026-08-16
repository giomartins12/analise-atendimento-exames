$ErrorActionPreference = "Stop"

$minimumVersion = [Version]"3.12"
$pythonCommand = $null
$pythonArguments = @()

$candidates = @(
    @{ Command = "py"; Arguments = @("-3") },
    @{ Command = "python"; Arguments = @() },
    @{ Command = "python3"; Arguments = @() }
)

foreach ($candidate in $candidates) {
    $candidateCommand = [string]$candidate.Command
    $candidateArguments = [string[]]$candidate.Arguments

    if (-not (Get-Command $candidateCommand -ErrorAction SilentlyContinue)) {
        continue
    }

    $versionText = & $candidateCommand @candidateArguments -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $versionText) {
        continue
    }

    try {
        $detectedVersion = [Version]($versionText | Select-Object -Last 1)
    }
    catch {
        continue
    }

    if ($detectedVersion -ge $minimumVersion) {
        $pythonCommand = $candidateCommand
        $pythonArguments = $candidateArguments
        Write-Host "Python $detectedVersion encontrado via '$pythonCommand $($pythonArguments -join ' ')'."
        break
    }
}

if (-not $pythonCommand) {
    throw "Python 3.12 ou superior nao foi encontrado. Instale-o em https://www.python.org/downloads/ e marque 'Add Python to PATH'."
}

$venvPython = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Criando ambiente virtual local..."
    & $pythonCommand @pythonArguments -m venv ".venv"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        throw "Nao foi possivel criar o ambiente virtual com o Python detectado."
    }
}

Write-Host "Instalando ou atualizando dependencias..."
& $venvPython -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar as dependencias do projeto."
}

Write-Host "Iniciando a aplicacao..."
& $venvPython -m streamlit run app.py
if ($LASTEXITCODE -ne 0) {
    throw "A aplicacao foi encerrada com erro."
}
