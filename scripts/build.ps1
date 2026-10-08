$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$distRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist'))
$legacyDirectory = [IO.Path]::GetFullPath((Join-Path $distRoot 'PromptSmith'))
$singleFile = Join-Path $distRoot 'PromptSmith.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv. Run: python -m venv .venv; .venv/Scripts/python.exe -m pip install -r requirements.txt'
}
if (-not $legacyDirectory.StartsWith($distRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe legacy distribution path: $legacyDirectory"
}
Push-Location $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean PromptSmith.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $singleFile -PathType Leaf)) {
        throw "Single-file executable was not created: $singleFile"
    }
    if (Test-Path -LiteralPath $legacyDirectory -PathType Container) {
        Remove-Item -LiteralPath $legacyDirectory -Recurse -Force
    }
    Write-Host "Single-file build: $singleFile"
} finally {
    Pop-Location
}
