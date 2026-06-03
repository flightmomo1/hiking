param(
    [string]$ProjectRoot = "C:\mountain_work\115_osm"
)

$ErrorActionPreference = "Stop"

$caseIds = @(
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

$radarRoot = Join-Path $ProjectRoot "outputs\thci_radar_v1_0b"
$axisScoreRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0b"
$batchDir = Join-Path $radarRoot "_batch_summary"
$caseSummaryCsv = Join-Path $batchDir "thci_radar_v1_0b_case_summary.csv"
$auditFp = Join-Path $batchDir "thci_radar_v1_0b_convergence_audit.csv"
$decisionFp = Join-Path $batchDir "thci_radar_v1_0b_convergence_decision.csv"

New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

function Test-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name
    )
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Test-Truthy {
    param($Value)
    return ([string]$Value).Trim().ToLowerInvariant() -in @("true", "1", "yes", "y")
}

function Test-Falsey {
    param($Value)
    return ([string]$Value).Trim().ToLowerInvariant() -in @("false", "0", "no")
}

function Convert-ToInvariantDouble {
    param(
        $Value,
        [ref]$OutValue
    )
    $num = 0.0
    $ok = [double]::TryParse(
        [string]$Value,
        [System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$num
    )
    if ($ok) {
        $OutValue.Value = $num
    }
    return $ok
}

$caseSummaryExists = Test-Path -LiteralPath $caseSummaryCsv -PathType Leaf
$caseSummaryRows = @()
if ($caseSummaryExists) {
    $caseSummaryRows = @(Import-Csv -LiteralPath $caseSummaryCsv)
}

$rows = @()

foreach ($caseId in $caseIds) {
    $caseDir = Join-Path $radarRoot $caseId
    $axisScoreCaseDir = Join-Path $axisScoreRoot $caseId
    $pngFp = Join-Path $caseDir "${caseId}_thci_radar_v1_0b.png"
    $plotDataCsv = Join-Path $caseDir "${caseId}_thci_radar_plot_data_v1_0b.csv"
    $summaryJson = Join-Path $caseDir "${caseId}_thci_radar_summary_v1_0b.json"
    $axisScoreCsv = Join-Path $axisScoreCaseDir "${caseId}_thci_axis_scores_v1_0b.csv"

    $pngExists = Test-Path -LiteralPath $pngFp -PathType Leaf
    $plotDataExists = Test-Path -LiteralPath $plotDataCsv -PathType Leaf
    $summaryJsonExists = Test-Path -LiteralPath $summaryJson -PathType Leaf
    $axisScoreCsvExists = Test-Path -LiteralPath $axisScoreCsv -PathType Leaf

    $blockingIssues = New-Object System.Collections.Generic.List[string]
    $missingAxes = New-Object System.Collections.Generic.List[string]
    $nonNumericAxes = New-Object System.Collections.Generic.List[string]
    $outOfRangeAxes = New-Object System.Collections.Generic.List[string]

    $axisCount = 0
    $sixAxisComplete = $false
    $sixAxisNumeric = $false
    $scoreRangeOk = $false
    $scoreMin = $null
    $scoreMax = $null
    $scoringVersion = ""
    $calibratedFromV10a = $false
    $navigationSemanticsCalibrated = $false
    $runtimeLlmAllowedOk = $false
    $previousV10aNavigationRiskScore = $null
    $v10bNavigationRiskScore = $null
    $proxyFeaturesN = 0
    $missingFeaturesN = 0
    $caseSummaryRadarStatus = ""

    if (-not $pngExists) { $blockingIssues.Add("PNG missing") }
    if (-not $plotDataExists) { $blockingIssues.Add("plot data CSV missing") }
    if (-not $summaryJsonExists) { $blockingIssues.Add("summary JSON missing") }
    if (-not $caseSummaryExists) { $blockingIssues.Add("case summary CSV missing") }
    if (-not $axisScoreCsvExists) { $blockingIssues.Add("source v1.0b axis score CSV missing") }

    if ($caseSummaryExists) {
        $caseSummaryMatch = $caseSummaryRows | Where-Object { $_.case_id -eq $caseId } | Select-Object -First 1
        if ($null -eq $caseSummaryMatch) {
            $blockingIssues.Add("case missing from batch summary")
        }
        else {
            $caseSummaryRadarStatus = [string]$caseSummaryMatch.radar_status
            if ($caseSummaryRadarStatus -ne "PASS") {
                $blockingIssues.Add("batch summary radar_status is not PASS")
            }
        }
    }

    if ($plotDataExists) {
        $plotRows = @(Import-Csv -LiteralPath $plotDataCsv)
        if ($plotRows.Count -eq 0) {
            $blockingIssues.Add("plot data CSV empty")
        }
        else {
            $cols = @($plotRows[0].PSObject.Properties.Name)
            $axisCol = @("axis_id", "axis", "score_axis") |
                Where-Object { $cols -contains $_ } |
                Select-Object -First 1
            $scoreCol = @("score", "axis_score", "value") |
                Where-Object { $cols -contains $_ } |
                Select-Object -First 1

            if (-not $axisCol) { $blockingIssues.Add("plot data missing axis column") }
            if (-not $scoreCol) { $blockingIssues.Add("plot data missing score column") }

            if ($axisCol -and $scoreCol) {
                $axisCount = ($plotRows | ForEach-Object { $_.$axisCol } | Sort-Object -Unique).Count
                $scores = @()

                foreach ($axis in $axisOrder) {
                    $match = $plotRows | Where-Object { "$($_.$axisCol)".Trim() -eq $axis } | Select-Object -First 1
                    if ($null -eq $match) {
                        $missingAxes.Add($axis)
                        continue
                    }

                    $scoreRef = [ref]0.0
                    if (-not (Convert-ToInvariantDouble -Value $match.$scoreCol -OutValue $scoreRef)) {
                        $nonNumericAxes.Add($axis)
                        continue
                    }

                    $score = $scoreRef.Value
                    $scores += $score
                    if ($score -lt 0.0 -or $score -gt 1.0) {
                        $outOfRangeAxes.Add($axis)
                    }
                }

                if ($scores.Count -gt 0) {
                    $scoreMin = ($scores | Measure-Object -Minimum).Minimum
                    $scoreMax = ($scores | Measure-Object -Maximum).Maximum
                }
            }
        }
    }

    $sixAxisComplete = ($missingAxes.Count -eq 0 -and $axisCount -eq 6)
    $sixAxisNumeric = ($sixAxisComplete -and $nonNumericAxes.Count -eq 0)
    $scoreRangeOk = ($sixAxisNumeric -and $outOfRangeAxes.Count -eq 0)

    if (-not $sixAxisComplete) {
        $blockingIssues.Add("six axis incomplete")
    }
    if ($nonNumericAxes.Count -gt 0) {
        $blockingIssues.Add("non-numeric axis scores: " + ($nonNumericAxes -join "|"))
    }
    if ($outOfRangeAxes.Count -gt 0) {
        $blockingIssues.Add("axis scores out of range: " + ($outOfRangeAxes -join "|"))
    }

    if ($summaryJsonExists) {
        try {
            $summary = Get-Content -LiteralPath $summaryJson -Raw -Encoding UTF8 | ConvertFrom-Json

            if (Test-ObjectProperty -Object $summary -Name "scoring_version") {
                $scoringVersion = [string]$summary.scoring_version
            }
            else {
                $blockingIssues.Add("summary missing scoring_version")
            }
            if ($scoringVersion -ne "v1.0b") {
                $blockingIssues.Add("summary scoring_version is not v1.0b")
            }

            if (Test-ObjectProperty -Object $summary -Name "calibrated_from_v1_0a") {
                $calibratedFromV10a = Test-Truthy $summary.calibrated_from_v1_0a
            }
            else {
                $blockingIssues.Add("summary missing calibrated_from_v1_0a")
            }
            if (-not $calibratedFromV10a) {
                $blockingIssues.Add("summary calibrated_from_v1_0a is not true")
            }

            if (Test-ObjectProperty -Object $summary -Name "navigation_semantics_calibrated") {
                $navigationSemanticsCalibrated = Test-Truthy $summary.navigation_semantics_calibrated
            }
            else {
                $blockingIssues.Add("summary missing navigation_semantics_calibrated")
            }
            if (-not $navigationSemanticsCalibrated) {
                $blockingIssues.Add("summary navigation_semantics_calibrated is not true")
            }

            if (Test-ObjectProperty -Object $summary -Name "runtime_llm_allowed") {
                $runtimeLlmAllowedOk = Test-Falsey $summary.runtime_llm_allowed
            }
            else {
                $blockingIssues.Add("summary missing runtime_llm_allowed")
            }
            if (-not $runtimeLlmAllowedOk) {
                $blockingIssues.Add("summary runtime_llm_allowed is not false")
            }

            if (Test-ObjectProperty -Object $summary -Name "previous_v1_0a_navigation_risk_score") {
                $prevRef = [ref]0.0
                if (Convert-ToInvariantDouble -Value $summary.previous_v1_0a_navigation_risk_score -OutValue $prevRef) {
                    $previousV10aNavigationRiskScore = $prevRef.Value
                    if ($previousV10aNavigationRiskScore -lt 0.0 -or $previousV10aNavigationRiskScore -gt 1.0) {
                        $blockingIssues.Add("previous_v1_0a_navigation_risk_score out of range")
                    }
                }
                else {
                    $blockingIssues.Add("previous_v1_0a_navigation_risk_score non-numeric")
                }
            }
            else {
                $blockingIssues.Add("summary missing previous_v1_0a_navigation_risk_score")
            }

            if (Test-ObjectProperty -Object $summary -Name "v1_0b_navigation_risk_score") {
                $navRef = [ref]0.0
                if (Convert-ToInvariantDouble -Value $summary.v1_0b_navigation_risk_score -OutValue $navRef) {
                    $v10bNavigationRiskScore = $navRef.Value
                    if ($v10bNavigationRiskScore -lt 0.0 -or $v10bNavigationRiskScore -gt 1.0) {
                        $blockingIssues.Add("v1_0b_navigation_risk_score out of range")
                    }
                }
                else {
                    $blockingIssues.Add("v1_0b_navigation_risk_score non-numeric")
                }
            }
            else {
                $blockingIssues.Add("summary missing v1_0b_navigation_risk_score")
            }

            if (Test-ObjectProperty -Object $summary -Name "proxy_features_n") {
                $proxyFeaturesN = [int]$summary.proxy_features_n
            }
            if (Test-ObjectProperty -Object $summary -Name "missing_features_n") {
                $missingFeaturesN = [int]$summary.missing_features_n
            }
        }
        catch {
            $blockingIssues.Add("summary JSON parse failed: $($_.Exception.Message)")
        }
    }

    $caseStatus = if ($blockingIssues.Count -gt 0) { "FAIL" } else { "PASS" }

    $row = [PSCustomObject]@{
        case_id = $caseId
        case_status = $caseStatus
        png_exists = $pngExists
        plot_data_exists = $plotDataExists
        summary_json_exists = $summaryJsonExists
        case_summary_csv_exists = $caseSummaryExists
        source_axis_score_csv_exists = $axisScoreCsvExists
        case_summary_radar_status = $caseSummaryRadarStatus
        axis_count = $axisCount
        six_axis_complete = $sixAxisComplete
        six_axis_numeric = $sixAxisNumeric
        score_min = $scoreMin
        score_max = $scoreMax
        score_range_ok = $scoreRangeOk
        scoring_version = $scoringVersion
        calibrated_from_v1_0a = $calibratedFromV10a
        navigation_semantics_calibrated = $navigationSemanticsCalibrated
        runtime_llm_allowed_ok = $runtimeLlmAllowedOk
        previous_v1_0a_navigation_risk_score = $previousV10aNavigationRiskScore
        v1_0b_navigation_risk_score = $v10bNavigationRiskScore
        proxy_features_n = $proxyFeaturesN
        missing_features_n = $missingFeaturesN
        missing_axes = ($missingAxes -join "|")
        non_numeric_axes = ($nonNumericAxes -join "|")
        out_of_range_axes = ($outOfRangeAxes -join "|")
        blocking_issue = ($blockingIssues -join " | ")
        output_png = $pngFp
        plot_data_csv = $plotDataCsv
        summary_json = $summaryJson
    }
    $rows += $row

    Write-Host (
        "{0}, {1}, png_exists={2}, plot_data_exists={3}, summary_json_exists={4}, six_axis_complete={5}, score_range_ok={6}, scoring_version={7}, calibrated_from_v1_0a={8}, navigation_semantics_calibrated={9}, previous_v1_0a_navigation_risk_score={10}, v1_0b_navigation_risk_score={11}, proxy_features_n={12}, missing_features_n={13}, blocking_issue={14}" -f
        $row.case_id,
        $row.case_status,
        $row.png_exists,
        $row.plot_data_exists,
        $row.summary_json_exists,
        $row.six_axis_complete,
        $row.score_range_ok,
        $row.scoring_version,
        $row.calibrated_from_v1_0a,
        $row.navigation_semantics_calibrated,
        $row.previous_v1_0a_navigation_risk_score,
        $row.v1_0b_navigation_risk_score,
        $row.proxy_features_n,
        $row.missing_features_n,
        $row.blocking_issue
    )
}

$rows | Export-Csv -LiteralPath $auditFp -NoTypeInformation -Encoding UTF8

$blockingFailN = @($rows | Where-Object { $_.case_status -eq "FAIL" }).Count
$passN = @($rows | Where-Object { $_.case_status -eq "PASS" }).Count
$finalStatus = if ($blockingFailN -gt 0 -or $passN -ne $caseIds.Count) {
    "FAIL"
}
else {
    "CONVERGED_WITH_NAVIGATION_SEMANTICS_CALIBRATED"
}

$decision = [PSCustomObject]@{
    thci_radar_v1_0b_status = $finalStatus
    case_count = $rows.Count
    pass_case_count = $passN
    blocking_fail_case_count = $blockingFailN
    case_summary_csv_exists = $caseSummaryExists
    proxy_features_total_n = ($rows | Measure-Object -Property proxy_features_n -Sum).Sum
    missing_features_total_n = ($rows | Measure-Object -Property missing_features_n -Sum).Sum
    formal_input_axis_score_root = $axisScoreRoot
    formal_output_radar_root = $radarRoot
    audit_csv = $auditFp
    decision_csv = $decisionFp
}

$decision | Export-Csv -LiteralPath $decisionFp -NoTypeInformation -Encoding UTF8

Write-Host "final decision: $finalStatus"
Write-Host "audit CSV: $auditFp"
Write-Host "decision CSV: $decisionFp"
