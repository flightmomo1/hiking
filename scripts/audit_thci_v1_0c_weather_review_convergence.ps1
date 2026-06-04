param()

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\mountain_work\115_osm"
$AxisV10bRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0b"
$AxisV10cRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0c"
$HydroTopoRoot = Join-Path $ProjectRoot "outputs\thci_weather_hydrology_topography_diagnostics_v1_0c_review"
$OutRoot = Join-Path $ProjectRoot "outputs\thci_v1_0c_weather_review_audit"

$Cases = @(
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b"
)

$NonWeatherAxes = @(
    "physical_difficulty_score",
    "technical_difficulty_score",
    "baseline_hazard_score",
    "navigation_risk_score",
    "support_difficulty_score"
)

$AllAxes = $NonWeatherAxes + @("weather_impact_score")

function Test-Truthy {
    param([object]$Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return [bool]$Value }
    return (@("true", "1", "yes", "y") -contains ([string]$Value).Trim().ToLowerInvariant())
}

function Test-Falsey {
    param([object]$Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return -not [bool]$Value }
    return (@("false", "0", "no", "n") -contains ([string]$Value).Trim().ToLowerInvariant())
}

function Convert-ToDoubleOrNull {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    $text = ([string]$Value).Trim()
    if ($text.Length -eq 0) { return $null }
    $out = 0.0
    if ([double]::TryParse($text, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$out)) {
        return $out
    }
    return $null
}

function Test-Range01 {
    param([object]$Value)
    $num = Convert-ToDoubleOrNull $Value
    return ($null -ne $num -and $num -ge 0.0 -and $num -le 1.0)
}

function Read-FirstCsvRow {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing CSV: $Path"
    }
    $rows = @(Import-Csv -LiteralPath $Path -Encoding UTF8)
    if ($rows.Count -lt 1) {
        throw "Empty CSV: $Path"
    }
    return $rows[0]
}

function Read-JsonObject {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing JSON: $Path"
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Resolve-HydroTopoCsvPath {
    param([string]$CaseId)
    $caseRoot = Join-Path $HydroTopoRoot $CaseId
    $specPath = Join-Path $caseRoot "$($CaseId)_weather_hydrology_topography_diagnostic_v1_0c_review.csv"
    if (Test-Path -LiteralPath $specPath) { return $specPath }
    $shortPath = Join-Path $caseRoot "$($CaseId)_hydro_topo_diag_v1_0c_review.csv"
    if (Test-Path -LiteralPath $shortPath) { return $shortPath }
    return $specPath
}

function Resolve-HydroTopoJsonPath {
    param([string]$CaseId)
    $caseRoot = Join-Path $HydroTopoRoot $CaseId
    $specPath = Join-Path $caseRoot "$($CaseId)_weather_hydrology_topography_summary_v1_0c_review.json"
    if (Test-Path -LiteralPath $specPath) { return $specPath }
    $shortPath = Join-Path $caseRoot "$($CaseId)_hydro_topo_summary_v1_0c_review.json"
    if (Test-Path -LiteralPath $shortPath) { return $shortPath }
    return $specPath
}

function Get-PropValue {
    param(
        [object]$Obj,
        [string]$Name
    )
    if ($null -eq $Obj) { return $null }
    $prop = $Obj.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$AxisBatchSummary = Join-Path $AxisV10cRoot "_batch_summary\thci_axis_scores_v1_0c_case_summary.csv"
$HydroTopoBatchSummary = Join-Path $HydroTopoRoot "_batch_summary\thci_weather_hydrology_topography_diagnostic_v1_0c_review_case_summary.csv"

$Rows = @()

foreach ($CaseId in $Cases) {
    $issues = New-Object System.Collections.Generic.List[string]

    $v10bCsv = Join-Path $AxisV10bRoot "$CaseId\$($CaseId)_thci_axis_scores_v1_0b.csv"
    $v10cCsv = Join-Path $AxisV10cRoot "$CaseId\$($CaseId)_thci_axis_scores_v1_0c.csv"
    $v10cJson = Join-Path $AxisV10cRoot "$CaseId\$($CaseId)_thci_axis_score_summary_v1_0c.json"
    $hydroCsv = Resolve-HydroTopoCsvPath $CaseId
    $hydroJson = Resolve-HydroTopoJsonPath $CaseId

    $v10cScoresExists = (Test-Path -LiteralPath $v10cCsv) -and (Test-Path -LiteralPath $v10cJson)
    $hydroTopoExists = (Test-Path -LiteralPath $hydroCsv) -and (Test-Path -LiteralPath $hydroJson)
    $weatherScoreRangeOk = $false
    $nonWeatherAxesCopied = $false
    $juansiEvidence = $false
    $summaryMetadataOk = $false
    $hydroMetadataOk = $false

    $weatherScore = $null
    $previousWeatherScore = $null
    $v10cWeatherScore = $null
    $hydrologyRatio = $null
    $lowHydroRatio = $null
    $waterCrossingPresence = $null
    $drainageScore = $null
    $crossingSurgeScore = $null

    try {
        if (-not (Test-Path -LiteralPath $AxisBatchSummary)) {
            $issues.Add("missing v1.0c batch summary: $AxisBatchSummary")
        }
        if (-not (Test-Path -LiteralPath $HydroTopoBatchSummary)) {
            $issues.Add("missing hydrology-topography batch summary: $HydroTopoBatchSummary")
        }

        if (-not $v10cScoresExists) {
            $issues.Add("missing v1.0c axis score CSV or summary JSON")
        }
        if (-not $hydroTopoExists) {
            $issues.Add("missing hydrology-topography diagnostic CSV or summary JSON")
        }
        if (-not (Test-Path -LiteralPath $v10bCsv)) {
            $issues.Add("missing v1.0b axis score CSV for non-weather axis comparison")
        }

        if ($v10cScoresExists) {
            $v10cRow = Read-FirstCsvRow $v10cCsv
            $v10cSummary = Read-JsonObject $v10cJson

            $summaryMetadataOk = (
                (Get-PropValue $v10cSummary "scoring_version") -eq "v1.0c" -and
                (Test-Truthy (Get-PropValue $v10cSummary "calibrated_from_v1_0b")) -and
                (Test-Truthy (Get-PropValue $v10cSummary "weather_semantics_calibrated")) -and
                (Test-Falsey (Get-PropValue $v10cSummary "runtime_llm_allowed")) -and
                (Test-Truthy (Get-PropValue $v10cSummary "non_weather_axes_copied_from_v1_0b"))
            )
            if (-not $summaryMetadataOk) {
                $issues.Add("v1.0c summary metadata invalid")
            }

            if ((Get-PropValue $v10cRow "scoring_version") -ne "v1.0c") {
                $issues.Add("v1.0c CSV scoring_version is not v1.0c")
            }
            if (-not (Test-Truthy (Get-PropValue $v10cRow "calibrated_from_v1_0b"))) {
                $issues.Add("v1.0c CSV calibrated_from_v1_0b is not true")
            }
            if (-not (Test-Truthy (Get-PropValue $v10cRow "weather_semantics_calibrated"))) {
                $issues.Add("v1.0c CSV weather_semantics_calibrated is not true")
            }
            if (-not (Test-Falsey (Get-PropValue $v10cRow "runtime_llm_allowed"))) {
                $issues.Add("v1.0c CSV runtime_llm_allowed is not false")
            }

            $weatherScore = Get-PropValue $v10cRow "weather_impact_score"
            $previousWeatherScore = Get-PropValue $v10cRow "previous_v1_0b_weather_impact_score"
            $v10cWeatherScore = Get-PropValue $v10cRow "v1_0c_weather_impact_score"
            $weatherScoreRangeOk = (Test-Range01 $weatherScore) -and (Test-Range01 $v10cWeatherScore)
            if (-not $weatherScoreRangeOk) {
                $issues.Add("weather_impact_score is missing, non-numeric, or outside 0-1")
            }

            $nonWeatherAxesCopied = $true
            if (Test-Path -LiteralPath $v10bCsv) {
                $v10bRow = Read-FirstCsvRow $v10bCsv
                foreach ($axis in $NonWeatherAxes) {
                    $a = Convert-ToDoubleOrNull (Get-PropValue $v10cRow $axis)
                    $b = Convert-ToDoubleOrNull (Get-PropValue $v10bRow $axis)
                    if ($null -eq $a -or $null -eq $b -or [math]::Abs($a - $b) -gt 1e-9) {
                        $nonWeatherAxesCopied = $false
                        $issues.Add("non-weather axis differs from v1.0b: $axis")
                    }
                }
            } else {
                $nonWeatherAxesCopied = $false
            }
        }

        if ($hydroTopoExists) {
            $hydroRow = Read-FirstCsvRow $hydroCsv
            $hydroSummary = Read-JsonObject $hydroJson

            $diagnosticVersion = Get-PropValue $hydroRow "diagnostic_version"
            if ([string]::IsNullOrWhiteSpace([string]$diagnosticVersion)) {
                $diagnosticVersion = Get-PropValue $hydroSummary "diagnostic_version"
            }
            $requiredHydroFields = @(
                "hydrology_proximity_ratio",
                "low_elevation_hydrology_overlap_ratio",
                "water_crossing_presence",
                "drainage_accumulation_proxy_score",
                "crossing_surge_score"
            )
            $hydroMetadataOk = -not [string]::IsNullOrWhiteSpace([string]$diagnosticVersion)
            foreach ($field in $requiredHydroFields) {
                if ($null -eq (Get-PropValue $hydroRow $field)) {
                    $hydroMetadataOk = $false
                    $issues.Add("hydrology-topography diagnostic missing field: $field")
                }
            }
            if (-not (Test-Falsey (Get-PropValue $hydroSummary "runtime_llm_allowed"))) {
                $hydroMetadataOk = $false
                $issues.Add("hydrology-topography summary runtime_llm_allowed is not false")
            }

            $hydrologyRatio = Convert-ToDoubleOrNull (Get-PropValue $hydroRow "hydrology_proximity_ratio")
            $lowHydroRatio = Convert-ToDoubleOrNull (Get-PropValue $hydroRow "low_elevation_hydrology_overlap_ratio")
            $waterCrossingPresence = Test-Truthy (Get-PropValue $hydroRow "water_crossing_presence")
            $drainageScore = Convert-ToDoubleOrNull (Get-PropValue $hydroRow "drainage_accumulation_proxy_score")
            $crossingSurgeScore = Convert-ToDoubleOrNull (Get-PropValue $hydroRow "crossing_surge_score")

            if ($CaseId -eq "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b") {
                $juansiEvidence = (
                    $null -ne $hydrologyRatio -and $hydrologyRatio -ge 0.5 -and
                    $null -ne $lowHydroRatio -and $lowHydroRatio -gt 0.0 -and
                    $waterCrossingPresence -eq $true -and
                    $null -ne $drainageScore -and $drainageScore -ge 0.5
                )
                if (-not $juansiEvidence) {
                    $issues.Add("juansi hydrology-topography review evidence criteria not met")
                }
            }
        }
    } catch {
        $issues.Add($_.Exception.Message)
    }

    $caseStatus = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
    $blockingIssue = if ($issues.Count -eq 0) { "" } else { ($issues -join "; ") }

    $row = [pscustomobject]@{
        case_id = $CaseId
        case_status = $caseStatus
        v1_0c_scores_exists = $v10cScoresExists
        hydrology_topography_diagnostic_exists = $hydroTopoExists
        v1_0c_batch_summary_exists = Test-Path -LiteralPath $AxisBatchSummary
        hydrology_topography_batch_summary_exists = Test-Path -LiteralPath $HydroTopoBatchSummary
        weather_score_range_ok = $weatherScoreRangeOk
        non_weather_axes_copied_from_v1_0b = $nonWeatherAxesCopied
        v1_0c_summary_metadata_ok = $summaryMetadataOk
        hydrology_topography_metadata_ok = $hydroMetadataOk
        juansi_hydrology_topography_review_evidence = $juansiEvidence
        previous_v1_0b_weather_impact_score = $previousWeatherScore
        v1_0c_weather_impact_score = $v10cWeatherScore
        hydrology_proximity_ratio = $hydrologyRatio
        low_elevation_hydrology_overlap_ratio = $lowHydroRatio
        water_crossing_presence = $waterCrossingPresence
        drainage_accumulation_proxy_score = $drainageScore
        crossing_surge_score = $crossingSurgeScore
        v1_0c_axis_score_csv = $v10cCsv
        v1_0c_axis_score_summary_json = $v10cJson
        hydrology_topography_diagnostic_csv = $hydroCsv
        hydrology_topography_summary_json = $hydroJson
        blocking_issue = $blockingIssue
    }
    $Rows += $row

    Write-Host ("{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}" -f `
        $row.case_id, `
        $row.case_status, `
        $row.v1_0c_scores_exists, `
        $row.hydrology_topography_diagnostic_exists, `
        $row.weather_score_range_ok, `
        $row.non_weather_axes_copied_from_v1_0b, `
        $row.juansi_hydrology_topography_review_evidence, `
        $row.blocking_issue)
}

$AuditCsv = Join-Path $OutRoot "thci_v1_0c_weather_review_convergence_audit.csv"
$DecisionCsv = Join-Path $OutRoot "thci_v1_0c_weather_review_convergence_decision.csv"

$Rows | Export-Csv -LiteralPath $AuditCsv -Encoding UTF8 -NoTypeInformation

$blockingFail = @($Rows | Where-Object { $_.case_status -ne "PASS" }).Count -gt 0
$finalStatus = if (-not $blockingFail) {
    "WEATHER_CALIBRATION_ESTABLISHED_WITH_HYDROLOGY_TOPOGRAPHY_REVIEW"
} else {
    "FAIL"
}

$decision = [pscustomobject]@{
    THCI_V1_0C_WEATHER_REVIEW_STATUS = $finalStatus
    cases_expected_n = $Cases.Count
    cases_pass_n = @($Rows | Where-Object { $_.case_status -eq "PASS" }).Count
    cases_fail_n = @($Rows | Where-Object { $_.case_status -ne "PASS" }).Count
    audit_csv = $AuditCsv
    generated_at_local = (Get-Date).ToString("s")
    note = "v1.0c is a weather calibration candidate and does not replace v1.0b recommended display version."
}
$decision | Export-Csv -LiteralPath $DecisionCsv -Encoding UTF8 -NoTypeInformation

Write-Host ("final decision: {0}" -f $finalStatus)
Write-Host ("audit CSV: {0}" -f $AuditCsv)
Write-Host ("decision CSV: {0}" -f $DecisionCsv)

if ($finalStatus -eq "FAIL") {
    exit 1
}
exit 0
