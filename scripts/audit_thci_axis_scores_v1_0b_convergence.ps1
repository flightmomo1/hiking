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

$nonNavigationAxisCols = @(
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "support_difficulty_score",
    "weather_impact_score"
)

$navigationDetailRequiredFields = @(
    "previous_v1_0a_navigation_risk_score",
    "route_confusion_score",
    "poor_visibility_score",
    "return_difficulty_score",
    "safe_exit_connectivity_score",
    "navigation_cap_applied",
    "score_before_cap",
    "final_score",
    "direct_features",
    "proxy_features",
    "missing_features",
    "note"
)

$v10aRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0a"
$outRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0b"
$batchDir = Join-Path $outRoot "_batch_summary"
$batchSummaryFp = Join-Path $batchDir "thci_axis_scores_v1_0b_case_summary.csv"
$auditFp = Join-Path $batchDir "thci_axis_scores_v1_0b_convergence_audit.csv"
$decisionFp = Join-Path $batchDir "thci_axis_scores_v1_0b_convergence_decision.csv"

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
    return ([string]$Value).Trim().ToLowerInvariant() -in @("false", "0", "no", "")
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

$batchSummaryExists = Test-Path -LiteralPath $batchSummaryFp -PathType Leaf
$rows = @()

foreach ($caseId in $caseIds) {
    $v10aCaseDir = Join-Path $v10aRoot $caseId
    $v10bCaseDir = Join-Path $outRoot $caseId
    $v10aScoreCsvFp = Join-Path $v10aCaseDir "${caseId}_thci_axis_scores_v1_0a.csv"
    $scoreCsvFp = Join-Path $v10bCaseDir "${caseId}_thci_axis_scores_v1_0b.csv"
    $summaryJsonFp = Join-Path $v10bCaseDir "${caseId}_thci_axis_score_summary_v1_0b.json"

    $v10aScoreCsvExists = Test-Path -LiteralPath $v10aScoreCsvFp -PathType Leaf
    $scoreCsvExists = Test-Path -LiteralPath $scoreCsvFp -PathType Leaf
    $summaryJsonExists = Test-Path -LiteralPath $summaryJsonFp -PathType Leaf
    $blockingIssues = New-Object System.Collections.Generic.List[string]
    $missingAxisCols = New-Object System.Collections.Generic.List[string]
    $nonNumericAxisCols = New-Object System.Collections.Generic.List[string]
    $outOfRangeAxisCols = New-Object System.Collections.Generic.List[string]
    $nonMatchingAxes = New-Object System.Collections.Generic.List[string]
    $missingNavigationDetailFields = New-Object System.Collections.Generic.List[string]

    $sixAxisComplete = $false
    $sixAxisNumeric = $false
    $scoreRangeOk = $false
    $nonNavigationAxesMatchV10a = $false
    $scoringVersion = ""
    $calibratedFromV10a = $false
    $navigationSemanticsCalibrated = $false
    $previousV10aNavigationRiskScore = $null
    $navigationRiskScore = $null
    $navigationCapApplied = $null
    $proxyFeaturesN = 0
    $missingFeaturesN = 0

    if (-not $v10aScoreCsvExists) {
        $blockingIssues.Add("v1.0a axis score CSV missing")
    }

    $v10aFirst = $null
    if ($v10aScoreCsvExists) {
        $v10aRows = @(Import-Csv -LiteralPath $v10aScoreCsvFp)
        if ($v10aRows.Count -eq 0) {
            $blockingIssues.Add("v1.0a axis score CSV empty")
        }
        else {
            $v10aFirst = $v10aRows[0]
        }
    }

    if (-not $scoreCsvExists) {
        $blockingIssues.Add("v1.0b axis score CSV missing")
    }
    else {
        $csvRows = @(Import-Csv -LiteralPath $scoreCsvFp)
        if ($csvRows.Count -eq 0) {
            $blockingIssues.Add("v1.0b axis score CSV empty")
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
                    $numRef = [ref]0.0
                    if (-not (Convert-ToInvariantDouble -Value $first.$axis -OutValue $numRef)) {
                        $nonNumericAxisCols.Add($axis)
                    }
                    else {
                        $num = $numRef.Value
                        if ($axis -eq "navigation_risk_score") {
                            $navigationRiskScore = $num
                        }
                        if ($num -lt 0.0 -or $num -gt 1.0) {
                            $outOfRangeAxisCols.Add($axis)
                        }
                    }
                }
            }

            $sixAxisNumeric = ($sixAxisComplete -and $nonNumericAxisCols.Count -eq 0)
            $scoreRangeOk = ($sixAxisNumeric -and $outOfRangeAxisCols.Count -eq 0)

            if (Test-ObjectProperty -Object $first -Name "scoring_version") {
                $scoringVersion = [string]$first.scoring_version
            }
            else {
                $blockingIssues.Add("CSV missing scoring_version")
            }
            if ($scoringVersion -ne "v1.0b") {
                $blockingIssues.Add("scoring_version is not v1.0b")
            }

            if (Test-ObjectProperty -Object $first -Name "calibrated_from_v1_0a") {
                $calibratedFromV10a = Test-Truthy $first.calibrated_from_v1_0a
            }
            else {
                $blockingIssues.Add("CSV missing calibrated_from_v1_0a")
            }
            if (-not $calibratedFromV10a) {
                $blockingIssues.Add("calibrated_from_v1_0a is not true")
            }

            if (Test-ObjectProperty -Object $first -Name "navigation_semantics_calibrated") {
                $navigationSemanticsCalibrated = Test-Truthy $first.navigation_semantics_calibrated
            }
            else {
                $blockingIssues.Add("CSV missing navigation_semantics_calibrated")
            }
            if (-not $navigationSemanticsCalibrated) {
                $blockingIssues.Add("navigation_semantics_calibrated is not true")
            }

            if (Test-ObjectProperty -Object $first -Name "navigation_cap_applied") {
                $navigationCapApplied = Test-Truthy $first.navigation_cap_applied
            }
            else {
                $blockingIssues.Add("CSV missing navigation_cap_applied")
            }

            if (Test-ObjectProperty -Object $first -Name "proxy_features_n") {
                $proxyFeaturesN = [int]$first.proxy_features_n
            }
            else {
                $blockingIssues.Add("CSV missing proxy_features_n")
            }
            if (Test-ObjectProperty -Object $first -Name "missing_features_n") {
                $missingFeaturesN = [int]$first.missing_features_n
            }
            else {
                $blockingIssues.Add("CSV missing missing_features_n")
            }

            if ($null -ne $v10aFirst -and $sixAxisComplete) {
                foreach ($axis in $nonNavigationAxisCols) {
                    if (-not (Test-ObjectProperty -Object $v10aFirst -Name $axis)) {
                        $nonMatchingAxes.Add("${axis}:missing_in_v1_0a")
                        continue
                    }
                    $aRef = [ref]0.0
                    $bRef = [ref]0.0
                    $aOk = Convert-ToInvariantDouble -Value $v10aFirst.$axis -OutValue $aRef
                    $bOk = Convert-ToInvariantDouble -Value $first.$axis -OutValue $bRef
                    if (-not $aOk -or -not $bOk) {
                        $nonMatchingAxes.Add("${axis}:non_numeric_compare")
                    }
                    elseif ([Math]::Abs($aRef.Value - $bRef.Value) -gt 1e-9) {
                        $nonMatchingAxes.Add("${axis}:v1_0a=$($aRef.Value),v1_0b=$($bRef.Value)")
                    }
                }
            }

            $nonNavigationAxesMatchV10a = ($nonMatchingAxes.Count -eq 0 -and $null -ne $v10aFirst)

            if (-not $sixAxisComplete) {
                $blockingIssues.Add("missing axis columns: " + ($missingAxisCols -join "|"))
            }
            if ($nonNumericAxisCols.Count -gt 0) {
                $blockingIssues.Add("non-numeric axis scores: " + ($nonNumericAxisCols -join "|"))
            }
            if ($outOfRangeAxisCols.Count -gt 0) {
                $blockingIssues.Add("axis scores out of range: " + ($outOfRangeAxisCols -join "|"))
            }
            if (-not $nonNavigationAxesMatchV10a) {
                $blockingIssues.Add("non-navigation axes differ from v1.0a: " + ($nonMatchingAxes -join "|"))
            }
        }
    }

    $jsonHasConfigPaths = $false
    $jsonHasInputRoots = $false
    $jsonHasAxisDetails = $false
    $jsonHasDirectFeatures = $false
    $jsonHasProxyFeatures = $false
    $jsonHasMissingFeatures = $false
    $runtimeLlmAllowedOk = $true

    if (-not $summaryJsonExists) {
        $blockingIssues.Add("summary JSON missing")
    }
    else {
        try {
            $summary = Get-Content -LiteralPath $summaryJsonFp -Raw -Encoding UTF8 | ConvertFrom-Json
            if (-not (Test-ObjectProperty -Object $summary -Name "scoring_version")) {
                $blockingIssues.Add("summary JSON missing scoring_version")
            }
            elseif ([string]$summary.scoring_version -ne "v1.0b") {
                $blockingIssues.Add("summary scoring_version is not v1.0b")
            }

            if (-not (Test-ObjectProperty -Object $summary -Name "calibrated_from_v1_0a")) {
                $blockingIssues.Add("summary JSON missing calibrated_from_v1_0a")
            }
            elseif (-not (Test-Truthy $summary.calibrated_from_v1_0a)) {
                $blockingIssues.Add("summary calibrated_from_v1_0a is not true")
            }

            if (-not (Test-ObjectProperty -Object $summary -Name "navigation_semantics_calibrated")) {
                $blockingIssues.Add("summary JSON missing navigation_semantics_calibrated")
            }
            elseif (-not (Test-Truthy $summary.navigation_semantics_calibrated)) {
                $blockingIssues.Add("summary navigation_semantics_calibrated is not true")
            }

            $jsonHasConfigPaths = Test-ObjectProperty -Object $summary -Name "config_paths"
            $jsonHasInputRoots = Test-ObjectProperty -Object $summary -Name "input_roots"
            $jsonHasAxisDetails = Test-ObjectProperty -Object $summary -Name "axis_details"
            $jsonHasDirectFeatures = Test-ObjectProperty -Object $summary -Name "direct_features"
            $jsonHasProxyFeatures = Test-ObjectProperty -Object $summary -Name "proxy_features"
            $jsonHasMissingFeatures = Test-ObjectProperty -Object $summary -Name "missing_features"

            if (-not $jsonHasConfigPaths) { $blockingIssues.Add("summary JSON missing config_paths") }
            if (-not $jsonHasInputRoots) { $blockingIssues.Add("summary JSON missing input_roots") }
            if (-not $jsonHasAxisDetails) { $blockingIssues.Add("summary JSON missing axis_details") }
            if (-not $jsonHasDirectFeatures) { $blockingIssues.Add("summary JSON missing direct_features") }
            if (-not $jsonHasProxyFeatures) { $blockingIssues.Add("summary JSON missing proxy_features") }
            if (-not $jsonHasMissingFeatures) { $blockingIssues.Add("summary JSON missing missing_features") }

            if ($jsonHasAxisDetails -and (Test-ObjectProperty -Object $summary.axis_details -Name "navigation_risk_score")) {
                $navDetail = $summary.axis_details.navigation_risk_score
                foreach ($field in $navigationDetailRequiredFields) {
                    if (-not (Test-ObjectProperty -Object $navDetail -Name $field)) {
                        $missingNavigationDetailFields.Add($field)
                    }
                }
                if (Test-ObjectProperty -Object $navDetail -Name "previous_v1_0a_navigation_risk_score") {
                    $prevRef = [ref]0.0
                    if (Convert-ToInvariantDouble -Value $navDetail.previous_v1_0a_navigation_risk_score -OutValue $prevRef) {
                        $previousV10aNavigationRiskScore = $prevRef.Value
                    }
                    else {
                        $blockingIssues.Add("previous_v1_0a_navigation_risk_score is non-numeric")
                    }
                }
                if (Test-ObjectProperty -Object $navDetail -Name "navigation_cap_applied") {
                    $navigationCapApplied = Test-Truthy $navDetail.navigation_cap_applied
                }
            }
            else {
                $blockingIssues.Add("axis_details.navigation_risk_score missing")
            }

            if ($missingNavigationDetailFields.Count -gt 0) {
                $blockingIssues.Add("axis_details.navigation_risk_score missing fields: " + ($missingNavigationDetailFields -join "|"))
            }

            if ($jsonHasProxyFeatures -and $proxyFeaturesN -eq 0) {
                $proxyFeaturesN = Count-NestedFeatures $summary.proxy_features
            }
            if ($jsonHasMissingFeatures -and $missingFeaturesN -eq 0) {
                $missingFeaturesN = Count-NestedFeatures $summary.missing_features
            }

            if (Test-ObjectProperty -Object $summary -Name "runtime_llm_allowed") {
                $runtimeLlmAllowedOk = Test-Falsey $summary.runtime_llm_allowed
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

    $row = [PSCustomObject]@{
        case_id = $caseId
        case_status = $caseStatus
        v1_0a_axis_score_csv_exists = $v10aScoreCsvExists
        axis_score_csv_exists = $scoreCsvExists
        summary_json_exists = $summaryJsonExists
        batch_summary_exists = $batchSummaryExists
        six_axis_complete = $sixAxisComplete
        six_axis_numeric = $sixAxisNumeric
        score_range_ok = $scoreRangeOk
        scoring_version = $scoringVersion
        calibrated_from_v1_0a = $calibratedFromV10a
        navigation_semantics_calibrated = $navigationSemanticsCalibrated
        non_navigation_axes_match_v1_0a = $nonNavigationAxesMatchV10a
        previous_v1_0a_navigation_risk_score = $previousV10aNavigationRiskScore
        navigation_risk_score = $navigationRiskScore
        navigation_cap_applied = $navigationCapApplied
        json_has_config_paths = $jsonHasConfigPaths
        json_has_input_roots = $jsonHasInputRoots
        json_has_axis_details = $jsonHasAxisDetails
        json_has_direct_features = $jsonHasDirectFeatures
        json_has_proxy_features = $jsonHasProxyFeatures
        json_has_missing_features = $jsonHasMissingFeatures
        runtime_llm_allowed_ok = $runtimeLlmAllowedOk
        proxy_features_n = $proxyFeaturesN
        missing_features_n = $missingFeaturesN
        non_matching_non_navigation_axes = ($nonMatchingAxes -join "|")
        missing_navigation_detail_fields = ($missingNavigationDetailFields -join "|")
        blocking_issue = ($blockingIssues -join " | ")
    }
    $rows += $row

    Write-Host (
        "{0}, {1}, six_axis_complete={2}, score_range_ok={3}, scoring_version={4}, calibrated_from_v1_0a={5}, navigation_semantics_calibrated={6}, non_navigation_axes_match_v1_0a={7}, previous_v1_0a_navigation_risk_score={8}, navigation_risk_score={9}, navigation_cap_applied={10}, blocking_issue={11}" -f
        $row.case_id,
        $row.case_status,
        $row.six_axis_complete,
        $row.score_range_ok,
        $row.scoring_version,
        $row.calibrated_from_v1_0a,
        $row.navigation_semantics_calibrated,
        $row.non_navigation_axes_match_v1_0a,
        $row.previous_v1_0a_navigation_risk_score,
        $row.navigation_risk_score,
        $row.navigation_cap_applied,
        $row.blocking_issue
    )
}

$rows | Export-Csv -LiteralPath $auditFp -NoTypeInformation -Encoding UTF8

$blockingFailN = @($rows | Where-Object { $_.case_status -eq "FAIL" }).Count
$nonNavigationMismatchN = @($rows | Where-Object { -not $_.non_navigation_axes_match_v1_0a }).Count
$passN = @($rows | Where-Object { $_.case_status -eq "PASS" }).Count
$finalStatus = if ($blockingFailN -gt 0 -or $nonNavigationMismatchN -gt 0 -or $passN -ne $caseIds.Count) {
    "FAIL"
}
else {
    "CONVERGED_WITH_NAVIGATION_SEMANTICS_CALIBRATED"
}

$decision = [PSCustomObject]@{
    thci_axis_scores_v1_0b_status = $finalStatus
    case_count = $rows.Count
    pass_case_count = $passN
    blocking_fail_case_count = $blockingFailN
    non_navigation_mismatch_case_count = $nonNavigationMismatchN
    proxy_features_total_n = ($rows | Measure-Object -Property proxy_features_n -Sum).Sum
    missing_features_total_n = ($rows | Measure-Object -Property missing_features_n -Sum).Sum
    audit_csv = $auditFp
    batch_summary_csv = $batchSummaryFp
}

$decision | Export-Csv -LiteralPath $decisionFp -NoTypeInformation -Encoding UTF8

Write-Host "final decision: $finalStatus"
Write-Host "audit CSV: $auditFp"
Write-Host "decision CSV: $decisionFp"
