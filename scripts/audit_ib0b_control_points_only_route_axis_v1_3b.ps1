cd "C:\mountain_work\115_osm"

$root = ".\outputs\ib0b_mainline_route_definition_v1_3b_control_points_only"
$outDir = ".\outputs\ib0_route_axis_v1_3b_convergence_audit"
$outCsv = Join-Path $outDir "ib0b_control_points_only_route_axis_convergence_audit.csv"

New-Item -ItemType Directory -Force $outDir | Out-Null

$cases = @(
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"
)

$expectedLength = @{
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b" = 4187.392949
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b"  = 3245.056611
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b"       = 3695.539299
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"  = 5447.777653
}

$rows = foreach ($caseId in $cases) {
  $orderedPath = Join-Path $root "$caseId`_mainline_ordered_path_ib0_candidates.geojson"
  $mainline = Join-Path $root "$caseId`_mainline_ib0_candidates.geojson"
  $debugSegments = Join-Path $root "$caseId`_mainline_debug_segments_ib0_candidates.csv"
  $map = Join-Path $root "$caseId`_mainline_map_ib0_candidates.html"
  $summary = Join-Path $root "$caseId`_mainline_summary_ib0_candidates.csv"
  $controlCsv = Join-Path $root "$caseId`_route_definition_control_points_used_ib0_candidates.csv"
  $controlGeojson = Join-Path $root "$caseId`_route_definition_control_points_used_ib0_candidates.geojson"
  $requiredWayQaCsv = Join-Path $root "$caseId`_mainline_required_way_qa_ib0_candidates.csv"
  $requiredWayQaTxt = Join-Path $root "$caseId`_mainline_required_way_qa_ib0_candidates.txt"

  $summaryRows = if (Test-Path $summary) { @(Import-Csv $summary) } else { @() }
  $controlRows = if (Test-Path $controlCsv) { @(Import-Csv $controlCsv) } else { @() }

  $length = $null
  if ($summaryRows.Count -gt 0) {
    $lengthCol = @(
      "ordered_path_length_m",
      "mainline_ordered_path_length_m",
      "length_m"
    ) | Where-Object {
      $summaryRows[0].PSObject.Properties.Name -contains $_
    } | Select-Object -First 1

    if ($lengthCol) {
      $lengthRaw = $summaryRows[0].$lengthCol
      if ($null -ne $lengthRaw -and "$lengthRaw".Trim() -ne "") {
        $length = [double]$lengthRaw
      }
    }
  }

  $expected = [double]$expectedLength[$caseId]
  $lengthDelta = if ($null -ne $length) { [math]::Abs($length - $expected) } else { $null }
  $lengthOk = if ($null -ne $lengthDelta) { $lengthDelta -lt 0.01 } else { $false }

  $requiredFilesOk =
    (Test-Path $orderedPath) -and
    (Test-Path $mainline) -and
    (Test-Path $debugSegments) -and
    (Test-Path $map) -and
    (Test-Path $summary) -and
    (Test-Path $controlCsv) -and
    (Test-Path $controlGeojson)

  $controlDistCol = $null
  $controlDistValues = @()
  $controlDistMonotonic = $false
  $controlStartDistM = $null
  $controlEndDistM = $null
  $controlStartOk = $false
  $controlEndOk = $false

  if ($controlRows.Count -gt 0) {
    $controlDistCol = @(
      "projected_route_dist_m",
      "route_dist_m",
      "dist_m"
    ) | Where-Object {
      $controlRows[0].PSObject.Properties.Name -contains $_
    } | Select-Object -First 1

    if ($controlDistCol) {
      $controlDistValues = @($controlRows | ForEach-Object { [double]$_.$controlDistCol })

      $controlDistMonotonic = $true
      for ($i = 1; $i -lt $controlDistValues.Count; $i++) {
        if ($controlDistValues[$i] -lt $controlDistValues[$i - 1]) {
          $controlDistMonotonic = $false
        }
      }

      $controlStartDistM = $controlDistValues[0]
      $controlEndDistM = $controlDistValues[$controlDistValues.Count - 1]
      $controlStartOk = ([math]::Abs($controlStartDistM - 0.0) -lt 1.0)

      if ($null -eq $length) {
        $controlLengthCol = @(
          "ordered_path_length_m",
          "mainline_ordered_path_length_m",
          "length_m"
        ) | Where-Object {
          $controlRows[0].PSObject.Properties.Name -contains $_
        } | Select-Object -First 1

        if ($controlLengthCol) {
          $controlLengthRaw = $controlRows[0].$controlLengthCol
          if ($null -ne $controlLengthRaw -and "$controlLengthRaw".Trim() -ne "") {
            $length = [double]$controlLengthRaw
          }
        }
      }

      if ($null -ne $length) {
        $controlEndOk = ([math]::Abs($controlEndDistM - $length) -lt 1.0)
      } else {
        $controlEndOk = ([math]::Abs($controlEndDistM - $expected) -lt 1.0)
      }
    }
  }

  if ($null -eq $length -and $null -ne $controlEndDistM) {
    $length = [double]$controlEndDistM
  }

  $lengthDelta = if ($null -ne $length) { [math]::Abs($length - $expected) } else { $null }
  $lengthOk = if ($null -ne $lengthDelta) { $lengthDelta -lt 0.01 } else { $false }

  $requiredWayAllPresentInInput = ""
  $requiredWayAllPresentInMainline = ""
  if ($summaryRows.Count -gt 0) {
    $requiredWayAllPresentInInput = $summaryRows[0].'required_way_all_present_in_input'
    $requiredWayAllPresentInMainline = $summaryRows[0].'required_way_all_present_in_mainline'
  }

  $requiredWayInputOk = if ("$requiredWayAllPresentInInput".Trim() -eq "") {
    $true
  } else {
    "$requiredWayAllPresentInInput".Trim().ToLower() -eq "true"
  }

  $requiredWayMainlineOk = if ("$requiredWayAllPresentInMainline".Trim() -eq "") {
    $true
  } else {
    "$requiredWayAllPresentInMainline".Trim().ToLower() -eq "true"
  }

  $caseStatus = if (-not $requiredFilesOk) {
    "FAIL_missing_required_files"
  } elseif ($null -eq $length) {
    "FAIL_missing_ordered_path_length_m"
  } elseif (-not $lengthOk) {
    "FAIL_length_mismatch"
  } elseif ($controlRows.Count -eq 0) {
    "FAIL_missing_control_points_used"
  } elseif (-not $controlDistCol) {
    "FAIL_missing_control_point_route_distance_column"
  } elseif (-not $controlDistMonotonic) {
    "FAIL_control_point_route_distance_not_monotonic"
  } elseif (-not $controlStartOk) {
    "WARN_control_start_not_near_zero"
  } elseif (-not $controlEndOk) {
    "WARN_control_end_not_near_route_length"
  } elseif (-not $requiredWayInputOk) {
    "FAIL_required_way_missing_from_input"
  } elseif (-not $requiredWayMainlineOk) {
    "FAIL_required_way_missing_from_mainline"
  } else {
    "PASS"
  }

  [pscustomobject]@{
    case_id = $caseId
    required_files_ok = $requiredFilesOk
    ordered_path_exists = Test-Path $orderedPath
    mainline_exists = Test-Path $mainline
    debug_segments_exists = Test-Path $debugSegments
    map_exists = Test-Path $map
    summary_exists = Test-Path $summary
    control_points_csv_exists = Test-Path $controlCsv
    control_points_geojson_exists = Test-Path $controlGeojson
    required_way_qa_csv_exists = Test-Path $requiredWayQaCsv
    required_way_qa_txt_exists = Test-Path $requiredWayQaTxt
    control_points_n = $controlRows.Count
    control_dist_col = $controlDistCol
    control_dist_monotonic = $controlDistMonotonic
    control_start_dist_m = $controlStartDistM
    control_end_dist_m = $controlEndDistM
    control_start_ok = $controlStartOk
    control_end_ok = $controlEndOk
    ordered_path_length_m = $length
    expected_ordered_path_length_m = $expected
    length_delta_m = $lengthDelta
    length_ok = $lengthOk
    required_way_all_present_in_input = $requiredWayAllPresentInInput
    required_way_all_present_in_mainline = $requiredWayAllPresentInMainline
    required_way_input_ok = $requiredWayInputOk
    required_way_mainline_ok = $requiredWayMainlineOk
    ib0b_status = $caseStatus
  }
}

$rows | Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

"--- IB0B convergence audit ---"
$rows |
  Select-Object `
    case_id,
    required_files_ok,
    control_points_n,
    control_dist_monotonic,
    control_start_ok,
    control_end_ok,
    ordered_path_length_m,
    expected_ordered_path_length_m,
    length_delta_m,
    length_ok,
    required_way_mainline_ok,
    ib0b_status |
  Format-Table -AutoSize

"wrote: $outCsv"
