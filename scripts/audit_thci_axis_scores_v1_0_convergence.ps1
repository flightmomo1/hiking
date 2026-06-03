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

$axisCols = @(
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score",
    "weather_impact_score"
)

$outRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0"
$batchDir = Join-Path $outRoot "_batch_summary"
$batchSummaryFp = Join-Path $batchDir "thci_axis_scores_v1_0_case_summary.csv"
$auditFp = Join-Path $batchDir "thci_axis_scores_v1_0_convergence_audit.csv"
$decisionFp = Join-Path $batchDir "thci_axis_scores_v1_0_convergence_decision.csv"

New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

function Test-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name
    )
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Count-MissingFeatures {
    param($MissingFeatures)

    if ($null -eq $MissingFeatures) {
        return 0
    }

    $count = 0
    foreach ($prop in $MissingFeatures.PSObject.Properties) {
        $value = $prop.Value
        if ($null -eq $value) {
            continue
        }
        if ($value -is [System.Array]) {
            $count += $value.Count
        }
        elseif ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
            $items = @($value)
            $count += $items.Count
        }
        elseif ([string]$value -ne "") {
            $count += 1
        }
    }
    return $count
}

$batchSummaryExists = Test-Path -LiteralPath $batchSummaryFp -PathType Leaf
$rows = @()

foreach ($caseId in $caseIds) {
    $caseDir = Join-Path $outRoot $caseId
    $scoreCsvFp = Join-Path $caseDir "${caseId}_thci_axis_scores_v1_0.csv"
    $summaryJsonFp = Join-Path $caseDir "${caseId}_thci_axis_score_summary_v1_0.json"

    $axisScoreCsvExists = Test-Path -LiteralPath $scoreCsvFp -PathType Leaf
    $summaryJsonExists = Test-Path -LiteralPath $summaryJsonFp -PathType Leaf

    $blockingIssues = New-Object System.Collections.Generic.List[string]
    $missingAxisCols = New-Object System.Collections.Generic.List[string]
    $nonNumericAxisCols = New-Object System.Collections.Generic.List[string]
    $outOfRangeAxisCols = New-Object System.Collections.Generic.List[string]

    $sixAxisComplete = $false
    $sixAxisNumeric = $false
    $scoreRangeOk = $false

    if (-not $axisScoreCsvExists) {
        $blockingIssues.Add("axis score CSV missing")
    }
    else {
        $csvRows = @(Import-Csv -LiteralPath $scoreCsvFp)
        if ($csvRows.Count -eq 0) {
            $blockingIssues.Add("axis score CSV empty")
        }
        else {
            $first = $csvRows[0]
            foreach ($axis in $axisCols) {
                if (-not (Test-ObjectProperty -Object $first -Name $axis)) {
                    $missingAxisCols.Add($axis)
                }
            }
            $sixAxisComplete = ($missingAxisCols.Count -eq 0)

            if ($sixAxisComplete) {
                foreach ($axis in $axisCols) {
                    $raw = $first.$axis
                    $num = 0.0
                    if (-not [double]::TryParse([string]$raw, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$num)) {
                        $nonNumericAxisCols.Add($axis)
                    }
                    elseif ($num -lt 0.0 -or $num -gt 1.0) {
                        $outOfRangeAxisCols.Add($axis)
                    }
                }
            }
            $sixAxisNumeric = ($sixAxisComplete -and $nonNumericAxisCols.Count -eq 0)
            $scoreRangeOk = ($sixAxisComplete -and $sixAxisNumeric -and $outOfRangeAxisCols.Count -eq 0)

            if (-not $sixAxisComplete) {
                $blockingIssues.Add("missing axis columns: " + ($missingAxisCols -join "|"))
            }
            if ($nonNumericAxisCols.Count -gt 0) {
                $blockingIssues.Add("non-numeric axis scores: " + ($nonNumericAxisCols -join "|"))
            }
            if ($outOfRangeAxisCols.Count -gt 0) {
                $blockingIssues.Add("axis scores out of range: " + ($outOfRangeAxisCols -join "|"))
            }
        }
    }

    $jsonHasConfigPaths = $false
    $jsonHasInputRoots = $false
    $jsonHasAxisDetails = $false
    $jsonHasMissingFeatures = $false
    $runtimeLlmAllowedOk = $true
    $missingFeaturesN = 0

    if (-not $summaryJsonExists) {
        $blockingIssues.Add("summary JSON missing")
    }
    else {
        try {
            $summary = Get-Content -LiteralPath $summaryJsonFp -Raw -Encoding UTF8 | ConvertFrom-Json
            $jsonHasConfigPaths = Test-ObjectProperty -Object $summary -Name "config_paths"
            $jsonHasInputRoots = Test-ObjectProperty -Object $summary -Name "input_roots"
            $jsonHasAxisDetails = Test-ObjectProperty -Object $summary -Name "axis_details"
            $jsonHasMissingFeatures = Test-ObjectProperty -Object $summary -Name "missing_features"

            if (-not $jsonHasConfigPaths) { $blockingIssues.Add("summary JSON missing config_paths") }
            if (-not $jsonHasInputRoots) { $blockingIssues.Add("summary JSON missing input_roots") }
            if (-not $jsonHasAxisDetails) { $blockingIssues.Add("summary JSON missing axis_details") }
            if (-not $jsonHasMissingFeatures) { $blockingIssues.Add("summary JSON missing missing_features") }

            if (Test-ObjectProperty -Object $summary -Name "runtime_llm_allowed") {
                $runtimeLlmAllowedOk = ([string]$summary.runtime_llm_allowed).ToLowerInvariant() -in @("false", "0", "no")
                if (-not $runtimeLlmAllowedOk) {
                    $blockingIssues.Add("runtime_llm_allowed is not false")
                }
            }

            if ($jsonHasMissingFeatures) {
                $missingFeaturesN = Count-MissingFeatures -MissingFeatures $summary.missing_features
            }
        }
        catch {
            $blockingIssues.Add("summary JSON parse failed: $($_.Exception.Message)")
        }
    }

    if (-not $batchSummaryExists) {
        $blockingIssues.Add("batch summary missing")
    }

    $hasBlockingFail = ($blockingIssues.Count -gt 0)
    if ($hasBlockingFail) {
        $caseStatus = "FAIL"
    }
    elseif ($missingFeaturesN -gt 0) {
        $caseStatus = "WARN_MISSING_FEATURES_RECORDED"
    }
    else {
        $caseStatus = "PASS"
    }

    $row = [PSCustomObject]@{
        case_id = $caseId
        case_status = $caseStatus
        axis_score_csv_exists = $axisScoreCsvExists
        summary_json_exists = $summaryJsonExists
        batch_summary_exists = $batchSummaryExists
        six_axis_complete = $sixAxisComplete
        six_axis_numeric = $sixAxisNumeric
        score_range_ok = $scoreRangeOk
        json_has_config_paths = $jsonHasConfigPaths
        json_has_input_roots = $jsonHasInputRoots
        json_has_axis_details = $jsonHasAxisDetails
        json_has_missing_features = $jsonHasMissingFeatures
        runtime_llm_allowed_ok = $runtimeLlmAllowedOk
        missing_features_n = $missingFeaturesN
        blocking_issue = ($blockingIssues -join " | ")
    }
    $rows += $row

    Write-Host (
        "{0}, {1}, six_axis_complete={2}, score_range_ok={3}, summary_json_exists={4}, missing_features_n={5}, blocking_issue={6}" -f
        $row.case_id,
        $row.case_status,
        $row.six_axis_complete,
        $row.score_range_ok,
        $row.summary_json_exists,
        $row.missing_features_n,
        $row.blocking_issue
    )
}

$rows | Export-Csv -LiteralPath $auditFp -NoTypeInformation -Encoding UTF8

$blockingFailN = @($rows | Where-Object { $_.case_status -eq "FAIL" }).Count
$missingFeaturesTotalN = ($rows | Measure-Object -Property missing_features_n -Sum).Sum

if ($blockingFailN -gt 0) {
    $finalStatus = "FAIL"
}
elseif ($missingFeaturesTotalN -gt 0) {
    $finalStatus = "CONVERGED_WITH_MISSING_FEATURES_RECORDED"
}
else {
    $finalStatus = "CONVERGED"
}

$decision = [PSCustomObject]@{
    thci_axis_scores_status = $finalStatus
    case_count = $rows.Count
    pass_or_warn_case_count = @($rows | Where-Object { $_.case_status -ne "FAIL" }).Count
    blocking_fail_case_count = $blockingFailN
    missing_features_total_n = $missingFeaturesTotalN
    audit_csv = $auditFp
    batch_summary_csv = $batchSummaryFp
}

$decision | Export-Csv -LiteralPath $decisionFp -NoTypeInformation -Encoding UTF8

Write-Host "final decision: $finalStatus"
Write-Host "audit CSV: $auditFp"
Write-Host "decision CSV: $decisionFp"
