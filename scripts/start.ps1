<#
.SYNOPSIS
    Controls the infrastructure stack (Kafka, PostgreSQL, Elasticsearch).

.DESCRIPTION
    Actions:
      up      Start all containers, wait until healthy, then run the smoke test.
      down    Stop and remove containers (data in volumes is kept).
      status  Show container status.
      logs    Follow logs (all services, or one: kafka, postgres, elasticsearch).
      test    Run the smoke test only.
      reset   Delete ALL data (PostgreSQL and Elasticsearch volumes). Asks for confirmation.

.EXAMPLE
    .\scripts\start.ps1 up
    .\scripts\start.ps1 logs kafka
    .\scripts\start.ps1 reset
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "status", "logs", "test", "reset")]
    [string]$Action = "up",

    [Parameter(Position = 1)]
    [string]$Service = ""
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ComposeFile = Join-Path $ProjectRoot "infrastructure\docker\docker-compose.yml"
$EnvFile     = Join-Path $ProjectRoot ".env"
$VenvPython  = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"
$SmokeTest   = Join-Path $ProjectRoot "scripts\smoke_test.py"
$Compose     = @("compose", "-f", $ComposeFile, "--env-file", $EnvFile)

$HealthChecked = @("cla-kafka", "cla-postgres", "cla-elasticsearch")

# ---------------- helpers ----------------
function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Stop-WithError([string]$Message) {
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
    exit 1
}

function Assert-Ready {
    docker info > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Docker is not running. Start Docker Desktop first."
    }
    if (-not (Test-Path $EnvFile)) {
        Stop-WithError ".env not found. Run .\scripts\setup.ps1 first."
    }
}

function Wait-Healthy([string[]]$Containers, [int]$TimeoutSeconds = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    foreach ($container in $Containers) {
        while ($true) {
            $status = docker inspect --format "{{.State.Health.Status}}" $container 2>$null
            if ($status -eq "healthy") {
                Write-Host "  [OK] $container is healthy" -ForegroundColor Green
                break
            }
            if ((Get-Date) -gt $deadline) {
                Stop-WithError "$container did not become healthy within $TimeoutSeconds s (last status: $status). Check: .\scripts\start.ps1 logs"
            }
            Start-Sleep -Seconds 3
        }
    }
}

function Wait-KafkaInit([int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ($true) {
        $state = docker inspect --format "{{.State.Status}} {{.State.ExitCode}}" cla-kafka-init 2>$null
        if ($state -eq "exited 0") {
            Write-Host "  [OK] Kafka topics created" -ForegroundColor Green
            return
        }
        if ($state -like "exited *") {
            Stop-WithError "kafka-init failed ($state). Check: docker logs cla-kafka-init"
        }
        if ((Get-Date) -gt $deadline) {
            Stop-WithError "kafka-init did not finish within $TimeoutSeconds s"
        }
        Start-Sleep -Seconds 2
    }
}

function Invoke-SmokeTest {
    if (-not (Test-Path $VenvPython)) {
        Stop-WithError "Virtual environment not found. Run .\scripts\setup.ps1 first."
    }
    & $VenvPython $SmokeTest
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Smoke test failed"
    }
}

# ---------------- actions ----------------
switch ($Action) {

    "up" {
        Assert-Ready
        Write-Step "Starting containers"
        docker @Compose up -d
        if ($LASTEXITCODE -ne 0) { Stop-WithError "docker compose up failed" }

        Write-Step "Waiting for services to become healthy"
        Wait-Healthy $HealthChecked
        Wait-KafkaInit

        Write-Step "Running smoke test"
        Invoke-SmokeTest

        Write-Host ""
        Write-Host "Stack is up." -ForegroundColor Green
        Write-Host "  Kafka          localhost:9092"
        Write-Host "  PostgreSQL     localhost:15432"
        Write-Host "  Elasticsearch  http://localhost:9200"
    }

    "down" {
        Assert-Ready
        Write-Step "Stopping containers (data is kept)"
        docker @Compose down
    }

    "status" {
        Assert-Ready
        docker @Compose ps -a
    }

    "logs" {
        Assert-Ready
        if ($Service) {
            docker @Compose logs -f --tail 100 $Service
        } else {
            docker @Compose logs -f --tail 100
        }
    }

    "test" {
        Invoke-SmokeTest
    }

    "reset" {
        Assert-Ready
        Write-Host ""
        Write-Host "WARNING: this deletes ALL PostgreSQL and Elasticsearch data." -ForegroundColor Yellow
        $answer = Read-Host "Type 'yes' to continue"
        if ($answer -ne "yes") {
            Write-Host "Cancelled."
            exit 0
        }
        Write-Step "Removing containers and volumes"
        docker @Compose down -v
        Write-Host "Reset complete. Start again with: .\scripts\start.ps1 up" -ForegroundColor Green
    }
}