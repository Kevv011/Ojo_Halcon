[CmdletBinding()]
param(
    [ValidateRange(0, 9)]
    [int]$Camera = 1,

    [switch]$CheckOnly,

    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $backendDir "requirements.txt"
$packageFile = Join-Path $frontendDir "package.json"
$lockFile = Join-Path $frontendDir "pnpm-lock.yaml"
$workspaceFile = Join-Path $frontendDir "pnpm-workspace.yaml"
$minimumPnpmVersion = [version]"11.25.0"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Convert-ToVersion {
    param(
        [string]$Text,
        [string]$ToolName
    )

    $match = [regex]::Match($Text, "(\d+)\.(\d+)\.(\d+)")
    if (-not $match.Success) {
        throw "No se pudo interpretar la version de ${ToolName}: $Text"
    }
    return [version]$match.Value
}

function Invoke-External {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-FileSha256 {
    param([string]$Path)

    $sha256 = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        $bytes = $sha256.ComputeHash($stream)
        return ([BitConverter]::ToString($bytes)).Replace("-", "")
    }
    finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

function Resolve-Python314 {
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        $versionText = & $py.Source -3.14 -c "import platform; print(platform.python_version())" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $version = Convert-ToVersion $versionText "Python"
            if ($version.Major -eq 3 -and $version.Minor -eq 14) {
                return [pscustomobject]@{
                    FilePath = $py.Source
                    Prefix = @("-3.14")
                    Version = $version
                }
            }
        }
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $versionText = & $python.Source -c "import platform; print(platform.python_version())" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $version = Convert-ToVersion $versionText "Python"
            if ($version.Major -eq 3 -and $version.Minor -eq 14) {
                return [pscustomobject]@{
                    FilePath = $python.Source
                    Prefix = @()
                    Version = $version
                }
            }
        }
    }

    throw @"
Python 3.14 no esta disponible.
Instala Python Install Manager y ejecuta: py install 3.14
Despues cierra y vuelve a abrir esta ventana.
"@
}

function Test-HttpEndpoint {
    param([string]$Uri)

    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 2
        return $true
    }
    catch {
        return $false
    }
}

function Test-ListeningPort {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Wait-ForEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds
    )

    $limit = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $limit) {
        if (Test-HttpEndpoint $Uri) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Start-PowerShellWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )

    $safeTitle = $Title.Replace("'", "''")
    $safeDirectory = $WorkingDirectory.Replace("'", "''")
    $payload = @"
`$Host.UI.RawUI.WindowTitle = '$safeTitle'
Set-Location -LiteralPath '$safeDirectory'
$Command
if (`$LASTEXITCODE -ne 0) {
    Write-Host "El proceso termino con un error. Revisa los mensajes anteriores." -ForegroundColor Red
}
"@
    $bytes = [Text.Encoding]::Unicode.GetBytes($payload)
    $encoded = [Convert]::ToBase64String($bytes)
    return Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-NoProfile",
        "-EncodedCommand",
        $encoded
    ) -PassThru
}

Write-Host "OJO DE HALCON - INICIO AUTOMATICO" -ForegroundColor Green
Write-Host "Proyecto: $projectRoot"
Write-Host "Camara seleccionada: $Camera"

Write-Step "Comprobando archivos del proyecto"
foreach ($requiredPath in @($backendDir, $frontendDir, $requirementsFile, $packageFile, $lockFile)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Falta un archivo o carpeta requerido: $requiredPath"
    }
}
Write-Ok "Estructura del proyecto completa"

Write-Step "Comprobando Python 3.14"
$python314 = Resolve-Python314
Write-Ok "Python $($python314.Version) disponible"

Write-Step "Comprobando Node.js 24 LTS"
$node = Get-Command "node" -ErrorAction SilentlyContinue
if ($null -eq $node) {
    throw "Node.js no esta instalado. Instala Node.js 24 LTS para Windows x64."
}
$nodeText = & $node.Source --version
$nodeVersion = Convert-ToVersion $nodeText "Node.js"
if ($nodeVersion.Major -ne 24) {
    throw "Se requiere Node.js 24 LTS. Version encontrada: $nodeVersion"
}
Write-Ok "Node.js $nodeVersion disponible"

Write-Step "Comprobando pnpm 11.25.0 o posterior"
$pnpm = Get-Command "pnpm" -ErrorAction SilentlyContinue
if ($null -eq $pnpm) {
    throw "pnpm no esta instalado. Ejecuta: npm install --global pnpm@11.25.0"
}
$pnpmText = & $pnpm.Source --version
$pnpmVersion = Convert-ToVersion $pnpmText "pnpm"
if ($pnpmVersion -lt $minimumPnpmVersion) {
    throw "Se requiere pnpm 11.25.0 o posterior. Version encontrada: $pnpmVersion"
}
Write-Ok "pnpm $pnpmVersion disponible"

Write-Step "Preparando el entorno virtual del backend"
$createVenv = -not (Test-Path -LiteralPath $venvPython)
if (-not $createVenv) {
    $venvVersionText = & $venvPython -c "import platform; print(platform.python_version())" 2>$null
    $venvVersion = Convert-ToVersion $venvVersionText "Python del entorno virtual"
    if ($venvVersion.Major -ne 3 -or $venvVersion.Minor -ne 14) {
        $backupName = ".venv-incompatible-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
        $backupPath = Join-Path $backendDir $backupName
        Write-Host "El entorno existente usa Python $venvVersion; se conservara en $backupName." -ForegroundColor Yellow
        Move-Item -LiteralPath $venvDir -Destination $backupPath
        $createVenv = $true
    }
}

if ($createVenv) {
    Write-Host "Creando backend\.venv con Python 3.14..."
    $venvArguments = @($python314.Prefix) + @("-m", "venv", $venvDir)
    Invoke-External $python314.FilePath $venvArguments "No se pudo crear el entorno virtual."
    Invoke-External $venvPython @("-m", "pip", "install", "--upgrade", "pip") `
        "No se pudo actualizar pip."
}

$requirementsHash = Get-FileSha256 $requirementsFile
$backendMarker = Join-Path $venvDir ".ojo-halcon-requirements.sha256"
$savedRequirementsHash = if (Test-Path -LiteralPath $backendMarker) {
    (Get-Content -Raw -LiteralPath $backendMarker).Trim()
} else {
    ""
}

# La ausencia de librerias es esperable en un .venv recien creado. Windows
# PowerShell convierte parte de stderr de programas nativos en NativeCommandError;
# se silencia solo durante esta prueba para poder continuar con la restauracion.
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    & $venvPython -c "import cv2, numpy, fastapi, uvicorn" 2>$null
    $backendImportsReady = $LASTEXITCODE -eq 0
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
$restoreBackend = $createVenv -or -not $backendImportsReady -or $savedRequirementsHash -ne $requirementsHash

if ($restoreBackend) {
    Write-Host "Instalando o restaurando dependencias del backend..."
    Invoke-External $venvPython @("-m", "pip", "install", "-r", $requirementsFile) `
        "No se pudieron instalar las dependencias del backend."
    Set-Content -LiteralPath $backendMarker -Value $requirementsHash -Encoding ASCII
}
Write-Ok "Backend preparado"

Write-Step "Preparando dependencias del frontend"
$frontendHashes = @(
    (Get-FileSha256 $packageFile),
    (Get-FileSha256 $lockFile)
)
if (Test-Path -LiteralPath $workspaceFile) {
    $frontendHashes += Get-FileSha256 $workspaceFile
}
$frontendHash = $frontendHashes -join "-"
$nodeModules = Join-Path $frontendDir "node_modules"
$frontendMarker = Join-Path $nodeModules ".ojo-halcon-lock.sha256"
$viteCommand = Join-Path $nodeModules ".bin\vite.cmd"
$savedFrontendHash = if (Test-Path -LiteralPath $frontendMarker) {
    (Get-Content -Raw -LiteralPath $frontendMarker).Trim()
} else {
    ""
}
$restoreFrontend = -not (Test-Path -LiteralPath $nodeModules) `
    -or -not (Test-Path -LiteralPath $viteCommand) `
    -or $savedFrontendHash -ne $frontendHash

if ($restoreFrontend) {
    Write-Host "Instalando o restaurando frontend\node_modules..."
    Push-Location $frontendDir
    try {
        Invoke-External $pnpm.Source @("install", "--frozen-lockfile") `
            "No se pudieron instalar las dependencias del frontend."
    }
    finally {
        Pop-Location
    }
    Set-Content -LiteralPath $frontendMarker -Value $frontendHash -Encoding ASCII
}
Write-Ok "Frontend preparado"

if ($CheckOnly) {
    Write-Host "`nComprobacion finalizada. El proyecto esta listo para ejecutarse." -ForegroundColor Green
    exit 0
}

Write-Step "Comprobando servicios existentes"
$backendRunning = Test-HttpEndpoint "http://127.0.0.1:8000/api/health"
if (-not $backendRunning -and (Test-ListeningPort 8000)) {
    throw "El puerto 8000 esta ocupado por otro programa. Cierralo antes de continuar."
}

$frontendRunning = Test-HttpEndpoint "http://127.0.0.1:5173/"
if (-not $frontendRunning -and (Test-ListeningPort 5173)) {
    throw "El puerto 5173 esta ocupado por otro programa. Cierralo antes de continuar."
}

if (-not $backendRunning) {
    Write-Step "Iniciando backend en una terminal independiente"
    $safePython = $venvPython.Replace("'", "''")
    $backendCommand = "& '$safePython' -m ojo_halcon.api --camera $Camera"
    $null = Start-PowerShellWindow "Ojo de Halcon - Backend" $backendDir $backendCommand
    if (-not (Wait-ForEndpoint "http://127.0.0.1:8000/api/health" 30)) {
        throw "El backend no respondio en 30 segundos. Revisa su nueva ventana."
    }
    Write-Ok "Backend disponible en http://127.0.0.1:8000"
}
else {
    Write-Ok "El backend ya estaba ejecutandose"
}

if (-not $frontendRunning) {
    Write-Step "Iniciando frontend en una terminal independiente"
    $safePnpm = $pnpm.Source.Replace("'", "''")
    $frontendCommand = "& '$safePnpm' dev"
    $null = Start-PowerShellWindow "Ojo de Halcon - Frontend" $frontendDir $frontendCommand
    if (-not (Wait-ForEndpoint "http://127.0.0.1:5173/" 30)) {
        throw "El frontend no respondio en 30 segundos. Revisa su nueva ventana."
    }
    Write-Ok "Frontend disponible en http://127.0.0.1:5173"
}
else {
    Write-Ok "El frontend ya estaba ejecutandose"
}

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173/"
}

Write-Host "`nOjo de Halcon esta listo." -ForegroundColor Green
Write-Host "Marcador: http://127.0.0.1:5173/"
Write-Host "Administracion: http://127.0.0.1:5173/admin"
Write-Host "Para detenerlo, presiona Ctrl+C en las dos ventanas abiertas."
