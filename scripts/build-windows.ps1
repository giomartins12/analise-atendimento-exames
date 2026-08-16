$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildPython = Join-Path $repoRoot ".build-venv\Scripts\python.exe"

Push-Location $repoRoot
try {
    if (-not (Test-Path $buildPython)) {
        python -m venv ".build-venv"
        if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente de build." }
    }

    & $buildPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip." }
    & $buildPython -m pip install -e ".[dev,build]"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências de build." }
    & $buildPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Os testes falharam; o instalador não será criado." }

    & $buildPython -m PyInstaller --noconfirm --clean "installer\AnaliseAtendimentoExames.spec"
    if ($LASTEXITCODE -ne 0) { throw "Falha no empacotamento com PyInstaller." }

    $isccCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 não encontrado. Instale-o em https://jrsoftware.org/isdl.php"
    }

    & $iscc "installer\AnaliseAtendimentoExames.iss"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o instalador." }

    $installer = Get-ChildItem "installer\output\AnaliseAtendimentoExames-Setup-*-win64.exe" | Select-Object -First 1
    if (-not $installer) { throw "O arquivo final do instalador não foi encontrado." }
    Write-Host "Instalador criado: $($installer.FullName)"
}
finally {
    Pop-Location
}

