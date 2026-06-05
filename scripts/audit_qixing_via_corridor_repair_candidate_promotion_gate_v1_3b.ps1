$ErrorActionPreference = "Stop"

$CaseId = "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b"
$RouteFolder = "qixing_lengshuikeng"
$ActivityIds = @("37_1", "33_1", "15_1")

$GateRoot = "outputs\qixing_via_corridor_repair_promotion_gate_v1_3b"
$IndexRoot = "outputs\qixing_via_corridor_repaired_formal_index_v1_3b"

$AuditCsv = Join-Path $GateRoot "qixing_via_corridor_repair_promotion_gate_audit.csv"
$DecisionCsv = Join-Path $GateRoot "qixing_via_corridor_repair_promotion_gate_decision.csv"
$SummaryJson = Join-Path $GateRoot "qixing_via_corridor_repair_promotion_gate_summary.json"
$IndexJson = Join-Path $IndexRoot "qixing_via_corridor_repaired_formal_index.json"
$IndexCsv = Join-Path $IndexRoot "qixing_via_corridor_repaired_formal_index.csv"

$Evidence = [ordered]@{
    RouteAxisSummary = "outputs\qixing_lengshuikeng_via_corridor_route_axis_oscillation_audit_v1_3b\qixing_lengshuikeng_via_corridor_route_axis_oscillation_summary.json"
    RepairPlanSummary = "outputs\qixing_lengshuikeng_via_corridor_repair_plan_v1_3b\qixing_lengshuikeng_via_corridor_repair_plan_summary.json"
    PruningSummary = "outputs\ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate\$CaseId\qixing_via_corridor_pruning_summary.json"
    RawdataSafetySummary = "outputs\qixing_via_corridor_pruning_activity_rawdata_safety_audit_v1_3b\qixing_pruning_activity_rawdata_safety_summary.json"
    FormalReviewSummary = "outputs\qixing_via_corridor_repair_candidate_formal_review_v1_3b\qixing_via_corridor_repair_candidate_formal_review_summary.json"
}

$PreviousFormalRoots = [ordered]@{
    IB0D = "outputs\ib0d_trimmed_mainline_v1_3b_control_points_only_contract_qa"
    IB1A = "outputs\ib1_route_profile_v1_3b_contract_qa"
    IB1C = "outputs\ib1c_route_profile_semantics_v1_3b_contract_qa"
    IB1C_SemanticRisk = "outputs\ib1c_osm_semantic_risk_v1_3b_contract_qa"
    IB1G = "outputs\ib1g_contour_window_features_v1_3b_contract_qa"
    IB1E = "outputs\ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
    IB2 = "outputs\ib2_v2_route_risk_v1_3b_contract_qa"
    IB2D = "outputs\ib2d_route_risk_offline_map_v1_3b_contract_qa"
    IB3Sequence = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_thci_v1_0c"
    IB3A2 = "outputs\ib3a2_on_route_activity_filter_v1_3b_thci_v1_0c"
    IB3B2 = "outputs\ib3_activity_profile_visual_qa_v1_3b_thci_v1_0c"
}

$RootMap = @(
    [pscustomobject]@{ stage = "IB0D"; source = "outputs\ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib0d_trimmed_mainline_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB1A"; source = "outputs\ib1_route_profile_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib1_route_profile_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB1C"; source = "outputs\ib1c_route_profile_semantics_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib1c_route_profile_semantics_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB1C_SemanticRisk"; source = "outputs\ib1c_osm_semantic_risk_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib1c_osm_semantic_risk_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB1G"; source = "outputs\ib1g_contour_window_features_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib1g_contour_window_features_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB1E"; source = "outputs\_j_ib1e_root_qixing_candidate\$CaseId"; destination = "outputs\ib1e_route_profile_contour_window_terrain_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB2"; source = "outputs\ib2_v2_route_risk_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib2_v2_route_risk_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB2D"; source = "outputs\ib2d_route_risk_offline_map_v1_3b_qixing_via_corridor_repair_candidate\$CaseId"; destination = "outputs\ib2d_route_risk_offline_map_v1_3b_qixing_via_corridor_repaired_formal\$CaseId" },
    [pscustomobject]@{ stage = "IB3Sequence"; source = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repair_candidate\$RouteFolder"; destination = "outputs\ib3a_sequence_mapmatched_activity_v1_3b_qixing_via_corridor_repaired_formal\$RouteFolder" },
    [pscustomobject]@{ stage = "IB3A2"; source = "outputs\ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repair_candidate\$RouteFolder"; destination = "outputs\ib3a2_on_route_activity_filter_v1_3b_qixing_via_corridor_repaired_formal\$RouteFolder" },
    [pscustomobject]@{ stage = "IB3B2"; source = "outputs\ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repair_candidate\$RouteFolder"; destination = "outputs\ib3_activity_profile_visual_qa_v1_3b_qixing_via_corridor_repaired_formal\$RouteFolder" }
)

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function As-Bool {
    param($Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return $Value }
    return ([string]$Value).ToLowerInvariant() -in @("true", "1", "yes")
}

function Copy-DirectoryContents {
    param(
        [string]$Source,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source root missing: $Source"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $GateRoot | Out-Null
New-Item -ItemType Directory -Force -Path $IndexRoot | Out-Null

$routeAxis = Read-JsonFile $Evidence.RouteAxisSummary
$repairPlan = Read-JsonFile $Evidence.RepairPlanSummary
$pruning = Read-JsonFile $Evidence.PruningSummary
$rawdata = Read-JsonFile $Evidence.RawdataSafetySummary
$formalReview = Read-JsonFile $Evidence.FormalReviewSummary

$evidenceRows = foreach ($item in $Evidence.GetEnumerator()) {
    [pscustomobject]@{
        item_type = "evidence_file"
        item_name = $item.Key
        exists = Test-Path -LiteralPath $item.Value
        status = if (Test-Path -LiteralPath $item.Value) { "PASS" } else { "FAIL_MISSING" }
        path = $item.Value
        note = ""
    }
}

$candidateRootRows = foreach ($root in $RootMap) {
    [pscustomobject]@{
        item_type = "candidate_root"
        item_name = $root.stage
        exists = Test-Path -LiteralPath $root.source
        status = if (Test-Path -LiteralPath $root.source) { "PASS" } else { "FAIL_MISSING" }
        path = $root.source
        note = "candidate source root"
    }
}

$routeIssueConfirmed = $routeAxis -and ((As-Bool $routeAxis.route_axis_issue_suspected) -or ([string]$routeAxis.final_diagnostic_decision -like "*SUSPECTED_ROUTE_BASELINE_ISSUE*"))
$repairNeeded = $repairPlan -and (As-Bool $repairPlan.repair_needed) -and ([string]$repairPlan.recommended_repair_layer -eq "IB0D local loop pruning") -and (As-Bool $repairPlan.micro_bounce_suspected)
$ib0dCandidatePass = $pruning -and ([string]$pruning.final_candidate_decision -like "*CANDIDATE_PASS*") -and (-not (As-Bool $pruning.local_oscillation_detected_after))
$downstreamRunnable = -not (($candidateRootRows | Where-Object { -not $_.exists }) | Select-Object -First 1)
$rawdataSafe = $rawdata -and (-not (As-Bool $rawdata.raw_data_modified)) -and (-not (As-Bool $rawdata.sequence_alignment_changed)) -and ([string]$rawdata.final_decision -in @("PASS_RAWDATA_SAFE_REMAP_REVIEW_REQUIRED", "PASS_RAWDATA_SAFE_PROJECTION_IMPROVED"))

$rawAuditRows = @()
$projectionRows = @()
if ($rawdata -and $rawdata.raw_audits) { $rawAuditRows = @($rawdata.raw_audits) }
if ($rawdata -and $rawdata.projection_summaries) { $projectionRows = @($rawdata.projection_summaries) }

$sequenceRowsStable = $true
foreach ($activityId in $ActivityIds) {
    $row = $rawAuditRows | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    if (-not $row -or -not (As-Bool $row.sequence_rows_same) -or -not (As-Bool $row.timestamp_order_same)) {
        $sequenceRowsStable = $false
    }
}

$onRouteNotDegraded = $true
$branchAmbiguityNotIncreased = $true
$offRouteLowConfidenceNotIncreased = $true
$excursionsNotIncreased = $true
$projectionReversalMixed = $false
$projectionReversalClearlyImproved = $true
$anyProjectionReversalImproved = $false

foreach ($activityId in $ActivityIds) {
    $row = $projectionRows | Where-Object { $_.activity_id -eq $activityId } | Select-Object -First 1
    if (-not $row) {
        $onRouteNotDegraded = $false
        $branchAmbiguityNotIncreased = $false
        $offRouteLowConfidenceNotIncreased = $false
        $excursionsNotIncreased = $false
        $projectionReversalClearlyImproved = $false
        continue
    }

    if ($null -ne $row.on_route_delta_ratio -and [double]$row.on_route_delta_ratio -lt -0.10) {
        $onRouteNotDegraded = $false
    }
    if ([int]$row.branch_ambiguous_delta_rows -gt 0) {
        $branchAmbiguityNotIncreased = $false
    }
    if (([int]$row.off_route_projection_delta_rows -gt 0) -or ([int]$row.near_route_low_confidence_delta_rows -gt 0)) {
        $offRouteLowConfidenceNotIncreased = $false
    }
    if ([int]$row.excursions_delta_n -gt 0) {
        $excursionsNotIncreased = $false
    }
    if ([int]$row.route_dist_projection_reversal_delta_n -gt 0 -or [int]$row.corridor_reversal_delta_n -gt 0) {
        $projectionReversalClearlyImproved = $false
        $projectionReversalMixed = $true
    }
    if ([int]$row.route_dist_projection_reversal_delta_n -lt 0 -or [int]$row.corridor_reversal_delta_n -lt 0) {
        $anyProjectionReversalImproved = $true
        $projectionReversalMixed = $true
    }
}
if (-not $anyProjectionReversalImproved) {
    $projectionReversalClearlyImproved = $false
}

$lengthChangeExplainable = $false
if ($pruning) {
    $removed = [double]$pruning.removed_dist_m
    $ratio = [double]$pruning.length_reduction_ratio
    $lengthChangeExplainable = ($removed -gt 0) -and ($ratio -gt 0) -and ($ratio -lt 0.15) -and (As-Bool $pruning.length_ok) -and (As-Bool $pruning.geometry_continuous)
}

$blockingGatesPass = $routeIssueConfirmed -and $repairNeeded -and $ib0dCandidatePass -and $downstreamRunnable -and $rawdataSafe -and $sequenceRowsStable -and $onRouteNotDegraded -and $branchAmbiguityNotIncreased -and $offRouteLowConfidenceNotIncreased -and $excursionsNotIncreased -and $lengthChangeExplainable

if (-not $rawdataSafe) {
    $PromotionGateStatus = "FAIL_RAWDATA_SAFETY"
    $PromotionNote = "Rawdata safety failed; repaired formal roots were not created."
} elseif (-not $downstreamRunnable) {
    $PromotionGateStatus = "FAIL_DOWNSTREAM"
    $PromotionNote = "Candidate downstream roots are incomplete; repaired formal roots were not created."
} elseif ($blockingGatesPass -and $projectionReversalClearlyImproved) {
    $PromotionGateStatus = "PASS_READY_FOR_FORMAL_ROOT"
    $PromotionNote = "Projection reversal improved and all promotion gates passed."
} elseif ($blockingGatesPass -and $projectionReversalMixed) {
    $PromotionGateStatus = "PASS_WITH_REMAP_REVIEW_NOTE"
    $PromotionNote = "Projection reversal mixed; branch ambiguity improved; on_route rows not degraded."
} else {
    $PromotionGateStatus = "FAIL_PROMOTION_GATE"
    $PromotionNote = "One or more promotion gates failed; repaired formal roots were not created."
}

$gateRows = @(
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "route_issue_confirmed"; exists = $routeIssueConfirmed; status = if ($routeIssueConfirmed) { "PASS" } else { "FAIL" }; path = $Evidence.RouteAxisSummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "repair_needed"; exists = $repairNeeded; status = if ($repairNeeded) { "PASS" } else { "FAIL" }; path = $Evidence.RepairPlanSummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "ib0d_candidate_pass"; exists = $ib0dCandidatePass; status = if ($ib0dCandidatePass) { "PASS" } else { "FAIL" }; path = $Evidence.PruningSummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "downstream_runnable"; exists = $downstreamRunnable; status = if ($downstreamRunnable) { "PASS" } else { "FAIL" }; path = "candidate roots"; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "rawdata_safe"; exists = $rawdataSafe; status = if ($rawdataSafe) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "sequence_rows_stable"; exists = $sequenceRowsStable; status = if ($sequenceRowsStable) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "on_route_not_degraded"; exists = $onRouteNotDegraded; status = if ($onRouteNotDegraded) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "threshold: no activity drops more than 10%" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "branch_ambiguity_not_increased"; exists = $branchAmbiguityNotIncreased; status = if ($branchAmbiguityNotIncreased) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "off_route_low_confidence_not_increased"; exists = $offRouteLowConfidenceNotIncreased; status = if ($offRouteLowConfidenceNotIncreased) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "excursions_not_increased"; exists = $excursionsNotIncreased; status = if ($excursionsNotIncreased) { "PASS" } else { "FAIL" }; path = $Evidence.RawdataSafetySummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "length_change_explainable"; exists = $lengthChangeExplainable; status = if ($lengthChangeExplainable) { "PASS" } else { "FAIL" }; path = $Evidence.PruningSummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "local_oscillation_after_false"; exists = (-not (As-Bool $pruning.local_oscillation_detected_after)); status = if (-not (As-Bool $pruning.local_oscillation_detected_after)) { "PASS" } else { "FAIL" }; path = $Evidence.PruningSummary; note = "" },
    [pscustomobject]@{ item_type = "promotion_gate"; item_name = "projection_reversal_mixed_allowed"; exists = $projectionReversalMixed; status = if ($projectionReversalMixed) { "PASS_WITH_REVIEW_NOTE" } else { "PASS" }; path = $Evidence.RawdataSafetySummary; note = "mixed projection reversal is not blocking when rawdata and other projection gates pass" }
)

$auditRows = @()
$auditRows += $evidenceRows
$auditRows += $candidateRootRows
$auditRows += $gateRows
$auditRows | Export-Csv -Path $AuditCsv -NoTypeInformation -Encoding UTF8

$ShouldCreateRepairedRoots = $PromotionGateStatus -in @("PASS_WITH_REMAP_REVIEW_NOTE", "PASS_READY_FOR_FORMAL_ROOT")
$PromotionRows = @()
if ($ShouldCreateRepairedRoots) {
    foreach ($root in $RootMap) {
        Copy-DirectoryContents -Source $root.source -Destination $root.destination
        $promotionSummary = [ordered]@{
            case_id = $CaseId
            stage = $root.stage
            source_candidate_root = $root.source
            repaired_formal_root = $root.destination
            promoted_from_candidate = $true
            promotion_gate_status = $PromotionGateStatus
            promotion_note = $PromotionNote
            previous_formal_root_preserved = $true
            rawdata_safe = $rawdataSafe
            remap_review_note = "projection reversal mixed; branch ambiguity improved; on_route rows not degraded"
            thci_v1_0c_recomputed_for_repaired_root = $false
            runtime_llm_allowed = $false
        }
        $summaryPath = Join-Path $root.destination "_qixing_via_corridor_repaired_formal_promotion_summary.json"
        $promotionSummary | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryPath -Encoding UTF8
        $PromotionRows += [pscustomobject]@{
            stage = $root.stage
            source_candidate_root = $root.source
            repaired_formal_root = $root.destination
            repaired_formal_root_exists = Test-Path -LiteralPath $root.destination
            promotion_summary_json = $summaryPath
        }
    }
}

$RepairedFormalRoots = [ordered]@{}
foreach ($root in $RootMap) {
    $RepairedFormalRoots[$root.stage] = $root.destination
}

$DecisionRow = [pscustomobject]@{
    case_id = $CaseId
    promotion_gate_status = $PromotionGateStatus
    promotion_note = $PromotionNote
    repaired_formal_roots_created = $ShouldCreateRepairedRoots
    previous_formal_roots_preserved = $true
    rawdata_safe = $rawdataSafe
    sequence_rows_stable = $sequenceRowsStable
    on_route_not_degraded = $onRouteNotDegraded
    branch_ambiguity_not_increased = $branchAmbiguityNotIncreased
    off_route_low_confidence_not_increased = $offRouteLowConfidenceNotIncreased
    excursions_not_increased = $excursionsNotIncreased
    projection_reversal_mixed = $projectionReversalMixed
    thci_v1_0c_recomputed_for_repaired_root = $false
    audit_csv = $AuditCsv
    summary_json = $SummaryJson
    repaired_formal_index_json = $IndexJson
    repaired_formal_index_csv = $IndexCsv
}
$DecisionRow | Export-Csv -Path $DecisionCsv -NoTypeInformation -Encoding UTF8

$BackendUsageNote = "qixing_lengshuikeng repaired formal root may be used as the current qixing route baseline with remap review note. Previous v1.3b formal roots are preserved. THCI v1.0c has not yet been recomputed for the repaired root."
$RemapReviewNote = "projection reversal mixed; branch ambiguity improved; on_route rows not degraded"

$Index = [ordered]@{
    case_id = $CaseId
    repaired_formal_status = if ($ShouldCreateRepairedRoots) { "created" } else { "not_created" }
    promotion_gate_status = $PromotionGateStatus
    previous_formal_status = "preserved"
    previous_formal_roots = $PreviousFormalRoots
    repaired_formal_roots = $RepairedFormalRoots
    rawdata_safety_status = if ($rawdata) { $rawdata.final_decision } else { $null }
    remap_review_note = $RemapReviewNote
    backend_usage_note = $BackendUsageNote
    thci_v1_0c_recomputed_for_repaired_root = $false
    outputs = [ordered]@{
        promotion_gate_audit_csv = $AuditCsv
        promotion_gate_decision_csv = $DecisionCsv
        promotion_gate_summary_json = $SummaryJson
        repaired_formal_index_json = $IndexJson
        repaired_formal_index_csv = $IndexCsv
    }
    runtime_llm_allowed = $false
}
$Index | ConvertTo-Json -Depth 8 | Set-Content -Path $IndexJson -Encoding UTF8

$IndexCsvRow = [pscustomobject]@{
    case_id = $CaseId
    repaired_formal_status = $Index.repaired_formal_status
    promotion_gate_status = $PromotionGateStatus
    previous_formal_status = "preserved"
    previous_formal_roots = ($PreviousFormalRoots.Values -join ";")
    repaired_formal_roots = ($RepairedFormalRoots.Values -join ";")
    rawdata_safety_status = if ($rawdata) { $rawdata.final_decision } else { "" }
    remap_review_note = $RemapReviewNote
    backend_usage_note = $BackendUsageNote
}
$IndexCsvRow | Export-Csv -Path $IndexCsv -NoTypeInformation -Encoding UTF8

$Summary = [ordered]@{
    case_id = $CaseId
    promotion_gate_status = $PromotionGateStatus
    promotion_note = $PromotionNote
    repaired_formal_roots_created = $ShouldCreateRepairedRoots
    route_issue_confirmed = $routeIssueConfirmed
    repair_needed = $repairNeeded
    ib0d_candidate_pass = $ib0dCandidatePass
    downstream_runnable = $downstreamRunnable
    rawdata_safe = $rawdataSafe
    sequence_rows_stable = $sequenceRowsStable
    on_route_not_degraded = $onRouteNotDegraded
    branch_ambiguity_not_increased = $branchAmbiguityNotIncreased
    off_route_low_confidence_not_increased = $offRouteLowConfidenceNotIncreased
    excursions_not_increased = $excursionsNotIncreased
    length_change_explainable = $lengthChangeExplainable
    projection_reversal_mixed = $projectionReversalMixed
    projection_reversal_clearly_improved = $projectionReversalClearlyImproved
    previous_formal_roots_preserved = $true
    previous_formal_roots = $PreviousFormalRoots
    repaired_formal_roots = $RepairedFormalRoots
    promotion_rows = $PromotionRows
    evidence_paths = $Evidence
    formal_review_status = if ($formalReview) { $formalReview.formal_review_status } else { $null }
    rawdata_safety_status = if ($rawdata) { $rawdata.final_decision } else { $null }
    remap_review_note = $RemapReviewNote
    backend_usage_note = $BackendUsageNote
    thci_v1_0c_recomputed_for_repaired_root = $false
    outputs = [ordered]@{
        audit_csv = $AuditCsv
        decision_csv = $DecisionCsv
        summary_json = $SummaryJson
        repaired_formal_index_json = $IndexJson
        repaired_formal_index_csv = $IndexCsv
    }
    runtime_llm_allowed = $false
    note = "This promotion gate creates a new repaired formal root family only when gates pass. Existing formal v1.3b roots and candidate roots are not overwritten."
}
$Summary | ConvertTo-Json -Depth 10 | Set-Content -Path $SummaryJson -Encoding UTF8

Write-Host "promotion_gate_status=$PromotionGateStatus"
Write-Host "repaired_formal_roots_created=$ShouldCreateRepairedRoots"
Write-Host "repaired_formal_index_json=$IndexJson"
Write-Host "previous_formal_roots_preserved=True"
Write-Host "formal_roots_overwritten=False"
Write-Host "backend_can_use_repaired_formal_roots=$ShouldCreateRepairedRoots"
Write-Host "remap_review_note=$RemapReviewNote"
Write-Host "audit_csv=$AuditCsv"
Write-Host "decision_csv=$DecisionCsv"
Write-Host "summary_json=$SummaryJson"
