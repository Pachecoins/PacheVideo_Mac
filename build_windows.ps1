param(
    [switch]$SkipInstall,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

$AppName = "PacheVideo"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host ""
Write-Host "========================================"
Write-Host "  PacheVideo Windows Builder"
Write-Host "========================================"
Write-Host ""

function Test-PythonPip {
    param(
        [string]$Command,
        [string[]]$Args = @()
    )

    try {
        & $Command @Args -m pip --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PythonCommand {
    param(
        [string]$Command,
        [string[]]$Args = @()
    )

    try {
        & $Command @Args --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$PythonCmd = $null
$PythonArgs = @()

$KnownPythonPaths = @(
    $PythonPath,
    "C:\Python311\python.exe",
    "C:\Python312\python.exe",
    "C:\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
) | Where-Object { $_ -and (Test-Path $_) }

foreach ($Candidate in $KnownPythonPaths) {
    if (Test-PythonCommand $Candidate) {
        $PythonCmd = $Candidate
        $PythonArgs = @()
        break
    }
}

if ($PythonCmd) {
    # Already selected from an explicit or known absolute path.
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonCommand "python")) {
    $PythonCmd = "python"
    $PythonArgs = @()
} elseif ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonCommand "py" @("-3.11"))) {
    $PythonCmd = "py"
    $PythonArgs = @("-3.11")
} elseif ((Get-Command py -ErrorAction SilentlyContinue) -and (Test-PythonCommand "py" @("-3"))) {
    $PythonCmd = "py"
    $PythonArgs = @("-3")
} else {
    throw "No se encontro Python 3. Proba: .\build_windows.ps1 -PythonPath C:\Python311\python.exe"
}

Write-Host "[1/5] Python:"
& $PythonCmd @PythonArgs --version

if (-not (Test-PythonPip $PythonCmd $PythonArgs)) {
    Write-Host "pip no esta activo para este Python. Intentando instalar pip con ensurepip..."
    & $PythonCmd @PythonArgs -m ensurepip --upgrade
    if (-not (Test-PythonPip $PythonCmd $PythonArgs)) {
        throw "Python funciona, pero pip no pudo activarse. Reinstala Python 3.11 marcando 'pip' y 'Add python.exe to PATH'."
    }
}

if (-not $SkipInstall) {
    Write-Host "[2/5] Instalando dependencias..."
    & $PythonCmd @PythonArgs -m pip install --upgrade pip
    & $PythonCmd @PythonArgs -m pip install -r requirements.txt
} else {
    Write-Host "[2/5] Saltando instalacion de dependencias (-SkipInstall)."
}

Write-Host "[3/5] Preparando ffmpeg.exe..."

$FfmpegPath = ""
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $PythonCmd @PythonArgs -c "import ffmpeg_downloader as ffd; ffd.download()" *> $null
    $DownloadedFfmpeg = (& $PythonCmd @PythonArgs -c "import ffmpeg_downloader as ffd; print(ffd.ffmpeg_path)" 2>$null)
    if ($DownloadedFfmpeg) {
        $FfmpegPath = $DownloadedFfmpeg.Trim()
    }
} catch {
    $FfmpegPath = ""
} finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
}

if (-not $FfmpegPath -or -not (Test-Path $FfmpegPath)) {
    $SystemFfmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($SystemFfmpeg) {
        $FfmpegPath = $SystemFfmpeg.Source
    }
}

if (-not $FfmpegPath -or -not (Test-Path $FfmpegPath)) {
    throw "No se encontro ffmpeg.exe. Instala ffmpeg y volve a correr el build, o ejecuta sin -SkipInstall para instalar ffmpeg-downloader."
}

Copy-Item -LiteralPath $FfmpegPath -Destination ".\ffmpeg.exe" -Force
Write-Host "ffmpeg: $FfmpegPath"

Write-Host "[4/5] Limpiando builds anteriores..."
Remove-Item -Recurse -Force ".\build", ".\dist" -ErrorAction SilentlyContinue
Remove-Item -Force ".\PacheVideo.spec" -ErrorAction SilentlyContinue

Write-Host "[5/5] Construyendo PacheVideo.exe..."
$PyInstallerArgs = @(
    "--onefile",
    "--windowed",
    "--name", $AppName,
    "--icon", "icon.ico",
    "--add-binary", "ffmpeg.exe;.",
    "--add-data", "icon.ico;.",
    "--add-data", "logo.png;.",
    "--hidden-import", "customtkinter",
    "--hidden-import", "yt_dlp",
    "--hidden-import", "PIL",
    "--hidden-import", "mutagen",
    "--hidden-import", "yt_dlp_ejs",
    "--collect-all", "customtkinter",
    "--collect-all", "yt_dlp_ejs",
    "pache_video.py"
)

& $PythonCmd @PythonArgs -m PyInstaller @PyInstallerArgs

Remove-Item -Force ".\ffmpeg.exe" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue
Remove-Item -Force ".\PacheVideo.spec" -ErrorAction SilentlyContinue

if (-not (Test-Path ".\dist\PacheVideo.exe")) {
    throw "No se genero dist\PacheVideo.exe. Revisa los errores anteriores."
}

Write-Host ""
Write-Host "Listo. Ejecutable generado en:"
Write-Host "  dist\PacheVideo.exe"
Write-Host ""
