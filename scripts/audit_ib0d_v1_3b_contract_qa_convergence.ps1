cd "C:\mountain_work\115_osm"

# =========================================================
# IB0D v1.3b control-points-only contract QA convergence audit
# reviewed convergence audit / PASS + accepted WARN gate
# =========================================================

$root = ".\outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
$summaryAll = Join-Path $root "ib0d_v1_3b_contract_qa_summary_all.csv"

$outDir = ".\outputs\ib0_route_axis_v1_3b_convergence_audit"
$outCsv = Join-Path $outDir "ib0d_v1_3b_contract_qa_convergence_audit.csv"

New-Item -ItemType Directory -Force $outDir | Out-Null

if (-not (Test-Path $summaryAll)) {
  throw "MISSING IB0D summary_all CSV: $summaryAll"
}

$cases = @(
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"
)

$aggregate = @(Import-Csv $summaryAll)

$rows = foreach ($caseId in $cases) {
  $caseDir = Join-Path $root $caseId
  $caseDirExists = Test-Path $caseDir

  $agg = $aggregate |
    Where-Object { $_.case_id -eq $caseId } |
    Select-Object -First 1

  $routePoints       = Join-Path $caseDir "route_points.csv"
  $trimmedGeojson    = Join-Path $caseDir "mainline_ordered_path_trimmed.geojson"
  $trimSummary       = Join-Path $caseDir "trim_summary.csv"
  $controlProjection = Join-Path $caseDir "control_point_projection.csv"
  $selfNearPairs     = Join-Path $caseDir "self_near_pairs.csv"
  $selfNearZones     = Join-Path $caseDir "self_near_zones.csv"

  $qaSummaryExists = if ($caseDirExists) {
    @(Get-ChildItem $caseDir -File -Filter "*qa_summary*" -ErrorAction SilentlyContinue).Count -gt 0
  } else {
    $false
  }

  $qaMapExists = if ($caseDirExists) {
    @(Get-ChildItem $caseDir -File -Filter "*qa*map*.html" -ErrorAction SilentlyContinue).Count -gt 0
  } else {
    $false
  }

  $status = if ($agg) {
    "$($agg.status)".Trim()
  } else {
    ""
  }

  $safeForIb1Raw = if ($agg) {
    "$($agg.safe_for_ib1a_ib1c_ib1g_ib1e)".Trim()
  } else {
    ""
  }

  $safeForIb1Bool = $safeForIb1Raw -in @("True", "true", "TRUE", "1", "Yes", "yes", "YES")

  $unexpectedSelfNear = if ($agg -and "$($agg.unexpected_self_near_pair_count)".Trim() -ne "") {
    [int]$agg.unexpected_self_near_pair_count
  } else {
    -1
  }

  $hardFailReasons = if ($agg) {
    "$($agg.hard_fail_reasons)".Trim()
  } else {
    "missing_aggregate_row"
  }

  $routePointsExists       = Test-Path $routePoints
  $trimmedGeojsonExists    = Test-Path $trimmedGeojson
  $trimSummaryExists       = Test-Path $trimSummary
  $controlProjectionExists = Test-Path $controlProjection
  $selfNearPairsExists     = Test-Path $selfNearPairs
  $selfNearZonesExists     = Test-Path $selfNearZones

  $filesOk =
    $caseDirExists -and
    $routePointsExists -and
    $trimmedGeojsonExists -and
    $trimSummaryExists -and
    $controlProjectionExists -and
    $selfNearPairsExists -and
    $selfNearZonesExists -and
    $qaSummaryExists -and
    $qaMapExists

  $reviewedStatus = if (-not $agg) {
    "FAIL_missing_aggregate_row"
  } elseif (-not $filesOk) {
    "FAIL_missing_case_files"
  } elseif ($status -eq "FAIL") {
    "FAIL_aggregate_status"
  } elseif (-not $safeForIb1Bool) {
    "FAIL_not_safe_for_ib1"
  } elseif ($unexpectedSelfNear -ne 0) {
    "FAIL_unexpected_self_near"
  } elseif ($hardFailReasons -ne "") {
    "FAIL_hard_fail_reasons"
  } elseif ($status -eq "PASS") {
    "PASS"
  } elseif ($status -eq "WARN") {
    "WARN_ACCEPTED"
  } else {
    "FAIL_unknown_status"
  }

  [pscustomobject]@{
    case_id = $caseId
    reviewed_status = $reviewedStatus
    aggregate_status = $status

    case_dir_exists = $caseDirExists
    route_points_exists = $routePointsExists
    trimmed_geojson_exists = $trimmedGeojsonExists
    trim_summary_exists = $trimSummaryExists
    qa_summary_exists = $qaSummaryExists
    qa_map_exists = $qaMapExists
    control_point_projection_exists = $controlProjectionExists
    self_near_pairs_exists = $selfNearPairsExists
    self_near_zones_exists = $selfNearZonesExists

    safe_for_ib1a_ib1c_ib1g_ib1e = $safeForIb1Raw
    safe_for_ib1_bool = $safeForIb1Bool

    self_near_pair_count = if ($agg) { $agg.self_near_pair_count } else { "" }
    expected_self_near_pair_count = if ($agg) { $agg.expected_self_near_pair_count } else { "" }
    unexpected_self_near_pair_count = $unexpectedSelfNear

    trim_mode = if ($agg) { $agg.trim_mode } else { "" }
    warnings = if ($agg) { $agg.warnings } else { "" }
    hard_fail_reasons = $hardFailReasons
  }
}

$rows |
  Export-Csv $outCsv `
    -NoTypeInformation `
    -Encoding UTF8

Write-Host "--- IB0D convergence audit ---"

$rows |
  Select-Object `
    case_id,
    reviewed_status,
    aggregate_status,
    route_points_exists,
    trimmed_geojson_exists,
    trim_summary_exists,
    qa_summary_exists,
    qa_map_exists,
    control_point_projection_exists,
    self_near_pairs_exists,
    self_near_zones_exists,
    safe_for_ib1a_ib1c_ib1g_ib1e,
    unexpected_self_near_pair_count,
    trim_mode |
  Format-Table -AutoSize

Write-Host ""
Write-Host "=== IB0D convergence decision ==="

$fail = @($rows | Where-Object { $_.reviewed_status -like "FAIL*" })
$warnAccepted = @($rows | Where-Object { $_.reviewed_status -eq "WARN_ACCEPTED" })
$pass = @($rows | Where-Object { $_.reviewed_status -eq "PASS" })

$decision = [pscustomobject]@{
  cases_n = $rows.Count
  pass_n = $pass.Count
  warn_accepted_n = $warnAccepted.Count
  fail_n = $fail.Count
  ib0d_status = if ($rows.Count -eq 4 -and $fail.Count -eq 0) {
    "CONVERGED_REVIEWED_PASS_WARN"
  } else {
    "FAIL"
  }
  formal_ib1_input_root = $root
  audit_csv = $outCsv
}

$decision | Format-List

Write-Host "wrote: $outCsv"