cd "C:\mountain_work\115_osm"

# =========================================================
# THCI radar v1.0 convergence audit
# Checks radar PNG, plot data CSV, summary JSON, six-axis completeness,
# score range, and runtime LLM boundary.
# =========================================================

$root = ".\outputs\thci_radar_v1_0"
$batchDir = Join-Path $root "_batch_summary"
$caseSummaryCsv = Join-Path $batchDir "thci_radar_v1_0_case_summary.csv"

$outCsv = Join-Path $batchDir "thci_radar_v1_0_convergence_audit.csv"
$outDecisionCsv = Join-Path $batchDir "thci_radar_v1_0_convergence_decision.csv"

New-Item -ItemType Directory -Force $batchDir | Out-Null

$cases = @(
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"
)

$axisOrder = @(
  "physical_difficulty_score",
  "technical_difficulty_score",
  "baseline_hazard_score",
  "navigation_risk_score",
  "support_difficulty_score",
  "weather_impact_score"
)

$caseSummaryExists = Test-Path $caseSummaryCsv

$rows = foreach ($caseId in $cases) {
  $caseDir = Join-Path $root $caseId

  $pngFp = Join-Path $caseDir "$caseId`_thci_radar_v1_0.png"
  $plotDataCsv = Join-Path $caseDir "$caseId`_thci_radar_plot_data_v1_0.csv"
  $summaryJson = Join-Path $caseDir "$caseId`_thci_radar_summary_v1_0.json"

  $caseDirExists = Test-Path $caseDir
  $pngExists = Test-Path $pngFp
  $plotDataExists = Test-Path $plotDataCsv
  $summaryJsonExists = Test-Path $summaryJson

  $issues = @()
  $missingAxes = @()
  $outOfRangeAxes = @()
  $nonNumericAxes = @()

  $axisCount = 0
  $scoreMin = $null
  $scoreMax = $null
  $runtimeLlmAllowed = ""
  $summaryHasAxisOrder = $false
  $summaryHasAxisScores = $false
  $summaryRadarStatus = ""

  if (-not $caseDirExists) {
    $issues += "missing_case_dir"
  }

  if (-not $pngExists) {
    $issues += "missing_png"
  }

  if (-not $plotDataExists) {
    $issues += "missing_plot_data_csv"
  }

  if (-not $summaryJsonExists) {
    $issues += "missing_summary_json"
  }

  $plotRows = @()
  if ($plotDataExists) {
    $plotRows = @(Import-Csv $plotDataCsv)
  }

  if ($plotDataExists -and $plotRows.Count -le 0) {
    $issues += "empty_plot_data_csv"
  }

  if ($plotRows.Count -gt 0) {
    $cols = @($plotRows[0].PSObject.Properties.Name)

    $axisCol = @("axis_id", "axis", "score_axis") |
      Where-Object { $cols -contains $_ } |
      Select-Object -First 1

    $scoreCol = @("score", "axis_score", "value") |
      Where-Object { $cols -contains $_ } |
      Select-Object -First 1

    if (-not $axisCol) {
      $issues += "missing_axis_column_in_plot_data"
    }

    if (-not $scoreCol) {
      $issues += "missing_score_column_in_plot_data"
    }

    if ($axisCol -and $scoreCol) {
      $axisCount = ($plotRows | ForEach-Object { $_.$axisCol } | Sort-Object -Unique).Count

      foreach ($axis in $axisOrder) {
        $match = $plotRows | Where-Object { "$($_.$axisCol)".Trim() -eq $axis } | Select-Object -First 1

        if (-not $match) {
          $missingAxes += $axis
          continue
        }

        $scoreOk = $true
        $score = $null

        try {
          $score = [double]$match.$scoreCol
        } catch {
          $scoreOk = $false
        }

        if (-not $scoreOk) {
          $nonNumericAxes += $axis
        } elseif ($score -lt 0 -or $score -gt 1) {
          $outOfRangeAxes += $axis
        }
      }

      $scores = @()
      foreach ($r in $plotRows) {
        try {
          $scores += [double]$r.$scoreCol
        } catch {
        }
      }

      if ($scores.Count -gt 0) {
        $scoreMin = ($scores | Measure-Object -Minimum).Minimum
        $scoreMax = ($scores | Measure-Object -Maximum).Maximum
      }
    }
  }

  if ($summaryJsonExists) {
    try {
      $summary = Get-Content $summaryJson -Raw -Encoding UTF8 | ConvertFrom-Json

      $summaryRadarStatus = if ($summary.PSObject.Properties.Name -contains "radar_status") {
        "$($summary.radar_status)"
      } else {
        ""
      }

      $summaryHasAxisOrder = $summary.PSObject.Properties.Name -contains "axis_order"
      $summaryHasAxisScores = $summary.PSObject.Properties.Name -contains "axis_scores"

      if ($summary.PSObject.Properties.Name -contains "runtime_llm_allowed") {
        $runtimeLlmAllowed = "$($summary.runtime_llm_allowed)"
      } else {
        $runtimeLlmAllowed = "missing"
      }

      if (-not $summaryHasAxisOrder) {
        $issues += "summary_missing_axis_order"
      }

      if (-not $summaryHasAxisScores) {
        $issues += "summary_missing_axis_scores"
      }

      if ($runtimeLlmAllowed.ToLower() -ne "false") {
        $issues += "runtime_llm_allowed_not_false"
      }

      if ($summaryRadarStatus -eq "FAIL") {
        $issues += "summary_radar_status_fail"
      }
    } catch {
      $issues += "summary_json_parse_failed"
    }
  }

  if ($missingAxes.Count -gt 0) {
    $issues += "missing_axes"
  }

  if ($nonNumericAxes.Count -gt 0) {
    $issues += "non_numeric_axes"
  }

  if ($outOfRangeAxes.Count -gt 0) {
    $issues += "out_of_range_axes"
  }

  if ($axisCount -ne 6) {
    $issues += "axis_count_not_6"
  }

  $caseStatus = if ($issues.Count -eq 0) {
    "PASS"
  } else {
    "FAIL"
  }

  [pscustomobject]@{
    case_id = $caseId
    case_status = $caseStatus
    case_dir_exists = $caseDirExists
    png_exists = $pngExists
    plot_data_exists = $plotDataExists
    summary_json_exists = $summaryJsonExists
    case_summary_csv_exists = $caseSummaryExists

    axis_count = $axisCount
    six_axis_complete = ($missingAxes.Count -eq 0 -and $axisCount -eq 6)
    score_min = $scoreMin
    score_max = $scoreMax
    score_range_ok = ($nonNumericAxes.Count -eq 0 -and $outOfRangeAxes.Count -eq 0)

    summary_has_axis_order = $summaryHasAxisOrder
    summary_has_axis_scores = $summaryHasAxisScores
    runtime_llm_allowed = $runtimeLlmAllowed
    summary_radar_status = $summaryRadarStatus

    missing_axes = ($missingAxes -join ";")
    non_numeric_axes = ($nonNumericAxes -join ";")
    out_of_range_axes = ($outOfRangeAxes -join ";")
    blocking_issue = ($issues -join ";")

    output_png = $pngFp
    plot_data_csv = $plotDataCsv
    summary_json = $summaryJson
  }
}

$rows |
  Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

$fail = @($rows | Where-Object { $_.case_status -ne "PASS" })

$decision = [pscustomobject]@{
  cases_n = $rows.Count
  pass_n = ($rows.Count - $fail.Count)
  fail_n = $fail.Count
  case_summary_csv_exists = $caseSummaryExists
  thci_radar_status = if ($rows.Count -eq 4 -and $fail.Count -eq 0 -and $caseSummaryExists) {
    "CONVERGED"
  } else {
    "FAIL"
  }
  formal_input_root = ".\outputs\thci_axis_scores_v1_0"
  formal_output_root = $root
  audit_csv = $outCsv
  decision_csv = $outDecisionCsv
}

$decision |
  Export-Csv $outDecisionCsv -NoTypeInformation -Encoding UTF8

Write-Host "--- THCI radar v1.0 convergence audit ---"

$rows |
  Select-Object `
    case_id,
    case_status,
    png_exists,
    plot_data_exists,
    summary_json_exists,
    axis_count,
    six_axis_complete,
    score_min,
    score_max,
    score_range_ok,
    runtime_llm_allowed,
    blocking_issue |
  Format-Table -AutoSize

Write-Host ""
Write-Host "=== THCI radar convergence decision ==="
$decision | Format-List

Write-Host "wrote: $outCsv"
Write-Host "wrote: $outDecisionCsv"