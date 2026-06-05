$ErrorActionPreference = "Stop"

$RouteFolder = "qixing_lengshuikeng"
$CaseId = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
$ActivityIds = @("37_1", "33_1", "15_1")

$V1Root = "outputs\ib3_route_choice_inference_v1_3b_qixing_repaired_formal_review"
$V2Root = "outputs\ib3_route_choice_inference_v2_geometry_qixing_repaired_formal_review"
$RawQaRoot = "outputs\ib3_raw_gps_vs_projected_route_choice_qa_v1_3b_qixing_repaired_review"
$CorridorQaRoot = "outputs\ib3_route_choice_inference_v2_geometry_qixing_repaired_formal_review\corridor_definition_qa"
$ConfigCsv = "configs\risk_semantics\qixing_branch_corridor_definition_v1_3b.csv"

$V1SummaryCsv = Join-Path $V1Root "qixing_route_choice_inference_summary.csv"
$V1SummaryJson = Join-Path $V1Root "qixing_route_choice_inference_summary.json"
$V2SummaryCsv = Join-Path $V2Root "qixing_route_choice_inference_v2_geometry_summary.csv"
$V2SummaryJson = Join-Path $V2Root "qixing_route_choice_inference_v2_geometry_summary.json"
$RawSummaryCsv = Join-Path $RawQaRoot "qixing_raw_vs_projected_route_choice_summary.csv"
$RawSummaryJson = Join-Path $RawQaRoot "qixing_raw_vs_projected_route_choice_qa_summary.json"
$CorridorQaSummaryJson = Join-Path $CorridorQaRoot "qixing_branch_corridor_definition_qa_summary.json"
$CorridorQaHtml = Join-Path $CorridorQaRoot "qixing_branch_corridor_definition_qa.html"

$OutRoot = "outputs\ib3_route_choice_inference_conclusion_v1_3b_qixing"
$AuditCsv = Join-Path $OutRoot "qixing_route_choice_inference_conclusion_audit.csv"
$DecisionCsv = Join-Path $OutRoot "qixing_route_choice_inference_conclusion_decision.csv"
$SummaryJson = Join-Path $OutRoot "qixing_route_choice_inference_conclusion_summary.json"

function As-Bool {
    param($Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return $Value }
    return ([string]$Value).ToLowerInvariant() -in @("true", "1", "yes", "y")
}

function Read-CsvSafe {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    return @(Import-Csv -LiteralPath $Path)
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$requiredFiles = [ordered]@{
    v1_summary_csv = $V1SummaryCsv
    v1_summary_json = $V1SummaryJson
    v2_summary_csv = $V2SummaryCsv
    v2_summary_json = $V2SummaryJson
    raw_gps_projected_summary_csv = $RawSummaryCsv
    raw_gps_projected_summary_json = $RawSummaryJson
    corridor_definition_csv = $ConfigCsv
    corridor_qa_summary_json = $CorridorQaSummaryJson
    corridor_qa_html = $CorridorQaHtml
}

$auditRows = foreach ($item in $requiredFiles.GetEnumerator()) {
    $exists = Test-Path -LiteralPath $item.Value
    [pscustomobject]@{
        item_type = "required_file"
        item_name = $item.Key
        activity_id = ""
        status = if ($exists) { "PASS" } else { "FAIL_MISSING" }
        value = $exists
        path = $item.Value
        note = ""
    }
}

$v1 = Read-CsvSafe $V1SummaryCsv
$v2 = Read-CsvSafe $V2SummaryCsv
$raw = Read-CsvSafe $RawSummaryCsv

foreach ($activityId in $ActivityIds) {
    $v1Row = $v1 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    $v2Row = $v2 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    $rawRow = $raw | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    foreach ($pair in @(
        @{name="v1_activity_processed"; row=$v1Row; path=$V1SummaryCsv},
        @{name="v2_activity_processed"; row=$v2Row; path=$V2SummaryCsv},
        @{name="raw_activity_processed"; row=$rawRow; path=$RawSummaryCsv}
    )) {
        $ok = $null -ne $pair.row
        $auditRows += [pscustomobject]@{
            item_type = "activity_presence"
            item_name = $pair.name
            activity_id = $activityId
            status = if ($ok) { "PASS" } else { "FAIL_MISSING" }
            value = $ok
            path = $pair.path
            note = ""
        }
    }
}

$allFilesExist = -not (($auditRows | Where-Object { $_.item_type -eq "required_file" -and $_.status -ne "PASS" }) | Select-Object -First 1)
$allActivitiesProcessed = -not (($auditRows | Where-Object { $_.item_type -eq "activity_presence" -and $_.status -ne "PASS" }) | Select-Object -First 1)

$v1ReviewRequiredAll = $true
$v2ReviewRequiredAll = $true
$highConfidenceClassifications = 0
$automaticBranchClassifications = 0
foreach ($row in $v1 + $v2) {
    if ([string]$row.route_choice_confidence -eq "high") {
        $highConfidenceClassifications += 1
    }
    if ([string]$row.actual_branch_sequence -notin @("ambiguous", "partial") -and [string]$row.canonical_route_match -ne "unknown") {
        $automaticBranchClassifications += 1
    }
}
foreach ($activityId in $ActivityIds) {
    $v1Row = $v1 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    $v2Row = $v2 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    if (-not $v1Row -or -not (As-Bool $v1Row.route_choice_review_required)) { $v1ReviewRequiredAll = $false }
    if (-not $v2Row -or -not (As-Bool $v2Row.route_choice_review_required)) { $v2ReviewRequiredAll = $false }
}

$rawMismatchN = 0
foreach ($row in $raw) {
    if (As-Bool $row.raw_projection_order_mismatch_flag) {
        $rawMismatchN += 1
    }
}
$rawGpsMismatchPrimaryIssue = $rawMismatchN -gt 0
$rawMismatchStatus = if ($rawGpsMismatchPrimaryIssue) { "RAW_PROJECTION_MISMATCH_DETECTED" } else { "NO_PRIMARY_RAW_PROJECTION_MISMATCH" }

$reviewRequiredN = 0
foreach ($activityId in $ActivityIds) {
    $v1Row = $v1 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    $v2Row = $v2 | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    if (($v1Row -and (As-Bool $v1Row.route_choice_review_required)) -or ($v2Row -and (As-Bool $v2Row.route_choice_review_required))) {
        $reviewRequiredN += 1
    }
}

$evidenceComplete = $allFilesExist -and $allActivitiesProcessed
if (-not $evidenceComplete) {
    $finalStatus = "INCOMPLETE_EVIDENCE"
} elseif ($highConfidenceClassifications -gt 0) {
    $finalStatus = "GEOMETRY_INFERENCE_READY_FOR_REVIEW"
} elseif ($v1ReviewRequiredAll -and $v2ReviewRequiredAll -and -not $rawGpsMismatchPrimaryIssue) {
    $finalStatus = "AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED"
} else {
    $finalStatus = "AUTOMATIC_CLASSIFICATION_NOT_RELIABLE_REVIEW_REQUIRED"
}

$recommendedNextAction = "Do not force canonical route-choice classification for qixing_lengshuikeng activities. Keep route_choice_review_required=True unless additional branch corridor ground truth or stronger route network segmentation is available."

$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "all_activities_review_required"
    activity_id = ""
    status = if ($v1ReviewRequiredAll -and $v2ReviewRequiredAll) { "PASS" } else { "WARN" }
    value = ($v1ReviewRequiredAll -and $v2ReviewRequiredAll)
    path = "$V1SummaryCsv;$V2SummaryCsv"
    note = "v1 and v2 require review for all activities"
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "no_high_confidence_automatic_classification"
    activity_id = ""
    status = if ($highConfidenceClassifications -eq 0) { "PASS" } else { "WARN" }
    value = ($highConfidenceClassifications -eq 0)
    path = "$V1SummaryCsv;$V2SummaryCsv"
    note = "high-confidence automatic classifications are not expected in this conclusion"
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "raw_gps_mismatch_not_primary_issue"
    activity_id = ""
    status = if (-not $rawGpsMismatchPrimaryIssue) { "PASS" } else { "WARN" }
    value = (-not $rawGpsMismatchPrimaryIssue)
    path = $RawSummaryCsv
    note = $rawMismatchStatus
}

$auditRows | Export-Csv -Path $AuditCsv -NoTypeInformation -Encoding UTF8

$decision = [pscustomobject]@{
    case_id = $CaseId
    route_folder = $RouteFolder
    activities_n = $ActivityIds.Count
    review_required_n = $reviewRequiredN
    high_confidence_classifications_n = $highConfidenceClassifications
    automatic_branch_classifications_n = $automaticBranchClassifications
    raw_projection_mismatch_n = $rawMismatchN
    qixing_route_choice_inference_status = $finalStatus
    final_status = $finalStatus
    recommended_next_action = $recommendedNextAction
    audit_csv = $AuditCsv
    summary_json = $SummaryJson
}
$decision | Export-Csv -Path $DecisionCsv -NoTypeInformation -Encoding UTF8

$summary = [ordered]@{
    qixing_route_choice_inference_status = $finalStatus
    final_status = $finalStatus
    activities_n = $ActivityIds.Count
    high_confidence_classifications_n = $highConfidenceClassifications
    review_required_n = $reviewRequiredN
    v1_method_result = "point-proximity inference returned same_corridor/ambiguous/low confidence for 37_1, 33_1, and 15_1 because via_up/via_down control points are spatially close."
    v2_method_result = "geometry corridor-based inference returned mixed/ambiguous/low confidence for 37_1, 33_1, and 15_1; 30m corridor match ratios are low and via_up/via_down evidence is close."
    raw_gps_projection_mismatch_status = $rawMismatchStatus
    recommended_next_action = $recommendedNextAction
    evidence_paths = [ordered]@{
        v1_summary_csv = $V1SummaryCsv
        v2_summary_csv = $V2SummaryCsv
        raw_gps_projected_summary_csv = $RawSummaryCsv
        corridor_definition_csv = $ConfigCsv
        corridor_qa_summary_json = $CorridorQaSummaryJson
    }
    outputs = [ordered]@{
        audit_csv = $AuditCsv
        decision_csv = $DecisionCsv
        summary_json = $SummaryJson
    }
    note = "Conclusion audit is read-only. It does not rerun analysis, modify baseline roots, repaired roots, raw data, or THCI. It explicitly avoids forcing canonical route-choice classification."
    runtime_llm_allowed = $false
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -Path $SummaryJson -Encoding UTF8

Write-Host "final_status=$finalStatus"
Write-Host "QIXING_ROUTE_CHOICE_INFERENCE_STATUS=$finalStatus"
Write-Host "activities_n=$($ActivityIds.Count)"
Write-Host "review_required_n=$reviewRequiredN"
Write-Host "high_confidence_classifications_n=$highConfidenceClassifications"
Write-Host "recommended_next_action=$recommendedNextAction"
Write-Host "audit_csv=$AuditCsv"
Write-Host "decision_csv=$DecisionCsv"
Write-Host "summary_json=$SummaryJson"
