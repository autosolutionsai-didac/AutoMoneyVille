<#
  One-command Claudeville launcher (Windows / PowerShell).

  Encodes the operational gotchas so the stack "just works":
    - kills any stale servers holding :5000 / :8000 (Windows leaves detached pythons),
    - starts the Flask backend (autosim) and feeds the startup prompt a newline so it
      begins a fresh sim from local_config.json's default_fork,
    - starts the Django frontend with DJANGO_DEBUG=True (REQUIRED: with DEBUG off,
      runserver returns 404 for every /static/ file -> black screen + green sprites),
    - waits for both health endpoints, then prints the URL.

  Usage:  powershell -ExecutionPolicy Bypass -File scripts\run_claudeville.ps1
  Note (one-time, Windows long paths for the_ville assets):  git config core.longpaths true
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root "env\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "env python not found at $Py (create the uv venv first)" }

function Stop-Port($port) {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($op in ($c.OwningProcess | Sort-Object -Unique)) {
        try { Stop-Process -Id $op -Force -ErrorAction Stop } catch {}
    }
}

function Start-Server($exe, $argline, $workdir, $envmap) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = $argline
    $psi.WorkingDirectory = $workdir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    foreach ($k in $envmap.Keys) { $psi.EnvironmentVariables[$k] = $envmap[$k] }
    return [System.Diagnostics.Process]::Start($psi)
}

function Wait-Url($url, $label, $timeoutSec) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 | Out-Null; Write-Host "  $label ready"; return } catch { Start-Sleep -Seconds 1 }
    }
    Write-Host "  $label did not respond within $timeoutSec s (check the window)"
}

Write-Host "Stopping any servers on :5000 / :8000 ..."
Stop-Port 5000; Stop-Port 8000; Start-Sleep -Milliseconds 800

Write-Host "Starting backend (Flask + autosim) ..."
$be = Start-Server $Py "-u reverie.py" (Join-Path $Root "reverie\backend_server") `
    @{ PYTHONUTF8 = "1"; PYTHONIOENCODING = "utf-8"; CLAUDEVILLE_PERSONA_MOVE_TIMEOUT = "120" }
Start-Sleep -Seconds 2
$be.StandardInput.WriteLine("")   # choose "start new simulation" at the prompt

Write-Host "Starting frontend (Django, DJANGO_DEBUG=True) ..."
$fe = Start-Server $Py "-u manage.py runserver 8000 --noreload" (Join-Path $Root "environment\frontend_server") `
    @{ PYTHONUTF8 = "1"; DJANGO_DEBUG = "True" }

Wait-Url "http://127.0.0.1:5000/health" "Backend" 120
Wait-Url "http://127.0.0.1:8000/simulator_home" "Frontend" 60

Write-Host ""
Write-Host "Claudeville is up ->  http://localhost:8000/simulator_home"
Write-Host "(First Play step is LLM-bound ~1-2 min, shown as 'Buffering'; then it streams.)"
Write-Host "Backend PID $($be.Id) | Frontend PID $($fe.Id).  Stop with: Stop-Process -Id $($be.Id),$($fe.Id)"
