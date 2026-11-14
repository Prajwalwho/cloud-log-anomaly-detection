<#
Live evaluation runner (Phase 10, RQ3; docs/testing/live-evaluation-plan.md).

Runs the fault runs back to back (continuous traffic, every scenario in a different position in each run), then a
fault-free hour, waits for the last windows and auto-resolves, evaluates every run and writes the summary.
Before starting: stack up, venv active, detection and alerting services running, laptop plugged in and not set to
sleep. Takes about 41 minutes per fault run plus 60 minutes for the fault-free run.

Usage (project root):
    .\scripts\run_live_evaluation.ps1                  # runs 1-5 and the fault-free hour (about 4 h 40 min)
    .\scripts\run_live_evaluation.ps1 -Runs 1,2,3      # a subset
    .\scripts\run_live_evaluation.ps1 -SkipNormal      # fault runs only
    .\scripts\run_live_evaluation.ps1 -Runs @() -OnlyNormal
#>
param(
    [int[]]$Runs = @(1, 2, 3, 4, 5),
    [switch]$SkipNormal,
    [switch]$OnlyNormal,
    [int]$NormalMinutes = 60
)

$ErrorActionPreference = 'Stop'

# Each scenario once per run; the order rotates, so every scenario appears once in every position over 5 runs.
$Scenarios = @('error_burst', 'latency_spike', 'new_error', 'silent_service', 'cascading_failure')

function Get-Order([int]$run) {
    $shift = ($run - 1) % $Scenarios.Count
    return @($Scenarios[$shift..($Scenarios.Count - 1)]) + @(if ($shift -gt 0) { $Scenarios[0..($shift - 1)] })
}

function Invoke-Checked([string]$what, [scriptblock]$block) {
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" }
}

if (-not $env:VIRTUAL_ENV) { throw 'Activate the virtual environment first: backend\.venv\Scripts\Activate.ps1' }
New-Item -ItemType Directory -Force data\ground_truth | Out-Null

$done = @()
if (-not $OnlyNormal) {
    foreach ($run in $Runs) {
        $order = Get-Order $run
        $gt = "data/ground_truth/eval-r$run.jsonl"
        Write-Host "`n=== Fault run r$run (seed $(100 + $run)): $($order -join ' -> ') ===  started $(Get-Date -Format HH:mm)"
        Invoke-Checked "generator r$run" {
            python -m backend.log_generator.generator --kafka --seed (100 + $run) --scenario @order --ground-truth $gt
        }
        $done += @{ Label = "r$run"; GroundTruth = $gt }
    }
}

$normal = $null
if (-not $SkipNormal) {
    Write-Host "`n=== Fault-free run n1 (seed 201, $NormalMinutes min) ===  started $(Get-Date -Format HH:mm)"
    $start = (Get-Date).ToUniversalTime()
    Invoke-Checked 'generator n1' {
        python -m backend.log_generator.generator --kafka --seed 201 --duration ($NormalMinutes * 60)
    }
    $end = (Get-Date).ToUniversalTime()
    # Leave out the first two minutes (traffic starting) and the last one (traffic stopping).
    $normal = @{
        From = $start.AddMinutes(2).ToString('yyyy-MM-ddTHH:mm:00Z')
        To   = $end.AddMinutes(-1).ToString('yyyy-MM-ddTHH:mm:00Z')
    }
}

Write-Host "`nWaiting 7 minutes for the last windows to close and quiet alerts to resolve..."
Start-Sleep -Seconds 420

foreach ($item in $done) {
    Invoke-Checked "evaluation $($item.Label)" { python scripts/live_eval.py run $item.GroundTruth --label $item.Label }
}
if ($normal) {
    Invoke-Checked 'evaluation n1' { python scripts/live_eval.py normal --label n1 --from $normal.From --to $normal.To }
}
Invoke-Checked 'summary' { python scripts/live_eval.py summary }
Write-Host "`nDone $(Get-Date -Format HH:mm). Results: experiments/results/live/ (summary.md for the paper)."