[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$Compiler = '',
    [string]$RuntimeInstaller = '',
    [string]$Version = '2026.10.14',
    [string]$OutputDirectory = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $projectRoot 'local_artifacts/installer-build'
if ($Version -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') { throw 'Version must contain 3 or 4 numeric components' }
if (-not $Python) {
    $Python = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python -ErrorAction Stop).Source }
}
if (-not $Compiler) {
    $compilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($compilerCommand) { $Compiler = $compilerCommand.Source }
    else { $Compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
}
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6.7+ or pass -Compiler with the ISCC.exe path' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'dist/installer' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $buildRoot, $OutputDirectory | Out-Null
if (-not $RuntimeInstaller) {
    $RuntimeInstaller = Join-Path $buildRoot 'MicrosoftEdgeWebview2Setup.exe'
    if (-not (Test-Path -LiteralPath $RuntimeInstaller)) {
        Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $RuntimeInstaller -UseBasicParsing
    }
}
$RuntimeInstaller = [IO.Path]::GetFullPath($RuntimeInstaller)
$signature = Get-AuthenticodeSignature -LiteralPath $RuntimeInstaller
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw 'WebView2 installer must have a valid Microsoft Corporation signature'
}
$previousMode = $env:INTEXT_BUNDLE_MODE
Push-Location $projectRoot
try {
    $env:INTEXT_BUNDLE_MODE = 'onedir'
    & $Python -m PyInstaller --noconfirm --clean --distpath (Join-Path $buildRoot 'dist') --workpath (Join-Path $buildRoot 'build') PromptSmith.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $payload = Join-Path $buildRoot 'dist/Intext'
    if (-not (Test-Path -LiteralPath (Join-Path $payload '_internal/python311.dll'))) {
        # DLL name follows the Python version used by the builder.
        if (-not (Get-ChildItem -LiteralPath (Join-Path $payload '_internal') -Filter 'python3*.dll')) {
            throw 'Incomplete onedir Python runtime'
        }
    }
    & $Compiler "/DAppVersion=$Version" "/DPayloadDir=$payload" "/DRuntimeInstaller=$RuntimeInstaller" "/DOutputDir=$OutputDirectory" (Join-Path $projectRoot 'installer/Intext.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
    $installer = Join-Path $OutputDirectory "Intext-Setup-$Version.exe"
    $hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($installer))" | Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Encoding ASCII
    Write-Host "Installer: $installer"
    Write-Host "SHA256: $hash"
} finally {
    $env:INTEXT_BUNDLE_MODE = $previousMode
    Pop-Location
}
