$ErrorActionPreference = "Stop"

$CaseId = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
$OutRoot = "outputs\qixing_via_corridor_repair_candidate_formal_review_v1_3b"

$Evidence = [ordered]@{
    RouteAxisSummary = "outputs\qixing_lengshuikeng_via_corridor_route_axis_oscillation_audit_v1_3b\qixing_lengshuikeng_via_corridor_route_axis_oscillation_summary.json"
    RepairPlanSummary = "outputs\qixing_lengshuikeng_via_corridor_repair_plan_v1_3b\qixing_lengshuikeng_via_corridor_repair_plan_summary.json"
    PruningSummary = "outputs\ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\qixing_via_corridor_pruning_summary.json"
    RawdataSafetySummary = "outputs\qixing_via_corridor_pruning_activity_rawdata_safety_audit_v1_3b\qixing_pruning_activity_rawdata_safety_summary.json"
}

$DownstreamOutputs = [ordered]@{
    IB1A = "outputs\ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_route_profile.csv"
    IB1C = "outputs\ib1c_route_profile_semantics_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_route_profile_semantic_enriched.csv"
    IB1C_SemanticRisk = "outputs\ib1c_osm_semantic_risk_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_osm_semantic_risk_profile.csv"
    IB1G = "outputs\ib1g_contour_window_features_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_contour_window_features.csv"
    IB1E = "outputs\_j_ib1e_root_qixing_candidate\$CaseId\${CaseId}_route_profile_contour_window_terrain_enriched.csv"
    IB2 = "outputs\ib2_v2_route_risk_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_route_risk_v2.csv"
    IB2D = "outputs\ib2d_route_risk_offline_map_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\${CaseId}_route_risk_offline_map.png"
    IB3Sequence37 = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\37_1_mapmatched.csv"
    IB3Sequence33 = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\33_1_mapmatched.csv"
    IB3Sequence15 = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\15_1_mapmatched.csv"
    IB3A2OnRoute37 = "outputs\ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\qixing_lengshuikeng_37_1_mapmatched_activity_on_route.csv"
    IB3A2OnRoute33 = "outputs\ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\qixing_lengshuikeng_33_1_mapmatched_activity_on_route.csv"
    IB3A2OnRoute15 = "outputs\ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\qixing_lengshuikeng_15_1_mapmatched_activity_on_route.csv"
    IB3B2Visual37 = "outputs\ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\37_1\qixing_lengshuikeng_37_1_activity_profile_1d_2d.png"
    IB3B2Visual33 = "outputs\ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\33_1\qixing_lengshuikeng_33_1_activity_profile_1d_2d.png"
    IB3B2Visual15 = "outputs\ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate\qixing_lengshuikeng\15_1\qixing_lengshuikeng_15_1_activity_profile_1d_2d.png"
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function As-Bool {
    param($Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return $Value }
    return ([string]$Value).ToLowerInvariant() -in @("true", "1", "yes")
}

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$routeAxis = Read-JsonFile $Evidence.RouteAxisSummary
$repairPlan = Read-JsonFile $Evidence.RepairPlanSummary
$pruning = Read-JsonFile $Evidence.PruningSummary
$rawdata = Read-JsonFile $Evidence.RawdataSafetySummary

$evidenceRows = foreach ($item in $Evidence.GetEnumerator()) {
    [pscustomobject]@{
        item_type = "evidence_file"
        item_name = $item.Key
        required = $true
        exists = Test-Path -LiteralPath $item.Value
        status = if (Test-Path -LiteralPath $item.Value) { "PASS" } else { "FAIL_MISSING" }
        path = $item.Value
    }
}

$downstreamRows = foreach ($item in $DownstreamOutputs.GetEnumerator()) {
    [pscustomobject]@{
        item_type = "downstream_output"
        item_name = $item.Key
        required = $true
        exists = Test-Path -LiteralPath $item.Value
        status = if (Test-Path -LiteralPath $item.Value) { "PASS" } else { "FAIL_MISSING" }
        path = $item.Value
    }
}

$routeIssueConfirmed = $false
if ($routeAxis) {
    $routeIssueConfirmed = (As-Bool $routeAxis.route_axis_issue_suspected) -or
        ([string]$routeAxis.final_diagnostic_decision -like "*SUSPECTED_ROUTE_BASELINE_ISSUE*")
}

$repairNeededConfirmed = $false
if ($repairPlan) {
    $repairNeededConfirmed = (As-Bool $repairPlan.repair_needed) -and
        ([string]$repairPlan.recommended_repair_layer -eq "IB0D local loop pruning") -and
        (As-Bool $repairPlan.micro_bounce_suspected) -and
        (As-Bool $repairPlan.ib0d_pruning_recommended) -and
        (-not (As-Bool $repairPlan.ib3_only_review_recommended))
}

$ib0dCandidatePass = $false
if ($pruning) {
    $ib0dCandidatePass = ([string]$pruning.final_candidate_decision -like "*CANDIDATE_PASS*") -and
        (As-Bool $pruning.geometry_continuous) -and
        (As-Bool $pruning.route_dist_monotonic) -and
        (As-Bool $pruning.via_distance_ok) -and
        (-not (As-Bool $pruning.local_oscillation_detected_after))
}

$downstreamRunnable = -not (($downstreamRows | Where-Object { -not $_.exists }) | Select-Object -First 1)

$rawdataSafetyStatus = if ($rawdata) { [string]$rawdata.final_decision } else { "" }
$rawdataSafe = $rawdata -and
    (-not (As-Bool $rawdata.raw_data_modified)) -and
    (-not (As-Bool $rawdata.sequence_alignment_changed)) -and
    ([string]$rawdataSafetyStatus -in @("PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED", "PASS_RAWDATA_SAFE_PROJECTION_IMPROVED"))

$projectionImprovementStatus = "UNKNOWN"
if ($rawdataSafetyStatus -eq "PASS_RAWDATA_SAFE_PROJECTION_IMPROVED") {
    $projectionImprovementStatus = "CLEARLY_IMPROVED"
} elseif ($rawdataSafetyStatus -eq "PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED") {
    $projectionImprovementStatus = "MIXED_REMAP_REVIEW_REQUIRED"
} elseif ($rawdataSafetyStatus) {
    $projectionImprovementStatus = "NOT_PASSING"
}

if (-not $rawdataSafe) {
    $formalReviewStatus = "FAIL_RAWDATA_SAFETY"
    $nextAction = "Do not promote candidate. Inspect rawdata safety audit blocking issues first."
} elseif (-not $downstreamRunnable) {
    $formalReviewStatus = "FAIL_DOWNSTREAM_REVALIDATION"
    $nextAction = "Do not promote candidate. Complete missing candidate-only downstream outputs first."
} elseif ($routeIssueConfirmed -and $repairNeededConfirmed -and $ib0dCandidatePass -and $downstreamRunnable -and $rawdataSafe -and $projectionImprovementStatus -eq "CLEARLY_IMPROVED") {
    $formalReviewStatus = "READY_FOR_FORMAL_PROMOTION"
    $nextAction = "Proceed to formal promotion planning with guarded replacement of qixing route baseline roots."
} elseif ($routeIssueConfirmed -and $repairNeededConfirmed -and $ib0dCandidatePass -and $downstreamRunnable -and $rawdataSafe -and $projectionImprovementStatus -eq "MIXED_REMAP_REVIEW_REQUIRED") {
    $formalReviewStatus = "REVIEW_REQUIRED_BEFORE_FORMAL_PROMOTION"
    $nextAction = "Keep candidate isolated. Review activity remap reversals and IB2D risk changes before any formal root replacement."
} else {
    $formalReviewStatus = "REVIEW_REQUIRED_BEFORE_FORMAL_PROMOTION"
    $nextAction = "Keep candidate isolated. Evidence gates are incomplete or mixed; perform manual formal repair review."
}

$auditRows = @()
$auditRows += $evidenceRows
$auditRows += $downstreamRows
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "route_issue_confirmed"
    required = $true
    exists = $routeIssueConfirmed
    status = if ($routeIssueConfirmed) { "PASS" } else { "FAIL" }
    path = $Evidence.RouteAxisSummary
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "repair_needed_confirmed"
    required = $true
    exists = $repairNeededConfirmed
    status = if ($repairNeededConfirmed) { "PASS" } else { "FAIL" }
    path = $Evidence.RepairPlanSummary
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "ib0d_candidate_pass"
    required = $true
    exists = $ib0dCandidatePass
    status = if ($ib0dCandidatePass) { "PASS" } else { "FAIL" }
    path = $Evidence.PruningSummary
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "downstream_runnable"
    required = $true
    exists = $downstreamRunnable
    status = if ($downstreamRunnable) { "PASS" } else { "FAIL" }
    path = "candidate downstream roots"
}
$auditRows += [pscustomobject]@{
    item_type = "decision_gate"
    item_name = "rawdata_safe"
    required = $true
    exists = $rawdataSafe
    status = if ($rawdataSafe) { "PASS" } else { "FAIL" }
    path = $Evidence.RawdataSafetySummary
}

$AuditCsv = Join-Path $OutRoot "qixing_via_corridor_repair_candidate_formal_review_audit.csv"
$DecisionCsv = Join-Path $OutRoot "qixing_via_corridor_repair_candidate_formal_review_decision.csv"
$SummaryJson = Join-Path $OutRoot "qixing_via_corridor_repair_candidate_formal_review_summary.json"

$auditRows | Export-Csv -Path $AuditCsv -NoTypeInformation -Encoding UTF8

$decisionRow = [pscustomobject]@{
    case_id = $CaseId
    route_issue_confirmed = $routeIssueConfirmed
    repair_needed_confirmed = $repairNeededConfirmed
    ib0d_candidate_pass = $ib0dCandidatePass
    downstream_runnable = $downstreamRunnable
    rawdata_safe = $rawdataSafe
    projection_improvement_status = $projectionImprovementStatus
    formal_review_status = $formalReviewStatus
    next_action = $nextAction
    audit_csv = $AuditCsv
    summary_json = $SummaryJson
}
$decisionRow | Export-Csv -Path $DecisionCsv -NoTypeInformation -Encoding UTF8

$summary = [ordered]@{
    case_id = $CaseId
    route_issue_confirmed = $routeIssueConfirmed
    repair_needed_confirmed = $repairNeededConfirmed
    ib0d_candidate_pass = $ib0dCandidatePass
    downstream_runnable = $downstreamRunnable
    rawdata_safe = $rawdataSafe
    projection_improvement_status = $projectionImprovementStatus
    formal_review_status = $formalReviewStatus
    next_action = $nextAction
    evidence_paths = $Evidence
    downstream_output_paths = $DownstreamOutputs
    key_metrics = [ordered]@{
        final_diagnostic_decision = if ($routeAxis) { $routeAxis.final_diagnostic_decision } else { $null }
        recommended_repair_layer = if ($repairPlan) { $repairPlan.recommended_repair_layer } else { $null }
        suspected_problem_segments_n = if ($repairPlan) { $repairPlan.suspected_problem_segments_n } else { $null }
        pruning_candidate_decision = if ($pruning) { $pruning.final_candidate_decision } else { $null }
        removed_dist_m = if ($pruning) { $pruning.removed_dist_m } else { $null }
        original_route_dist_max_m = if ($pruning) { $pruning.original_route_dist_max_m } else { $null }
        pruned_route_length_m = if ($pruning) { $pruning.pruned_route_length_m } else { $null }
        local_oscillation_detected_before = if ($pruning) { $pruning.local_oscillation_detected_before } else { $null }
        local_oscillation_detected_after = if ($pruning) { $pruning.local_oscillation_detected_after } else { $null }
        rawdata_safety_status = $rawdataSafetyStatus
        raw_data_modified = if ($rawdata) { $rawdata.raw_data_modified } else { $null }
        sequence_alignment_changed = if ($rawdata) { $rawdata.sequence_alignment_changed } else { $null }
    }
    outputs = [ordered]@{
        audit_csv = $AuditCsv
        decision_csv = $DecisionCsv
        summary_json = $SummaryJson
    }
    runtime_llm_allowed = $false
    note = "Read-only formal review audit. It does not rerun pipeline stages and does not overwrite formal v1.3b outputs."
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $SummaryJson -Encoding UTF8

Write-Host "route_issue_confirmed=$routeIssueConfirmed"
Write-Host "ib0d_candidate_pass=$ib0dCandidatePass"
Write-Host "downstream_runnable=$downstreamRunnable"
Write-Host "rawdata_safe=$rawdataSafe"
Write-Host "projection_improvement_status=$projectionImprovementStatus"
Write-Host "formal_review_status=$formalReviewStatus"
Write-Host "next_action=$nextAction"
Write-Host "wrote_audit_csv=$AuditCsv"
Write-Host "wrote_decision_csv=$DecisionCsv"
Write-Host "wrote_summary_json=$SummaryJson"
