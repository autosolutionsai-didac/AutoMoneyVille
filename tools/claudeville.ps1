param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Command = 'status',
    [string]$Fork = 'the_ville_isabella_maria_klaus',
    [string]$SimName = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root 'env\Scripts\python.exe'
$FrontendDir = Join-Path $Root 'environment\frontend_server'
$BackendDir = Join-Path $Root 'reverie\backend_server'
$TempDir = Join-Path $Root 'environment\frontend_server\temp_storage'
$PidFile = Join-Path $TempDir 'runtime_pids.json'
$DjangoOut = Join-Path $Root 'django.out.log'
$DjangoErr = Join-Path $Root 'django.err.log'
$BackendOut = Join-Path $Root 'backend.out.log'
$BackendErr = Join-Path $Root 'backend.err.log'

function Require-Python {
    if (-not (Test-Path $Python)) {
        throw "Missing local Python environment at $Python. Create it with: uv venv --python 3.11 env"
    }
}

function Stop-ProcessTree {
    param(
        [int]$ProcessId,
        [hashtable]$Seen = @{}
    )
    if ($Seen.ContainsKey($ProcessId)) {
        return
    }
    $Seen[$ProcessId] = $true

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId -Seen $Seen
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Read-Pids {
    if (-not (Test-Path $PidFile)) {
        return $null
    }
    return Get-Content -Raw $PidFile | ConvertFrom-Json
}

function Stop-Claudeville {
    $pids = Read-Pids
    if ($null -eq $pids) {
        Write-Host 'No runtime_pids.json found.'
    } else {
        foreach ($pidValue in @($pids.frontend_pid, $pids.backend_pid)) {
            if ($pidValue) {
                Stop-ProcessTree -ProcessId ([int]$pidValue)
            }
        }
    }

    foreach ($port in @(8000, 5000)) {
        $owners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($owner in $owners) {
            if ($owner) {
                Stop-ProcessTree -ProcessId ([int]$owner)
            }
        }
    }

    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host 'Claudeville stopped.'
}

function Start-Claudeville {
    Require-Python
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:CLAUDEVILLE_PERSONA_MOVE_TIMEOUT = '15'

    foreach ($port in @(8000, 5000)) {
        $owners = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($owner in $owners) {
            if ($owner) {
                Stop-ProcessTree -ProcessId ([int]$owner)
            }
        }
    }

    if (-not $SimName) {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $SimName = "${Fork}_${stamp}"
    }

    $backendCode = @"
import time
from reverie import ReverieServer
rs = ReverieServer("$Fork", "$SimName")
rs.start_http_server()
print("Backend ready for $SimName at http://127.0.0.1:5000", flush=True)
while True:
    time.sleep(3600)
"@
    $encodedBackend = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($backendCode))
    $backendArgs = "-c `"import base64;exec(base64.b64decode('$encodedBackend'))`""

    $frontend = Start-Process -FilePath $Python `
        -ArgumentList @('manage.py', 'runserver', '127.0.0.1:8000', '--noreload') `
        -WorkingDirectory $FrontendDir `
        -RedirectStandardOutput $DjangoOut `
        -RedirectStandardError $DjangoErr `
        -WindowStyle Hidden `
        -PassThru

    $backend = Start-Process -FilePath $Python `
        -ArgumentList $backendArgs `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $BackendOut `
        -RedirectStandardError $BackendErr `
        -WindowStyle Hidden `
        -PassThru

    @{
        frontend_pid = $frontend.Id
        backend_pid = $backend.Id
        sim_name = $SimName
        fork = $Fork
        started_at = (Get-Date).ToString('o')
    } | ConvertTo-Json | Set-Content -Encoding UTF8 $PidFile

    Write-Host "Claudeville starting: http://127.0.0.1:8000/simulator_home"
    Write-Host "Health: http://127.0.0.1:5000/health"
    Write-Host "PIDs written to $PidFile"
}

function Show-Status {
    $pids = Read-Pids
    if ($null -eq $pids) {
        Write-Host 'No PID file found.'
    } else {
        $pids | ConvertTo-Json
    }

    foreach ($port in @(8000, 5000)) {
        $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn) {
            Write-Host "Port ${port}: listening (pid $($conn.OwningProcess))"
        } else {
            Write-Host "Port ${port}: closed"
        }
    }

    try {
        $health = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5000/health' -TimeoutSec 3
        Write-Host $health.Content
    } catch {
        Write-Host "Backend /health unavailable: $($_.Exception.Message)"
    }
}

switch ($Command) {
    'start' { Start-Claudeville }
    'stop' { Stop-Claudeville }
    'restart' {
        Stop-Claudeville
        Start-Claudeville
    }
    'status' { Show-Status }
}
