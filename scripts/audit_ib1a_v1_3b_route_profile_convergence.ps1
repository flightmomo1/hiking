cd "C:\mountain_work\115_osm"

# =========================================================
# IB1A v1.3b route profile convergence audit
# formal input : IB0D trimmed mainline contract QA
# formal output: IB1A route profile contract QA
# =========================================================

$ib0dRoot = ".\outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
$ib1aRoot = ".\outputs\ib1_route_profile_v1_3b_contract_qa"

$outDir = ".\outputs\ib1_v1_3b_contract_qa_pipeline_summary"
$outCsv = Join-Path $outDir "ib1a_v1_3b_route_profile_convergence_audit.csv"

New-Item -ItemType Directory -Force $outDir | Out-Null

$cases = @(
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"
)

$rows = foreach ($caseId in $cases) {
  $ib0dCaseDir = Join-Path $ib0dRoot $caseId
  $ib1aCaseDir = Join-Path $ib1aRoot $caseId

  $ib0dRoutePoints = Join-Path $ib0dCaseDir "route_points.csv"
  $ib0dTrimmedGeojson = Join-Path $ib0dCaseDir "mainline_ordered_path_trimmed.geojson"

  $profileCsv = Join-Path $ib1aCaseDir "$caseId`_route_profile.csv"

  $profile = if (Test-Path $profileCsv) {
    @(Import-Csv $profileCsv)
  } else {
    @()
  }

  $cols = if ($profile.Count -gt 0) {
    $profile[0].PSObject.Properties.Name
  } else {
    @()
  }

  $distCol = @(
    "dist_m",
    "route_dist_m",
    "distance_m"
  ) |
    Where-Object { $cols -contains $_ } |
    Select-Object -First 1

  # v1.3b route_profile currently uses ele_smooth / ele_gpx_m.
  # ele_smooth is preferred as the formal profile elevation column.
  $eleCol = @(
    "ele_smooth",
    "ele_m",
    "elevation_m",
    "elev_m",
    "ele_gpx_m",
    "altitude_m",
    "altitude",
    "alt_m",
    "height_m",
    "z_m"
  ) |
    Where-Object { $cols -contains $_ } |
    Select-Object -First 1

  $gainCol = @(
    "cum_gain_m",
    "cumulative_gain_m"
  ) |
    Where-Object { $cols -contains $_ } |
    Select-Object -First 1

  $lossCol = @(
    "cum_loss_m",
    "cumulative_loss_m"
  ) |
    Where-Object { $cols -contains $_ } |
    Select-Object -First 1

  $distValues = if ($distCol) {
    @($profile | ForEach-Object { [double]$_.$distCol })
  } else {
    @()
  }

  $distMin = if ($distValues.Count -gt 0) {
    ($distValues | Measure-Object -Minimum).Minimum
  } else {
    $null
  }

  $distMax = if ($distValues.Count -gt 0) {
    ($distValues | Measure-Object -Maximum).Maximum
  } else {
    $null
  }

  $cumGain = if ($gainCol -and $profile.Count -gt 0) {
    [double]$profile[-1].$gainCol
  } else {
    $null
  }

  $cumLoss = if ($lossCol -and $profile.Count -gt 0) {
    [double]$profile[-1].$lossCol
  } else {
    $null
  }

  $distMonotonic = $true
  for ($i = 1; $i -lt $distValues.Count; $i++) {
    if ($distValues[$i] -lt $distValues[$i - 1]) {
      $distMonotonic = $false
      break
    }
  }

  $blocking = @()

  if (!(Test-Path $ib0dRoutePoints)) {
    $blocking += "missing_ib0d_route_points"
  }

  if (!(Test-Path $ib0dTrimmedGeojson)) {
    $blocking += "missing_ib0d_trimmed_geojson"
  }

  if (!(Test-Path $profileCsv)) {
    $blocking += "missing_ib1a_route_profile_csv"
  }

  if ($profile.Count -le 0) {
    $blocking += "empty_profile"
  }

  if (!$distCol) {
    $blocking += "missing_dist_column"
  }

  if (!$eleCol) {
    $blocking += "missing_elevation_column"
  }

  if (!$gainCol) {
    $blocking += "missing_cum_gain_column"
  }

  if (!$lossCol) {
    $blocking += "missing_cum_loss_column"
  }

  if ($distValues.Count -gt 0 -and !$distMonotonic) {
    $blocking += "dist_not_monotonic"
  }

  if ($null -ne $distMax -and $distMax -le 0) {
    $blocking += "dist_max_not_positive"
  }

  $status = if ($blocking.Count -eq 0) {
    "PASS"
  } else {
    "FAIL"
  }

  [pscustomobject]@{
    case_id = $caseId
    ib1a_status = $status

    ib0d_route_points_exists = Test-Path $ib0dRoutePoints
    ib0d_trimmed_geojson_exists = Test-Path $ib0dTrimmedGeojson
    route_profile_csv_exists = Test-Path $profileCsv

    rows = $profile.Count

    dist_col = $distCol
    elevation_col = $eleCol
    cum_gain_col = $gainCol
    cum_loss_col = $lossCol

    dist_min_m = $distMin
    dist_max_m = $distMax
    dist_monotonic = $distMonotonic

    cum_gain_m = $cumGain
    cum_loss_m = $cumLoss

    blocking_issue = ($blocking -join ";")
  }
}

$rows |
  Export-Csv $outCsv `
    -NoTypeInformation `
    -Encoding UTF8

Write-Host "--- IB1A route profile convergence audit ---"

$rows |
  Select-Object `
    case_id,
    ib1a_status,
    route_profile_csv_exists,
    rows,
    dist_col,
    elevation_col,
    cum_gain_col,
    cum_loss_col,
    dist_min_m,
    dist_max_m,
    dist_monotonic,
    cum_gain_m,
    cum_loss_m,
    blocking_issue |
  Format-Table -AutoSize

Write-Host ""
Write-Host "=== IB1A convergence decision ==="

$fail = @($rows | Where-Object { $_.ib1a_status -ne "PASS" })

$decision = [pscustomobject]@{
  cases_n = $rows.Count
  pass_n = ($rows.Count - $fail.Count)
  fail_n = $fail.Count
  ib1a_status = if ($rows.Count -eq 4 -and $fail.Count -eq 0) {
    "CONVERGED"
  } else {
    "FAIL"
  }
  formal_input_root = $ib0dRoot
  formal_output_root = $ib1aRoot
  audit_csv = $outCsv
}

$decision | Format-List

Write-Host "wrote: $outCsv"
