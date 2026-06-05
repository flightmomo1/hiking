$ErrorActionPreference = "Stop"

$Root = "outputs\ib3f_activity_route_features_v1_3b_qixing_repaired_review"
$RouteFolder = "qixing_lengshuikeng"
$ActivityIds = @("37_1", "33_1", "15_1")
$BatchDir = Join-Path $Root "_batch_summary"
$BatchSummaryCsv = Join-Path $BatchDir "ib3f_activity_route_features_summary.csv"
$ContractSummaryJson = Join-Path $BatchDir "ib3f_feature_contract_summary.json"
$AuditCsv = Join-Path $BatchDir "ib3f_qixing_repaired_review_smoke_audit.csv"
$DecisionCsv = Join-Path $BatchDir "ib3f_qixing_repaired_review_smoke_decision.csv"
$SummaryJson = Join-Path $BatchDir "ib3f_qixing_repaired_review_smoke_summary.json"

$RequiredColumns = @(
    "activity_id",
    "activity_quality_flag",
    "on_route_ratio",
    "speed_available",
    "hr_available",
    "moderate_risk_ratio",
    "high_risk_ratio",
    "route_choice_review_required",
    "remap_review_note"
)
$RequiredAliases = @{
    risk_join_coverage_ratio = @("risk_join_coverage_ratio", "route_risk_join_coverage_ratio")
}

function Has-AnyColumn {
    param([string[]]$Columns, [string[]]$Names)
    foreach ($name in $Names) {
        if ($name -in $Columns) { return $true }
    }
    return $false
}

function Get-AliasValue {
    param($Row, [string[]]$Names)
    foreach ($name in $Names) {
        if ($Row.PSObject.Properties.Name -contains $name) {
            return $Row.$name
        }
    }
    return $null
}

function As-Bool {
    param($Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return $Value }
    return ([string]$Value).ToLowerInvariant() -in @("true", "1", "yes", "y")
}

function As-Double {
    param($Value)
    $out = 0.0
    if ([double]::TryParse([string]$Value, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$out)) {
        return $out
    }
    return [double]::NaN
}

function Join-Notes {
    param([string[]]$Notes)
    return ($Notes | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "; "
}

New-Item -ItemType Directory -Force -Path $BatchDir | Out-Null

$batchExists = Test-Path -LiteralPath $BatchSummaryCsv
$contractExists = Test-Path -LiteralPath $ContractSummaryJson
$batchRows = if ($batchExists) { @(Import-Csv -LiteralPath $BatchSummaryCsv) } else { @() }
$batchColumns = if ($batchRows.Count -gt 0) { @($batchRows[0].PSObject.Properties.Name) } else { @() }
$missingColumns = @($RequiredColumns | Where-Object { $_ -notin $batchColumns })
foreach ($aliasName in $RequiredAliases.Keys) {
    if (-not (Has-AnyColumn $batchColumns $RequiredAliases[$aliasName])) {
        $missingColumns += $aliasName
    }
}

$auditRows = @()
foreach ($activityId in $ActivityIds) {
    $featureCsv = Join-Path $Root "$RouteFolder\${RouteFolder}_${activityId}_activity_features.csv"
    $featureJson = Join-Path $Root "$RouteFolder\${RouteFolder}_${activityId}_activity_features.json"
    $featureCsvExists = Test-Path -LiteralPath $featureCsv
    $featureJsonExists = Test-Path -LiteralPath $featureJson
    $row = $batchRows | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    $activityPresent = $null -ne $row
    $notes = @()

    if (-not $featureCsvExists) { $notes += "missing feature CSV" }
    if (-not $featureJsonExists) { $notes += "missing feature JSON" }
    if (-not $activityPresent) { $notes += "activity missing from batch summary" }

    $quality = if ($activityPresent) { [string]$row.activity_quality_flag } else { "" }
    $joinCoverage = if ($activityPresent) { As-Double (Get-AliasValue $row $RequiredAliases["risk_join_coverage_ratio"]) } else { [double]::NaN }
    $speedAvailable = if ($activityPresent) { As-Bool $row.speed_available } else { $false }
    $hrAvailable = if ($activityPresent) { As-Bool $row.hr_available } else { $false }
    $routeChoiceReview = if ($activityPresent) { As-Bool $row.route_choice_review_required } else { $false }
    $onRouteRatio = if ($activityPresent) { As-Double $row.on_route_ratio } else { [double]::NaN }
    $moderateRiskRatio = if ($activityPresent) { As-Double $row.moderate_risk_ratio } else { [double]::NaN }
    $highRiskRatio = if ($activityPresent) { As-Double $row.high_risk_ratio } else { [double]::NaN }

    if ($activityPresent -and ($joinCoverage -lt 0.95 -or [double]::IsNaN($joinCoverage))) { $notes += "join coverage below 0.95" }
    if ($activityPresent -and -not $speedAvailable) { $notes += "speed unavailable" }
    if ($activityPresent -and -not $hrAvailable) { $notes += "HR unavailable" }
    if ($quality -eq "REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO") { $notes += "allowed warning: low on-route ratio" }

    $blocking = @($notes | Where-Object { $_ -notlike "allowed warning*" })
    $status = if ($blocking.Count -gt 0) {
        "FAIL"
    } elseif ($quality -eq "REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO") {
        "WARN_REVIEW_REQUIRED_LOW_ON_ROUTE_RATIO"
    } else {
        "PASS"
    }

    $auditRows += [pscustomobject]@{
        activity_id = $activityId
        feature_csv_exists = $featureCsvExists
        feature_json_exists = $featureJsonExists
        batch_row_exists = $activityPresent
        activity_quality_flag = $quality
        on_route_ratio = $onRouteRatio
        speed_available = $speedAvailable
        hr_available = $hrAvailable
        moderate_risk_ratio = $moderateRiskRatio
        high_risk_ratio = $highRiskRatio
        risk_join_coverage_ratio = $joinCoverage
        route_choice_review_required = $routeChoiceReview
        remap_review_note = if ($activityPresent) { [string]$row.remap_review_note } else { "" }
        smoke_status = $status
        blocking_issue = Join-Notes $blocking
        note = Join-Notes $notes
        feature_csv = $featureCsv
        feature_json = $featureJson
    }
}

$missingFilesFail = -not $batchExists -or -not $contractExists
$missingColumnsFail = $missingColumns.Count -gt 0
$activityFailN = @($auditRows | Where-Object { $_.smoke_status -eq "FAIL" }).Count
$passReadyN = @($auditRows | Where-Object { $_.activity_quality_flag -eq "PASS_REVIEW_READY" }).Count
$reviewRequiredN = @($auditRows | Where-Object { $_.activity_quality_flag -like "REVIEW_REQUIRED*" }).Count
$speedAll = -not (@($auditRows | Where-Object { -not $_.speed_available }) | Select-Object -First 1)
$hrAll = -not (@($auditRows | Where-Object { -not $_.hr_available }) | Select-Object -First 1)
$joinCoverageValues = @($auditRows | ForEach-Object { $_.risk_join_coverage_ratio } | Where-Object { -not [double]::IsNaN($_) })
$joinCoverageMin = if ($joinCoverageValues.Count -gt 0) { ($joinCoverageValues | Measure-Object -Minimum).Minimum } else { [double]::NaN }
$joinCoverageOk = $joinCoverageValues.Count -eq $ActivityIds.Count -and $joinCoverageMin -ge 0.95

if ($missingFilesFail -or $missingColumnsFail -or $activityFailN -gt 0 -or -not $joinCoverageOk -or -not $speedAll -or -not $hrAll -or $passReadyN -lt 2) {
    $finalStatus = "FAIL"
} elseif ($reviewRequiredN -gt 0) {
    $finalStatus = "PASS_WITH_REVIEW_CASE"
} else {
    $finalStatus = "PASS"
}

$auditRows | Export-Csv -Path $AuditCsv -NoTypeInformation -Encoding UTF8

$decision = [pscustomobject]@{
    ib3f_qixing_repaired_review_smoke_status = $finalStatus
    activities_n = $ActivityIds.Count
    pass_ready_n = $passReadyN
    review_required_n = $reviewRequiredN
    fail_n = $activityFailN
    join_coverage_min = $joinCoverageMin
    speed_available_all = $speedAll
    hr_available_all = $hrAll
    batch_summary_exists = $batchExists
    contract_summary_exists = $contractExists
    missing_required_columns = ($missingColumns -join ";")
    audit_csv = $AuditCsv
    summary_json = $SummaryJson
}
$decision | Export-Csv -Path $DecisionCsv -NoTypeInformation -Encoding UTF8

$summary = [ordered]@{
    ib3f_qixing_repaired_review_smoke_status = $finalStatus
    activities_n = $ActivityIds.Count
    pass_ready_n = $passReadyN
    review_required_n = $reviewRequiredN
    fail_n = $activityFailN
    join_coverage_min = $joinCoverageMin
    speed_available_all = $speedAll
    hr_available_all = $hrAll
    input_root = $Root
    batch_summary_csv = $BatchSummaryCsv
    feature_contract_summary_json = $ContractSummaryJson
    missing_required_columns = $missingColumns
    outputs = [ordered]@{
        audit_csv = $AuditCsv
        decision_csv = $DecisionCsv
        summary_json = $SummaryJson
    }
    gate_rules = [ordered]@{
        join_coverage_min_required = 0.95
        speed_available_required = $true
        hr_available_required = $true
        pass_review_ready_min_required = 2
        review_required_low_on_route_ratio_allowed_as_warn = $true
    }
    runtime_llm_allowed = $false
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $SummaryJson -Encoding UTF8

Write-Host "IB3F_QIXING_REPAIRED_REVIEW_SMOKE_STATUS=$finalStatus"
Write-Host "activities_n=$($ActivityIds.Count)"
Write-Host "pass_ready_n=$passReadyN"
Write-Host "review_required_n=$reviewRequiredN"
Write-Host "fail_n=$activityFailN"
Write-Host "join_coverage_min=$joinCoverageMin"
Write-Host "speed_available_all=$speedAll"
Write-Host "hr_available_all=$hrAll"
Write-Host "audit_csv=$AuditCsv"
Write-Host "decision_csv=$DecisionCsv"
Write-Host "summary_json=$SummaryJson"
