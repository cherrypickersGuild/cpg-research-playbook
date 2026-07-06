<#
.SYNOPSIS
  Registers (or removes) Windows Task Scheduler jobs for the seeding schedule
  described in SEEDING_STRATEGY.md section 5 - the Windows equivalent of crontab.txt.

.DESCRIPTION
  Each task calls a bash script (Git Bash / bash.exe) at the cadence in the
  strategy doc. Every script is safe to run on a shorter check-cycle than its
  actual work cycle - it no-ops internally until its own due date passes.

  Requires Git for Windows (bash.exe) on PATH, or pass -BashExe explicitly.
  Run this script from an elevated PowerShell if Task Scheduler prompts for
  admin rights in your environment (usually not required for per-user tasks).

.PARAMETER ProjectRoot
  Absolute path to the axCaseResearch4 project. Defaults to this script's
  parent directory (schedule/..).

.PARAMETER BashExe
  Path to bash.exe. Defaults to the first "bash" found on PATH (Git Bash).

.PARAMETER Unregister
  Remove all tasks this script registers instead of creating them.

.EXAMPLE
  # Register everything using defaults
  .\register_windows_tasks.ps1

.EXAMPLE
  # Remove everything this script registered
  .\register_windows_tasks.ps1 -Unregister
#>
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$BashExe = (Get-Command bash -ErrorAction SilentlyContinue).Source,
  [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$TaskPrefix = "AXCaseResearch4"

if (-not $Unregister -and [string]::IsNullOrWhiteSpace($BashExe)) {
  throw "bash.exe not found on PATH. Install Git for Windows, or pass -BashExe 'C:\Program Files\Git\bin\bash.exe'."
}

$LogDir = Join-Path $ProjectRoot "schedule\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# name -> { script args; trigger }
$Tasks = @(
  @{ Name = "$TaskPrefix-NewsMonitor";        Args = "discover.sh --news-only";     Log = "news.log";               Trigger = (New-ScheduledTaskTrigger -Once (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 12) -RepetitionDuration ([TimeSpan]::MaxValue)) }
  @{ Name = "$TaskPrefix-EvergreenRefresh";   Args = "refresh.sh";                  Log = "refresh.log";            Trigger = (New-ScheduledTaskTrigger -Daily -At "3:00AM") }
  @{ Name = "$TaskPrefix-CommunityDiscovery"; Args = "run_stage1.sh state/monthly_discovery_case_db.json"; Log = "community_discovery.log"; Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "4:00AM") } # monthly cadence enforced inside the pipeline's own staleness checks; weekly trigger just checks in
  @{ Name = "$TaskPrefix-CategoryDiscovery";  Args = "discover.sh --category-only"; Log = "category.log";           Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "5:00AM") }
  @{ Name = "$TaskPrefix-SeedingHealth";      Args = "calibrate_seeding.sh";        Log = "seeding_health.log";     Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "6:00AM") }
)

if ($Unregister) {
  foreach ($t in $Tasks) {
    if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
      Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false
      Write-Host "Removed task: $($t.Name)"
    } else {
      Write-Host "Not found (skipped): $($t.Name)"
    }
  }
  return
}

Write-Host "Project root: $ProjectRoot"
Write-Host "bash.exe:     $BashExe"
Write-Host ""

foreach ($t in $Tasks) {
  $bashCmd = "cd '$ProjectRoot' && bash $($t.Args) >> 'schedule/logs/$($t.Log)' 2>&1"
  $action = New-ScheduledTaskAction -Execute $BashExe -Argument "-lc `"$bashCmd`"" -WorkingDirectory $ProjectRoot
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2)

  Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $t.Trigger -Settings $settings -Force | Out-Null
  Write-Host "Registered: $($t.Name)  ->  bash $($t.Args)"
}

Write-Host ""
Write-Host "Note: Tier 6 (full corpus recalibration / deck rebuild) is deliberately NOT scheduled - run it manually per lecture engagement:"
Write-Host "  bash run_pipeline.sh   (FROM_STAGE=2, EXISTING_CASE_DB=state/ax_case_db.json in pipeline.config.sh)"
Write-Host ""
Write-Host "To remove everything registered here: .\register_windows_tasks.ps1 -Unregister"
