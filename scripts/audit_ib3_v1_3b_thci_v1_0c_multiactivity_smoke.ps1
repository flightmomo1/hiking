param()

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\mountain_work\115_osm"
$SequenceRoot = Join-Path $ProjectRoot "outputs\ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c"
$OnRouteRoot = Join-Path $ProjectRoot "outputs\ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c"
$OutRoot = Join-Path $ProjectRoot "outputs\ib3_v1_3b_thci_v1_0c_multiactivity_smoke_audit"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$AuditCsv = Join-Path $OutRoot "ib3_v1_3b_thci_v1_0c_multiactivity_smoke_audit.csv"
$DecisionCsv = Join-Path $OutRoot "ib3_v1_3b_thci_v1_0c_multiactivity_smoke_decision.csv"

$SmokeSet = @(
  [pscustomobject]@{
    route_folder = "qixing_lengshuikeng"
    activity_id = "37_1"
    subject_id = "37"
    trial_id = "1"
    case_id = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
  },
  [pscustomobject]@{
    route_folder = "qixing_lengshuikeng"
    activity_id = "33_1"
    subject_id = "33"
    trial_id = "1"
    case_id = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
  },
  [pscustomobject]@{
    route_folder = "qixing_lengshuikeng"
    activity_id = "15_1"
    subject_id = "15"
    trial_id = "1"
    case_id = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
  },
  [pscustomobject]@{
    route_folder = "juansi_waterfall"
    activity_id = "37_1"
    subject_id = "37"
    trial_id = "1"
    case_id = "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b"
  },
  [pscustomobject]@{
    route_folder = "juansi_waterfall"
    activity_id = "20_1"
    subject_id = "20"
    trial_id = "1"
    case_id = "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b"
  }
)

function Read-CsvRows($Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    return ,@()
  }
  return ,@(Import-Csv -LiteralPath $Path -Encoding UTF8)
}

function Get-Columns($Rows) {
  $items = @($Rows)
  if ($items.Count -eq 0) {
    return @()
  }
  return @($items[0].PSObject.Properties.Name)
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
  $counts = [ordered]@{}
  $items = @($Rows)
  if ($items.Count -eq 0) {
    return $counts
  }
  foreach ($row in $items) {
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

function Get-CountValue($Counts, $Key) {
  if ($Counts.Contains($Key)) {
    return [int]$Counts[$Key]
  }
  return 0
}

function Get-MinMax($Rows, $Column) {
  $values = @()
  foreach ($row in @($Rows)) {
    $value = To-DoubleOrNull $row.$Column
    if ($null -ne $value) {
      $values += $value
    }
  }
  if ($values.Count -eq 0) {
    return @{ min = $null; max = $null }
  }
  return @{
    min = ($values | Measure-Object -Minimum).Minimum
    max = ($values | Measure-Object -Maximum).Maximum
  }
}

$Rows = @()

foreach ($item in $SmokeSet) {
  $route = $item.route_folder
  $activity = $item.activity_id
  $sequenceCsv = Join-Path $SequenceRoot "$route\$($activity)_mapmatched.csv"
  $labeledCsv = Join-Path $OnRouteRoot "$route\$($route)_$($activity)_mapmatched_activity_labeled.csv"
  $onRouteCsv = Join-Path $OnRouteRoot "$route\$($route)_$($activity)_mapmatched_activity_on_route.csv"
  $excursionsCsv = Join-Path $OnRouteRoot "$route\$($route)_$($activity)_mapmatched_activity_excursions.csv"

  $sequenceExists = Test-Path -LiteralPath $sequenceCsv
  $labeledExists = Test-Path -LiteralPath $labeledCsv
  $onRouteExists = Test-Path -LiteralPath $onRouteCsv
  $excursionsExists = Test-Path -LiteralPath $excursionsCsv

  $seqRows = Read-CsvRows $sequenceCsv
  $labeledRowsData = Read-CsvRows $labeledCsv
  $onRouteRowsData = Read-CsvRows $onRouteCsv
  $excursionRowsData = Read-CsvRows $excursionsCsv

  $sequenceRows = @($seqRows).Count
  $labeledRows = @($labeledRowsData).Count
  $onRouteRows = @($onRouteRowsData).Count
  $excursionsRows = @($excursionRowsData).Count
  $nonUsableRows = [Math]::Max(0, $labeledRows - $onRouteRows)

  $seqColumns = Get-Columns $seqRows
  $labeledColumns = Get-Columns $labeledRowsData
  $routeDistStats = Get-MinMax $seqRows "route_dist_m"
  $phaseCounts = Count-ByValue $seqRows "candidate_phase"
  $stateCounts = Count-ByValue $labeledRowsData "route_progress_state"
  $releaseCounts = Count-ByValue $seqRows "summit_transition_release_flag"

  $onRouteReliableRows = Get-CountValue $stateCounts "on_route_reliable"
  $offRouteProjectionOnlyRows = Get-CountValue $stateCounts "off_route_projection_only"
  $nearRouteLowConfidenceRows = Get-CountValue $stateCounts "near_route_low_confidence"
  $branchAmbiguousProjectionRows = Get-CountValue $stateCounts "branch_ambiguous_projection"
  $summitSelfNearRows = Get-CountValue $phaseCounts "summit_self_near"
  $descentPhasePreserved = $phaseCounts.Contains("descent")

  $summitReleaseTriggered = $false
  foreach ($key in $releaseCounts.Keys) {
    if ([string]$key -match "^(True|true|1)$" -and [int]$releaseCounts[$key] -gt 0) {
      $summitReleaseTriggered = $true
    }
  }

  $issues = New-Object System.Collections.Generic.List[string]
  if (-not $sequenceExists) { $issues.Add("missing_sequence_csv") }
  if (-not $labeledExists) { $issues.Add("missing_labeled_csv") }
  if (-not $onRouteExists) { $issues.Add("missing_on_route_csv") }
  if (-not $excursionsExists) { $issues.Add("missing_excursions_csv") }
  if ($sequenceRows -le 0) { $issues.Add("sequence_rows_not_positive") }
  if ($labeledRows -le 0) { $issues.Add("labeled_rows_not_positive") }
  if ($onRouteRows -le 0) { $issues.Add("on_route_rows_not_positive") }

  foreach ($column in @("route_dist_m", "reliable_route_dist_m", "candidate_phase")) {
    if ($seqColumns -notcontains $column) {
      $issues.Add("missing_sequence_column_$column")
    }
  }
  if ($labeledColumns -notcontains "route_progress_state") {
    $issues.Add("missing_labeled_column_route_progress_state")
  }

  if ($null -eq $routeDistStats.max -or $routeDistStats.max -le 0) {
    $issues.Add("route_dist_max_not_positive")
  }
  if ($onRouteReliableRows -le 0) {
    $issues.Add("on_route_reliable_rows_not_positive")
  }

  if ($route -eq "qixing_lengshuikeng") {
    if ($null -eq $routeDistStats.max -or $routeDistStats.max -lt 4000.0) {
      $issues.Add("qixing_route_dist_max_lt_4000")
    }
    if (-not $descentPhasePreserved) {
      $issues.Add("qixing_descent_phase_not_preserved")
    }
  }
  elseif ($route -eq "juansi_waterfall") {
    if ($null -eq $routeDistStats.max -or $routeDistStats.max -lt 3600.0) {
      $issues.Add("juansi_route_dist_max_lt_3600")
    }
    if (-not ($phaseCounts.Contains("ascent") -or $phaseCounts.Contains("descent"))) {
      $issues.Add("juansi_missing_ascent_or_descent_phase")
    }
  }

  $blockingIssue = if ($issues.Count -eq 0) { "" } else { ($issues -join "|") }
  $status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }

  $Rows += [pscustomobject]@{
    route_folder = $route
    case_id = $item.case_id
    activity_id = $activity
    subject_id = $item.subject_id
    trial_id = $item.trial_id
    sequence_csv_exists = $sequenceExists
    labeled_csv_exists = $labeledExists
    on_route_csv_exists = $onRouteExists
    excursions_csv_exists = $excursionsExists
    sequence_rows = $sequenceRows
    labeled_rows = $labeledRows
    on_route_rows = $onRouteRows
    non_usable_rows = $nonUsableRows
    excursions_rows = $excursionsRows
    route_dist_min_m = $routeDistStats.min
    route_dist_max_m = $routeDistStats.max
    on_route_reliable_rows = $onRouteReliableRows
    off_route_projection_only_rows = $offRouteProjectionOnlyRows
    near_route_low_confidence_rows = $nearRouteLowConfidenceRows
    branch_ambiguous_projection_rows = $branchAmbiguousProjectionRows
    candidate_phase_counts = Format-Counts $phaseCounts
    route_progress_state_counts = Format-Counts $stateCounts
    descent_phase_preserved = $descentPhasePreserved
    summit_self_near_rows = $summitSelfNearRows
    summit_release_flag_triggered = $summitReleaseTriggered
    blocking_issue = $blockingIssue
    activity_smoke_status = $status
  }
}

$Rows | Export-Csv -LiteralPath $AuditCsv -Encoding UTF8 -NoTypeInformation

$casesN = $Rows.Count
$passN = @($Rows | Where-Object { $_.activity_smoke_status -eq "PASS" }).Count
$failN = @($Rows | Where-Object { $_.activity_smoke_status -ne "PASS" }).Count
$routeFoldersN = @($Rows | Select-Object -ExpandProperty route_folder -Unique).Count
$qixingRows = @($Rows | Where-Object { $_.route_folder -eq "qixing_lengshuikeng" })
$juansiRows = @($Rows | Where-Object { $_.route_folder -eq "juansi_waterfall" })
$qixingDescentPreservedAll = (($qixingRows | Where-Object { $_.descent_phase_preserved -ne $true }).Count -eq 0)
$juansiOnRouteReliableAll = (($juansiRows | Where-Object { [int]$_.on_route_reliable_rows -le 0 }).Count -eq 0)
$finalStatus = if ($failN -eq 0) { "PASS" } else { "FAIL" }

$DecisionRow = [pscustomobject]@{
  cases_n = $casesN
  pass_n = $passN
  fail_n = $failN
  route_folders_n = $routeFoldersN
  qixing_cases_n = $qixingRows.Count
  juansi_cases_n = $juansiRows.Count
  qixing_descent_preserved_all = $qixingDescentPreservedAll
  juansi_on_route_reliable_all = $juansiOnRouteReliableAll
  ib3_multiactivity_smoke_status = $finalStatus
  sequence_root = $SequenceRoot
  on_route_root = $OnRouteRoot
  audit_csv = $AuditCsv
}
$DecisionRow | Export-Csv -LiteralPath $DecisionCsv -Encoding UTF8 -NoTypeInformation

Write-Host "per-activity summary table:"
$Rows |
  Select-Object route_folder, activity_id, activity_smoke_status, sequence_rows, on_route_rows, excursions_rows, route_dist_max_m, descent_phase_preserved, blocking_issue |
  Format-Table -AutoSize

Write-Host "final decision: IB3_V1_3B_THCI_V1_0C_MULTIACTIVITY_SMOKE_STATUS=$finalStatus"
Write-Host "wrote audit CSV path: $AuditCsv"
Write-Host "wrote decision CSV path: $DecisionCsv"
