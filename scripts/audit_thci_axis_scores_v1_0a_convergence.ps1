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

$outRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0a"
$batchDir = Join-Path $outRoot "_batch_summary"
$batchSummaryFp = Join-Path $batchDir "thci_axis_scores_v1_0a_case_summary.csv"
$auditFp = Join-Path $batchDir "thci_axis_scores_v1_0a_convergence_audit.csv"
$decisionFp = Join-Path $batchDir "thci_axis_scores_v1_0a_convergence_decision.csv"

New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

function Test-ObjectProperty {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string] $Name
    )
    return ($null -ne $Object.PSObject.Properties[$Name])
}

function Count-NestedFeatures {
    param($FeatureObject)

    if ($null -eq $FeatureObject) {
        return 0
    }

    $count = 0
    foreach ($prop in $FeatureObject.PSObject.Properties) {
        $value = $prop.Value
        if ($null -eq $value) {
            continue
        }
        if ($value -is [System.Array]) {
            $count += $value.Count
        }
        elseif ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
            $count += @($value).Count
        }
        elseif ([string]$value -ne "") {
            $count += 1
        }
    }
    return $count
}

function Test-Truthy {
    param($Value)
    return ([string]$Value).Trim().ToLowerInvariant() -in @("true", "1", "yes", "y")
}

$batchSummaryExists = Test-Path -LiteralPath $batchSummaryFp -PathType Leaf
$rows = @()

foreach ($caseId in $caseIds) {
    $caseDir = Join-Path $outRoot $caseId
    $scoreCsvFp = Join-Path $caseDir "${caseId}_thci_axis_scores_v1_0a.csv"
    $summaryJsonFp = Join-Path $caseDir "${caseId}_thci_axis_score_summary_v1_0a.json"

    $scoreCsvExists = Test-Path -LiteralPath $scoreCsvFp -PathType Leaf
    $summaryJsonExists = Test-Path -LiteralPath $summaryJsonFp -PathType Leaf
    $blockingIssues = New-Object System.Collections.Generic.List[string]
    $missingAxisCols = New-Object System.Collections.Generic.List[string]
    $nonNumericAxisCols = New-Object System.Collections.Generic.List[string]
    $outOfRangeAxisCols = New-Object System.Collections.Generic.List[string]

    $sixAxisComplete = $false
    $sixAxisNumeric = $false
    $scoreRangeOk = $false
    $csvProxyFeaturesN = $null
    $csvMissingFeaturesN = $null

    if (-not $scoreCsvExists) {
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
                    $num = 0.0
                    $raw = $first.$axis
                    if (-not [double]::TryParse([string]$raw, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$num)) {
                        $nonNumericAxisCols.Add($axis)
                    }
                    elseif ($num -lt 0.0 -or $num -gt 1.0) {
                        $outOfRangeAxisCols.Add($axis)
                    }
                }
            }
            $sixAxisNumeric = ($sixAxisComplete -and $nonNumericAxisCols.Count -eq 0)
            $scoreRangeOk = ($sixAxisNumeric -and $outOfRangeAxisCols.Count -eq 0)

            if (Test-ObjectProperty -Object $first -Name "proxy_features_n") {
                $csvProxyFeaturesN = [int]$first.proxy_features_n
            }
            else {
                $blockingIssues.Add("CSV missing proxy_features_n")
            }
            if (Test-ObjectProperty -Object $first -Name "missing_features_n") {
                $csvMissingFeaturesN = [int]$first.missing_features_n
            }
            else {
                $blockingIssues.Add("CSV missing missing_features_n")
            }

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

    $scoringVersion = ""
    $calibratedFromV10 = $false
    $jsonHasDirectFeatures = $false
    $jsonHasProxyFeatures = $false
    $jsonHasMissingFeatures = $false
    $jsonHasConfigPaths = $false
    $jsonHasInputRoots = $false
    $runtimeLlmAllowedOk = $true
    $jsonProxyFeaturesN = 0
    $jsonMissingFeaturesN = 0

    if (-not $summaryJsonExists) {
        $blockingIssues.Add("summary JSON missing")
    }
    else {
        try {
            $summary = Get-Content -LiteralPath $summaryJsonFp -Raw -Encoding UTF8 | ConvertFrom-Json
            if (Test-ObjectProperty -Object $summary -Name "scoring_version") {
                $scoringVersion = [string]$summary.scoring_version
            }
            else {
                $blockingIssues.Add("summary JSON missing scoring_version")
            }
            if ($scoringVersion -ne "v1.0a") {
                $blockingIssues.Add("scoring_version is not v1.0a")
            }

            if (Test-ObjectProperty -Object $summary -Name "calibrated_from_v1_0") {
                $calibratedFromV10 = Test-Truthy $summary.calibrated_from_v1_0
            }
            else {
                $blockingIssues.Add("summary JSON missing calibrated_from_v1_0")
            }
            if (-not $calibratedFromV10) {
                $blockingIssues.Add("calibrated_from_v1_0 is not true")
            }

            $jsonHasDirectFeatures = Test-ObjectProperty -Object $summary -Name "direct_features"
            $jsonHasProxyFeatures = Test-ObjectProperty -Object $summary -Name "proxy_features"
            $jsonHasMissingFeatures = Test-ObjectProperty -Object $summary -Name "missing_features"
            $jsonHasConfigPaths = Test-ObjectProperty -Object $summary -Name "config_paths"
            $jsonHasInputRoots = Test-ObjectProperty -Object $summary -Name "input_roots"

            if (-not $jsonHasDirectFeatures) { $blockingIssues.Add("summary JSON missing direct_features") }
            if (-not $jsonHasProxyFeatures) { $blockingIssues.Add("summary JSON missing proxy_features") }
            if (-not $jsonHasMissingFeatures) { $blockingIssues.Add("summary JSON missing missing_features") }
            if (-not $jsonHasConfigPaths) { $blockingIssues.Add("summary JSON missing config_paths") }
            if (-not $jsonHasInputRoots) { $blockingIssues.Add("summary JSON missing input_roots") }

            if ($jsonHasProxyFeatures) {
                $jsonProxyFeaturesN = Count-NestedFeatures $summary.proxy_features
            }
            if ($jsonHasMissingFeatures) {
                $jsonMissingFeaturesN = Count-NestedFeatures $summary.missing_features
            }

            if (Test-ObjectProperty -Object $summary -Name "runtime_llm_allowed") {
                $runtimeLlmAllowedOk = ([string]$summary.runtime_llm_allowed).ToLowerInvariant() -in @("false", "0", "no")
                if (-not $runtimeLlmAllowedOk) {
                    $blockingIssues.Add("runtime_llm_allowed is not false")
                }
            }
        }
        catch {
            $blockingIssues.Add("summary JSON parse failed: $($_.Exception.Message)")
        }
    }

    if (-not $batchSummaryExists) {
        $blockingIssues.Add("batch summary missing")
    }

    $caseStatus = if ($blockingIssues.Count -gt 0) { "FAIL" } else { "PASS" }
    $proxyFeaturesN = if ($null -ne $csvProxyFeaturesN) { $csvProxyFeaturesN } else { $jsonProxyFeaturesN }
    $missingFeaturesN = if ($null -ne $csvMissingFeaturesN) { $csvMissingFeaturesN } else { $jsonMissingFeaturesN }

    $row = [PSCustomObject]@{
        case_id = $caseId
        case_status = $caseStatus
        axis_score_csv_exists = $scoreCsvExists
        summary_json_exists = $summaryJsonExists
        batch_summary_exists = $batchSummaryExists
        six_axis_complete = $sixAxisComplete
        six_axis_numeric = $sixAxisNumeric
        score_range_ok = $scoreRangeOk
        scoring_version = $scoringVersion
        calibrated_from_v1_0 = $calibratedFromV10
        json_has_direct_features = $jsonHasDirectFeatures
        json_has_proxy_features = $jsonHasProxyFeatures
        json_has_missing_features = $jsonHasMissingFeatures
        json_has_config_paths = $jsonHasConfigPaths
        json_has_input_roots = $jsonHasInputRoots
        runtime_llm_allowed_ok = $runtimeLlmAllowedOk
        proxy_features_n = $proxyFeaturesN
        missing_features_n = $missingFeaturesN
        blocking_issue = ($blockingIssues -join " | ")
    }
    $rows += $row

    Write-Host (
        "{0}, {1}, six_axis_complete={2}, score_range_ok={3}, scoring_version={4}, calibrated_from_v1_0={5}, proxy_features_n={6}, missing_features_n={7}, blocking_issue={8}" -f
        $row.case_id,
        $row.case_status,
        $row.six_axis_complete,
        $row.score_range_ok,
        $row.scoring_version,
        $row.calibrated_from_v1_0,
        $row.proxy_features_n,
        $row.missing_features_n,
        $row.blocking_issue
    )
}

$rows | Export-Csv -LiteralPath $auditFp -NoTypeInformation -Encoding UTF8

$blockingFailN = @($rows | Where-Object { $_.case_status -eq "FAIL" }).Count
$finalStatus = if ($blockingFailN -gt 0) { "FAIL" } else { "CONVERGED_WITH_PROXY_FEATURES_RECORDED" }

$decision = [PSCustomObject]@{
    thci_axis_scores_v1_0a_status = $finalStatus
    case_count = $rows.Count
    pass_case_count = @($rows | Where-Object { $_.case_status -eq "PASS" }).Count
    blocking_fail_case_count = $blockingFailN
    proxy_features_total_n = ($rows | Measure-Object -Property proxy_features_n -Sum).Sum
    missing_features_total_n = ($rows | Measure-Object -Property missing_features_n -Sum).Sum
    audit_csv = $auditFp
    batch_summary_csv = $batchSummaryFp
}

$decision | Export-Csv -LiteralPath $decisionFp -NoTypeInformation -Encoding UTF8

Write-Host "final decision: $finalStatus"
Write-Host "audit CSV: $auditFp"
Write-Host "decision CSV: $decisionFp"
