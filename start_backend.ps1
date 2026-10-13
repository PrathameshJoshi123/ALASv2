<#
.SYNOPSIS
    Starts the MajorProject backend (FastAPI Web Server + Celery Background Worker + Docker Redis).

.DESCRIPTION
    Checks if Redis is running, automatically starts the Redis container in Docker if needed,
    launches the Celery background worker in a dedicated console window, and starts the
    Uvicorn FastAPI server on http://127.0.0.1:8000 in the active terminal.

.EXAMPLE
    .\start_backend.ps1
    .\start_backend.ps1 -ServerOnly
    .\start_backend.ps1 -WorkerOnly
    .\start_backend.ps1 -RedisOnly
#>

param (
    [switch]$ServerOnly,
    [switch]$WorkerOnly,
    [switch]$RedisOnly
)

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RootDir) {
    $RootDir = Get-Location
}
Set-Location $RootDir

$VenvPython  = Join-Path $RootDir "venv\Scripts\python.exe"
$VenvUvicorn = Join-Path $RootDir "venv\Scripts\uvicorn.exe"
$VenvCelery  = Join-Path $RootDir "venv\Scripts\celery.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment not found at $VenvPython!" -ForegroundColor Red
    Write-Host "Please ensure your virtual environment is created in .\venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       MajorProject Backend Starter (PowerShell)            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Working Directory : $RootDir" -ForegroundColor Gray
Write-Host "Python Executable : $VenvPython" -ForegroundColor Gray

# Function to start or run Redis in Docker
function Start-DockerRedis {
    Write-Host "[INFO] Checking Docker for Redis container..." -ForegroundColor Cyan
    try {
        # Check if docker CLI is available and responsive
        $dockerCheck = docker info 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARNING] Docker is not running or not responsive." -ForegroundColor Yellow
            return $false
        }

        # Check if a container named 'redis' exists
        $existingContainer = docker ps -a --filter "name=^/redis$" --format "{{.Names}}" 2>$null
        if ($existingContainer -eq "redis") {
            Write-Host "[DOCKER] Starting existing 'redis' container..." -ForegroundColor Cyan
            docker start redis | Out-Null
        } else {
            Write-Host "[DOCKER] Starting new Redis container on port 6379..." -ForegroundColor Cyan
            docker run -d --name redis -p 6379:6379 redis:latest | Out-Null
        }

        Start-Sleep -Seconds 2
        return $true
    } catch {
        Write-Host "[WARNING] Could not start Redis via Docker: $_" -ForegroundColor Yellow
        return $false
    }
}

# Redis Ping & Auto-Start Check
$redisConnected = $false
try {
    $redisCheck = & $VenvPython -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); r.ping(); print('OK')" 2>$null
    if ($redisCheck -eq "OK") {
        $redisConnected = $true
        Write-Host "[OK] Redis is connected and responsive on localhost:6379." -ForegroundColor Green
    }
} catch {}

if (-not $redisConnected) {
    Write-Host "[INFO] Redis is not currently reachable. Attempting to start Redis in Docker..." -ForegroundColor Yellow
    $started = Start-DockerRedis
    if ($started) {
        $redisCheck = & $VenvPython -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); r.ping(); print('OK')" 2>$null
        if ($redisCheck -eq "OK") {
            $redisConnected = $true
            Write-Host "[OK] Successfully started and connected to Redis via Docker!" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Redis container started, but ping not yet responding. Proceeding..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARNING] Docker Redis could not be started automatically. Ensure Redis is running." -ForegroundColor Yellow
    }
}

# Flush Redis so stale tasks/queues from previous sessions are wiped clean on every new startup
if ($redisConnected) {
    Write-Host "[REDIS] Flushing all Redis databases (FLUSHALL) for a clean server start..." -ForegroundColor Cyan
    try {
        $flushResult = & $VenvPython -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); r.flushall(); print('FLUSHED')" 2>$null
        if ($flushResult -eq "FLUSHED") {
            Write-Host "[OK] Redis database flushed successfully." -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Could not flush Redis: $flushResult" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[WARNING] Error while attempting to flush Redis: $_" -ForegroundColor Yellow
    }
}

# Mode 0: Redis Only
if ($RedisOnly) {
    Write-Host "`n[DONE] Redis is running. Exiting." -ForegroundColor Green
    exit 0
}

# Mode 1: Server Only
if ($ServerOnly) {
    Write-Host "`n[STARTING] FastAPI Uvicorn Server on http://127.0.0.1:8000..." -ForegroundColor Green
    & $VenvUvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
    exit 0
}

# Mode 2: Worker Only
if ($WorkerOnly) {
    Write-Host "`n[STARTING] Celery Worker (-P solo)..." -ForegroundColor Green
    & $VenvCelery -A backend.celery_app.celery_app worker --loglevel=info -P solo
    exit 0
}

# Mode 3: Full Backend (Celery Worker in new window + Uvicorn in current window)
Write-Host "`n[1/2] Launching Celery Background Worker in a separate window..." -ForegroundColor Cyan
$WorkerTitle = "MajorProject - Celery Background Worker"
$WorkerScript = @"
`$host.UI.RawUI.WindowTitle = '$WorkerTitle'
cd '$RootDir'
Write-Host '============================================================' -ForegroundColor Magenta
Write-Host '               MajorProject Celery Worker                   ' -ForegroundColor Magenta
Write-Host '============================================================' -ForegroundColor Magenta
.\venv\Scripts\celery.exe -A backend.celery_app.celery_app worker --loglevel=info -P solo
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $WorkerScript

Write-Host "[2/2] Starting FastAPI Uvicorn Server in this console (http://127.0.0.1:8000)..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server.`n" -ForegroundColor Gray
$host.UI.RawUI.WindowTitle = "MajorProject - FastAPI Server"

& $VenvUvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
