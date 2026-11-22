# NETWATCH installer / updater for Windows.
#
# First install (PowerShell):
#   irm https://raw.githubusercontent.com/assyaref/NETWATCH/main/install.ps1 | iex
# Afterwards, from any CMD/PowerShell:
#   netwatch-update
#
# Downloads the latest NETWATCH.exe from GitHub Releases into C:\Program Files\NETWATCH,
# adds the commands `netwatch` and `netwatch-update` to PATH, and creates shortcuts.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo       = 'assyaref/NETWATCH'
$ScriptUrl  = "https://raw.githubusercontent.com/$Repo/main/install.ps1"
$InstallDir = Join-Path $env:ProgramFiles 'NETWATCH'
$ExePath    = Join-Path $InstallDir 'NETWATCH.exe'
$VerFile    = Join-Path $InstallDir 'version.txt'

function Write-Step($msg) { Write-Host "  > $msg" -ForegroundColor Green }
function Finish {
    # Keep the separate elevated window open so the result can be read.
    if ($env:NETWATCH_PAUSE -eq '1') { Write-Host ''; Read-Host 'Tekan Enter untuk menutup' | Out-Null }
}

# --- Administrator (needed to write to Program Files) ------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Meminta izin Administrator...' -ForegroundColor Yellow
    $cmd = "`$env:NETWATCH_PAUSE='1'; irm '$ScriptUrl' | iex"
    try {
        Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`""
    } catch {
        Write-Host 'Izin Administrator ditolak. Update dibatalkan.' -ForegroundColor Red
    }
    return
}

Write-Host ''
Write-Host '  NETWATCH // UPDATE TERMINAL' -ForegroundColor Cyan
Write-Host '  ---------------------------' -ForegroundColor DarkCyan

try {
    # --- Latest release -------------------------------------------------------------------
    Write-Step 'Memeriksa versi terbaru di GitHub...'
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" `
                             -Headers @{ 'User-Agent' = 'netwatch-updater' }
    $asset = $rel.assets | Where-Object { $_.name -eq 'NETWATCH.exe' } | Select-Object -First 1
    if (-not $asset) { throw "Rilis $($rel.tag_name) tidak berisi NETWATCH.exe" }
    $latest = $rel.tag_name
    $current = if (Test-Path $VerFile) { (Get-Content $VerFile -Raw).Trim() } else { '' }

    if ($current -eq $latest -and (Test-Path $ExePath)) {
        Write-Step "Sudah versi terbaru ($latest)."
    } else {
        if ($current) { Write-Step "Update $current -> $latest" } else { Write-Step "Install $latest" }

        # --- Download -------------------------------------------------------------------
        $tmp = Join-Path $env:TEMP "NETWATCH-$latest.exe"
        Write-Step "Mengunduh NETWATCH.exe ($([math]::Round($asset.size / 1MB, 1)) MB)..."
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -UseBasicParsing `
                          -Headers @{ 'User-Agent' = 'netwatch-updater' }
        if ((Get-Item $tmp).Length -ne $asset.size) { throw 'Unduhan tidak lengkap, coba lagi.' }
        Unblock-File $tmp

        # --- Stop running instance ------------------------------------------------------
        $running = Get-Process -Name 'NETWATCH' -ErrorAction SilentlyContinue
        if ($running) {
            Write-Step 'Menutup NETWATCH yang sedang berjalan...'
            $running | Stop-Process -Force
            Start-Sleep -Seconds 2
        }

        # --- Replace --------------------------------------------------------------------
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Move-Item -Force $tmp $ExePath
        Set-Content -Path $VerFile -Value $latest -Encoding ASCII
        Write-Step "NETWATCH $latest terpasang di $InstallDir"
    }

    # --- Commands: netwatch / netwatch-update ---------------------------------------------
    $updCmd = Join-Path $InstallDir 'netwatch-update.cmd'
    Set-Content -Path $updCmd -Encoding ASCII -Value @(
        '@echo off',
        "powershell -NoProfile -ExecutionPolicy Bypass -Command `"irm '$ScriptUrl' | iex`""
    )
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if (($machinePath -split ';') -notcontains $InstallDir) {
        [Environment]::SetEnvironmentVariable('Path', "$machinePath;$InstallDir", 'Machine')
        Write-Step 'Perintah "netwatch" dan "netwatch-update" ditambahkan (buka terminal baru).'
    }

    # --- Shortcuts --------------------------------------------------------------------------
    $shell = New-Object -ComObject WScript.Shell
    $links = @(
        (Join-Path ([Environment]::GetFolderPath('CommonStartMenu')) 'Programs\NETWATCH.lnk'),
        (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'NETWATCH.lnk')
    )
    foreach ($l in $links) {
        if (-not (Test-Path $l)) {
            $s = $shell.CreateShortcut($l)
            $s.TargetPath = $ExePath
            $s.WorkingDirectory = $InstallDir
            $s.IconLocation = "$ExePath,0"
            $s.Description = 'NETWATCH Network Surveillance Terminal'
            $s.Save()
        }
    }

    Write-Host ''
    Write-Host '  SELESAI. Jalankan dengan mengetik: netwatch' -ForegroundColor Cyan
    Finish
} catch {
    Write-Host ''
    Write-Host "  GAGAL: $($_.Exception.Message)" -ForegroundColor Red
    Finish
}
