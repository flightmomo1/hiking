param()

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\mountain_work\115_osm"
$RouteFolder = "qixing_lengshuikeng"
$ActivityId = "37_1"
$CaseId = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"

$SequenceCsv = Join-Path $ProjectRoot "outputs\ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c\$RouteFolder\37_1_mapmatched.csv"
$LabeledCsv = Join-Path $ProjectRoot "outputs\ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c\$RouteFolder\qixing_lengshuikeng_37_1_mapmatched_activity_labeled.csv"
$OnRouteCsv = Join-Path $ProjectRoot "outputs\ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c\$RouteFolder\qixing_lengshuikeng_37_1_mapmatched_activity_on_route.csv"
$ExcursionsCsv = Join-Path $ProjectRoot "outputs\ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c\$RouteFolder\qixing_lengshuikeng_37_1_mapmatched_activity_excursions.csv"

$OutRoot = Join-Path $ProjectRoot "outputs\ib3_v1_3b_thci_v1_0c_smoke_audit"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
$AuditCsv = Join-Path $OutRoot "ib3_qixing_lengshuikeng_37_1_smoke_audit.csv"
$DecisionCsv = Join-Path $OutRoot "ib3_qixing_lengshuikeng_37_1_smoke_decision.csv"

function Read-CsvRows($Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    return @()
  }
  return @(Import-Csv -LiteralPath $Path -Encoding UTF8)
}

function Get-Columns($Rows) {
  if ($Rows.Count -eq 0) {
    return @()
  }
  return @($Rows[0].PSObject.Properties.Name)
}

function To-DoubleOrNull($Value) {
  $number = 0.0
  $text = [string]$Value
  if ([double]::TryParse($text, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
    return $number
  }
  return $null
}

function Count-ByValue($Rows, $Column) {
  if ($Rows.Count -eq 0) {
    return @{}
  }
  $counts = [ordered]@{}
  foreach ($row in $Rows) {
    $value = [string]$row.$Column
    if ([string]::IsNullOrWhiteSpace($value)) {
      $value = "<blank>"
    }
    if (-not $counts.Contains($value)) {
      $counts[$value] = 0
    }
    $counts[$value] += 1
  }
  return $counts
}

function Format-Counts($Counts) {
  if ($Counts.Count -eq 0) {
    return ""
  }
  return (($Counts.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "; ")
}

$BlockingIssues = New-Object System.Collections.Generic.List[string]

$SequenceExists = Test-Path -LiteralPath $SequenceCsv
$LabeledExists = Test-Path -LiteralPath $LabeledCsv
$OnRouteExists = Test-Path -LiteralPath $OnRouteCsv
$ExcursionsExists = Test-Path -LiteralPath $ExcursionsCsv

if (-not $SequenceExists) { $BlockingIssues.Add("missing_sequence_csv") }
if (-not $LabeledExists) { $BlockingIssues.Add("missing_labeled_csv") }
if (-not $OnRouteExists) { $BlockingIssues.Add("missing_on_route_csv") }
if (-not $ExcursionsExists) { $BlockingIssues.Add("missing_excursions_csv") }

$SequenceRowsData = Read-CsvRows $SequenceCsv
$LabeledRowsData = Read-CsvRows $LabeledCsv
$OnRouteRowsData = Read-CsvRows $OnRouteCsv
$ExcursionsRowsData = Read-CsvRows $ExcursionsCsv

$SequenceRows = $SequenceRowsData.Count
$LabeledRows = $LabeledRowsData.Count
$OnRouteRows = $OnRouteRowsData.Count
$ExcursionsRows = $ExcursionsRowsData.Count

if ($SequenceRows -le 0) { $BlockingIssues.Add("sequence_rows_not_positive") }
if ($LabeledRows -le 0) { $BlockingIssues.Add("labeled_rows_not_positive") }
if ($OnRouteRows -le 0) { $BlockingIssues.Add("on_route_rows_not_positive") }

$SequenceColumns = Get-Columns $SequenceRowsData
$LabeledColumns = Get-Columns $LabeledRowsData

$RequiredSequenceColumns = @(
  "route_dist_m",
  "reliable_route_dist_m",
  "candidate_phase",
  "summit_reached_flag",
  "summit_transition_lock_applied",
  "summit_transition_release_flag"
)

foreach ($column in $RequiredSequenceColumns) {
  if ($SequenceColumns -notcontains $column) {
    $BlockingIssues.Add("missing_sequence_column_$column")
  }
}

if ($LabeledColumns -notcontains "route_progress_state") {
  $BlockingIssues.Add("missing_labeled_column_route_progress_state")
}

$RouteDistValues = @()
if ($SequenceColumns -contains "route_dist_m") {
  foreach ($row in $SequenceRowsData) {
    $value = To-DoubleOrNull $row.route_dist_m
    if ($null -ne $value) {
      $RouteDistValues += $value
    }
  }
}

$RouteDistMin = if ($RouteDistValues.Count -gt 0) { ($RouteDistValues | Measure-Object -Minimum).Minimum } else { $null }
$RouteDistMax = if ($RouteDistValues.Count -gt 0) { ($RouteDistValues | Measure-Object -Maximum).Maximum } else { $null }

if ($null -eq $RouteDistMax -or $RouteDistMax -lt 4000.0) {
  $BlockingIssues.Add("route_dist_m_max_lt_4000")
}

$CandidatePhaseCounts = Count-ByValue $SequenceRowsData "candidate_phase"
$RouteProgressStateCounts = Count-ByValue $LabeledRowsData "route_progress_state"
$SummitReleaseCounts = Count-ByValue $SequenceRowsData "summit_transition_release_flag"

$CandidatePhases = @($CandidatePhaseCounts.Keys)
$IncludesDescent = $CandidatePhases -contains "descent"
$IncludesAscent = $CandidatePhases -contains "ascent"
$IncludesSummitSelfNear = $CandidatePhases -contains "summit_self_near"
$DescentPhasePreserved = $IncludesDescent

if (-not $IncludesDescent) { $BlockingIssues.Add("candidate_phase_missing_descent") }
if (-not $IncludesAscent) { $BlockingIssues.Add("candidate_phase_missing_ascent") }
if (-not $IncludesSummitSelfNear) { $BlockingIssues.Add("candidate_phase_missing_summit_self_near") }

$OnRouteReliableRows = 0
if ($RouteProgressStateCounts.Contains("on_route_reliable")) {
  $OnRouteReliableRows = [int]$RouteProgressStateCounts["on_route_reliable"]
}
if ($OnRouteReliableRows -le 0) {
  $BlockingIssues.Add("on_route_reliable_rows_not_positive")
}

$BranchAmbiguousRows = 0
if ($RouteProgressStateCounts.Contains("branch_ambiguous_projection")) {
  $BranchAmbiguousRows = [int]$RouteProgressStateCounts["branch_ambiguous_projection"]
}

$NonUsableRows = [Math]::Max(0, $LabeledRows - $OnRouteRows)
$SummitReleaseTriggered = $false
foreach ($key in $SummitReleaseCounts.Keys) {
  if ([string]$key -match "^(True|true|1)$" -and [int]$SummitReleaseCounts[$key] -gt 0) {
    $SummitReleaseTriggered = $true
  }
}

$FinalStatus = if ($BlockingIssues.Count -eq 0) { "PASS" } else { "FAIL" }
$BlockingIssueText = if ($BlockingIssues.Count -eq 0) { "" } else { ($BlockingIssues -join "|") }

$AuditRow = [pscustomobject]@{
  route_folder = $RouteFolder
  activity_id = $ActivityId
  case_id = $CaseId
  sequence_csv = $SequenceCsv
  labeled_csv = $LabeledCsv
  on_route_csv = $OnRouteCsv
  excursions_csv = $ExcursionsCsv
  sequence_csv_exists = $SequenceExists
  labeled_csv_exists = $LabeledExists
  on_route_csv_exists = $OnRouteExists
  excursions_csv_exists = $ExcursionsExists
  sequence_rows = $SequenceRows
  labeled_rows = $LabeledRows
  on_route_rows = $OnRouteRows
  non_usable_rows = $NonUsableRows
  excursions_rows = $ExcursionsRows
  route_dist_min_m = $RouteDistMin
  route_dist_max_m = $RouteDistMax
  route_dist_m_exists = ($SequenceColumns -contains "route_dist_m")
  reliable_route_dist_m_exists = ($SequenceColumns -contains "reliable_route_dist_m")
  candidate_phase_exists = ($SequenceColumns -contains "candidate_phase")
  summit_reached_flag_exists = ($SequenceColumns -contains "summit_reached_flag")
  summit_transition_lock_applied_exists = ($SequenceColumns -contains "summit_transition_lock_applied")
  summit_transition_release_flag_exists = ($SequenceColumns -contains "summit_transition_release_flag")
  candidate_phase_counts = Format-Counts $CandidatePhaseCounts
  route_progress_state_counts = Format-Counts $RouteProgressStateCounts
  candidate_phase_includes_descent = $IncludesDescent
  candidate_phase_includes_ascent = $IncludesAscent
  candidate_phase_includes_summit_self_near = $IncludesSummitSelfNear
  descent_phase_preserved = $DescentPhasePreserved
  on_route_reliable_rows = $OnRouteReliableRows
  branch_ambiguous_projection_rows = $BranchAmbiguousRows
  summit_release_flag_triggered = $SummitReleaseTriggered
  blocking_issue = $BlockingIssueText
  audit_status = $FinalStatus
}

$AuditRow | Export-Csv -LiteralPath $AuditCsv -Encoding UTF8 -NoTypeInformation

$DecisionRow = [pscustomobject]@{
  IB3_QIXING_LENGSHUIKENG_V1_3B_THCI_V1_0C_SMOKE_STATUS = $FinalStatus
  route_folder = $RouteFolder
  activity_id = $ActivityId
  case_id = $CaseId
  sequence_rows = $SequenceRows
  labeled_rows = $LabeledRows
  on_route_rows = $OnRouteRows
  route_dist_max_m = $RouteDistMax
  descent_phase_preserved = $DescentPhasePreserved
  summit_release_flag_triggered = $SummitReleaseTriggered
  blocking_issue = $BlockingIssueText
  audit_csv = $AuditCsv
}
$DecisionRow | Export-Csv -LiteralPath $DecisionCsv -Encoding UTF8 -NoTypeInformation

Write-Host "sequence_rows=$SequenceRows"
Write-Host "labeled_rows=$LabeledRows"
Write-Host "on_route_rows=$OnRouteRows"
Write-Host "non_usable_rows=$NonUsableRows"
Write-Host "excursions_rows=$ExcursionsRows"
Write-Host "route_dist_min_m=$RouteDistMin"
Write-Host "route_dist_max_m=$RouteDistMax"
Write-Host "candidate_phase_counts=$(Format-Counts $CandidatePhaseCounts)"
Write-Host "route_progress_state_counts=$(Format-Counts $RouteProgressStateCounts)"
Write-Host "descent_phase_preserved=$DescentPhasePreserved"
Write-Host "summit_release_flag_triggered=$SummitReleaseTriggered"
Write-Host "blocking_issue=$BlockingIssueText"
Write-Host "final decision: IB3_QIXING_LENGSHUIKENG_V1_3B_THCI_V1_0C_SMOKE_STATUS=$FinalStatus"
