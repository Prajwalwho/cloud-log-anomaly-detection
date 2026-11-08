<#
.SYNOPSIS
    One-time project setup for Cloud Log Anomaly Detection.

.DESCRIPTION
    1. Checks prerequisites (Python 3.12, Node.js, npm, Git, Docker).
    2. Creates the Python 3.12 virtual environment at backend\.venv.
    3. Installs Python dependencies from requirements-dev.txt.
    4. Creates .env from .env.example (if .env does not exist).
    5. Installs frontend dependencies.
    6. Pulls the Docker images.

    Safe to run again: an existing virtual environment and .env are kept.

.EXAMPLE
    .\scripts\setup.ps1
#>

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$VenvDir     = Join-Path $ProjectRoot "backend\.venv"
$VenvPython  = Join-Path $VenvDir "Scripts\python.exe"
$ComposeFile = Join-Path $ProjectRoot "infrastructure\docker\docker-compose.yml"
$EnvFile     = Join-Path $ProjectRoot ".env"
$EnvExample  = Join-Path $ProjectRoot ".env.example"

# ---------------- helpers ----------------
function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Stop-WithError([string]$Message) {
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
    exit 1
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "$Description failed (exit code $LASTEXITCODE)"
    }
}

# ---------------- 1. prerequisites ----------------
Write-Step "Checking prerequisites"

if (-not (Test-Command "py")) {
    Stop-WithError "Python launcher 'py' not found. Install Python 3.12 from python.org."
}
$pyVersion = & py -3.12 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Python 3.12 not found. Install it with: winget install -e --id Python.Python.3.12"
}
Write-Ok "$pyVersion"

foreach ($tool in @("node", "npm", "git", "docker")) {
    if (-not (Test-Command $tool)) {
        Stop-WithError "'$tool' not found. Install it and run this script again."
    }
}
Write-Ok "Node.js $(node --version), npm $(npm --version)"
Write-Ok "$(git --version)"

docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Docker is installed but not running. Start Docker Desktop and run this script again."
}
Write-Ok "Docker is running"

# ---------------- 2. virtual environment ----------------
Write-Step "Python virtual environment"

if (Test-Path $VenvPython) {
    $venvVersion = & $VenvPython --version 2>&1
    if ($venvVersion -notmatch "3\.12") {
        Stop-WithError "Existing backend\.venv uses $venvVersion. Delete backend\.venv and run this script again."
    }
    Write-Ok "Existing venv kept ($venvVersion)"
} else {
    Invoke-Checked { py -3.12 -m venv $VenvDir } "Creating virtual environment"
    Write-Ok "Created backend\.venv"
}

# ---------------- 3. Python dependencies ----------------
Write-Step "Installing Python dependencies (this can take a few minutes)"

Invoke-Checked { & $VenvPython -m pip install --upgrade pip --quiet } "Upgrading pip"
Invoke-Checked { & $VenvPython -m pip install -r requirements-dev.txt --quiet } "Installing requirements-dev.txt"
Invoke-Checked {
    & $VenvPython -c "import fastapi, sklearn, drain3, confluent_kafka, aiokafka, elasticsearch, psycopg; print('  imports OK')"
} "Verifying Python imports"
Write-Ok "Python dependencies installed"

# ---------------- 4. .env ----------------
Write-Step "Environment file"

if (Test-Path $EnvFile) {
    Write-Ok ".env already exists (kept)"
} else {
    Copy-Item $EnvExample $EnvFile
    Write-Ok "Created .env from .env.example"
}

# ---------------- 5. frontend dependencies ----------------
Write-Step "Installing frontend dependencies"

if (Test-Path (Join-Path $ProjectRoot "frontend\package-lock.json")) {
    Invoke-Checked { npm ci --prefix frontend --no-audit --no-fund } "npm ci"
} else {
    Invoke-Checked { npm install --prefix frontend --no-audit --no-fund } "npm install"
}
Write-Ok "Frontend dependencies installed"

# ---------------- 6. Docker images ----------------
Write-Step "Pulling Docker images (first time can take several minutes)"

Invoke-Checked { docker compose -f $ComposeFile --env-file $EnvFile pull } "Pulling Docker images"
Write-Ok "Docker images ready"

# ---------------- done ----------------
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  .\scripts\start.ps1 up       # start Kafka, PostgreSQL, Elasticsearch"
Write-Host "  .\scripts\start.ps1 status   # see container status"
Write-Host ""