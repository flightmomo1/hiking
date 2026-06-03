param(
    [string]$ProjectRoot = "C:\mountain_work\115_osm"
)

$ErrorActionPreference = "Stop"

$outRoot = Join-Path $ProjectRoot "outputs\thci_v1_0b_final_precommit"
$auditFp = Join-Path $outRoot "thci_v1_0b_final_precommit_audit.csv"
$decisionFp = Join-Path $outRoot "thci_v1_0b_final_precommit_decision.csv"

New-Item -ItemType Directory -Path $outRoot -Force | Out-Null

function New-AuditItem {
    param(
        [string]$ItemType,
        [string]$ItemName,
        [bool]$Required,
        [string]$RelativePath,
        [string]$PathType = "Any",
        [string]$Note = ""
    )

    $fullPath = if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        ""
    }
    else {
        Join-Path $ProjectRoot $RelativePath
    }

    $exists = $false
    if ($PathType -eq "Policy") {
        $exists = $true
        $fullPath = $RelativePath
    }
    elseif ($PathType -eq "Directory") {
        $exists = Test-Path -LiteralPath $fullPath -PathType Container
    }
    elseif ($PathType -eq "File") {
        $exists = Test-Path -LiteralPath $fullPath -PathType Leaf
    }
    else {
        $exists = Test-Path -LiteralPath $fullPath
    }

    $status = if ($Required -and -not $exists) { "FAIL" } else { "PASS" }

    return [PSCustomObject]@{
        item_type = $ItemType
        item_name = $ItemName
        required = $Required
        exists = $exists
        status = $status
        path = $fullPath
        note = $Note
    }
}

$items = @()

$items += New-AuditItem "decision_file" "THCI config bundle audit decision" $true "outputs\thci_v1_0_convergence_audit\thci_config_bundle_v1_0_convergence_decision.csv" "File"

$items += New-AuditItem "decision_file" "THCI axis scores v1.0 convergence decision" $true "outputs\thci_axis_scores_v1_0\_batch_summary\thci_axis_scores_v1_0_convergence_decision.csv" "File"
$items += New-AuditItem "decision_file" "THCI axis scores v1.0a convergence decision" $true "outputs\thci_axis_scores_v1_0a\_batch_summary\thci_axis_scores_v1_0a_convergence_decision.csv" "File"
$items += New-AuditItem "decision_file" "THCI axis scores v1.0b convergence decision" $true "outputs\thci_axis_scores_v1_0b\_batch_summary\thci_axis_scores_v1_0b_convergence_decision.csv" "File"

$items += New-AuditItem "decision_file" "THCI radar v1.0 convergence decision" $true "outputs\thci_radar_v1_0\_batch_summary\thci_radar_v1_0_convergence_decision.csv" "File"
$items += New-AuditItem "decision_file" "THCI radar v1.0b convergence decision" $true "outputs\thci_radar_v1_0b\_batch_summary\thci_radar_v1_0b_convergence_decision.csv" "File"

$items += New-AuditItem "comparison_file" "THCI v1.0/v1.0a/v1.0b comparison wide" $true "outputs\thci_version_comparison\thci_axis_scores_v1_0_v1_0a_v1_0b_comparison_wide.csv" "File"
$items += New-AuditItem "comparison_file" "THCI v1.0/v1.0a/v1.0b comparison long" $true "outputs\thci_version_comparison\thci_axis_scores_v1_0_v1_0a_v1_0b_comparison_long.csv" "File"

$items += New-AuditItem "recommended_root" "THCI axis scores v1.0b root" $true "outputs\thci_axis_scores_v1_0b" "Directory"
$items += New-AuditItem "recommended_root" "THCI radar v1.0b root" $true "outputs\thci_radar_v1_0b" "Directory"
$items += New-AuditItem "recommended_root" "THCI version comparison root" $true "outputs\thci_version_comparison" "Directory"

$items += New-AuditItem "documentation" "Latest handoff prompt" $true "runs\latest_handoff_prompt_updated_20260604_thci_version_comparison.md" "File"
$items += New-AuditItem "documentation" "Current pipeline README" $true "scripts\README_current_pipeline_updated_20260604_thci_version_comparison.md" "File"
$items += New-AuditItem "documentation" "Updated changelog" $true "runs\changelog_updated_20260604_thci_version_comparison.md" "File"
$items += New-AuditItem "documentation" "Current index" $true "runs\CURRENT_INDEX_updated_20260604_thci_version_comparison.md" "File"
$items += New-AuditItem "documentation" "Master organized changelog" $true "runs\115_osm_changelog_master_organized_20260604_thci_version_comparison.md" "File"
$items += New-AuditItem "documentation" "Changelog index" $true "runs\115_osm_changelog_index_20260604_thci_version_comparison.md" "File"

$items += New-AuditItem "script" "Compute THCI axis scores v1.0" $true "scripts\thci_compute_axis_scores_v1_0.py" "File"
$items += New-AuditItem "script" "Audit THCI axis scores v1.0 convergence" $true "scripts\audit_thci_axis_scores_v1_0_convergence.ps1" "File"
$items += New-AuditItem "script" "Plot THCI radar v1.0" $true "scripts\thci_plot_radar_v1_0.py" "File"
$items += New-AuditItem "script" "Audit THCI radar v1.0 convergence" $true "scripts\audit_thci_radar_v1_0_convergence.ps1" "File"
$items += New-AuditItem "script" "Diagnose THCI feature coverage v1.0a" $true "scripts\thci_diagnose_feature_coverage_v1_0a.py" "File"
$items += New-AuditItem "script" "Compute THCI axis scores v1.0a" $true "scripts\thci_compute_axis_scores_v1_0a.py" "File"
$items += New-AuditItem "script" "Audit THCI axis scores v1.0a convergence" $true "scripts\audit_thci_axis_scores_v1_0a_convergence.ps1" "File"
$items += New-AuditItem "script" "Compute THCI axis scores v1.0b" $true "scripts\thci_compute_axis_scores_v1_0b.py" "File"
$items += New-AuditItem "script" "Audit THCI axis scores v1.0b convergence" $true "scripts\audit_thci_axis_scores_v1_0b_convergence.ps1" "File"
$items += New-AuditItem "script" "Plot THCI radar v1.0b" $true "scripts\thci_plot_radar_v1_0b.py" "File"
$items += New-AuditItem "script" "Audit THCI radar v1.0b convergence" $true "scripts\audit_thci_radar_v1_0b_convergence.ps1" "File"

$items += New-AuditItem "config" "THCI axis definition v1.0" $true "configs\risk_semantics\thci_axis_definition_v1_0.csv" "File"
$items += New-AuditItem "config" "THCI feature mapping spec v1.0" $true "configs\risk_semantics\thci_feature_mapping_spec_v1_0.csv" "File"
$items += New-AuditItem "config" "THCI feature mapping v1.0" $true "configs\risk_semantics\thci_feature_mapping_v1_0.csv" "File"
$items += New-AuditItem "config" "THCI axis scoring rule v1.0" $true "configs\risk_semantics\thci_axis_scoring_rule_v1_0.csv" "File"
$items += New-AuditItem "config" "THCI normalization threshold v1.0" $true "configs\risk_semantics\thci_normalization_threshold_v1_0.csv" "File"

$items += New-AuditItem "boundary_check" "Do not require IB2D rerun" $true "policy: no IB2D rerun required for THCI v1.0b final pre-commit audit" "Policy" "This audit checks existing evidence only."
$items += New-AuditItem "boundary_check" "IB2D remains baseline route-risk visualization" $true "policy: IB2D remains baseline route-risk visualization" "Policy" "THCI v1.0b does not overwrite current IB2D outputs."
$items += New-AuditItem "boundary_check" "THCI v1.0b remains downstream calibrated six-axis interpretation layer" $true "policy: THCI v1.0b is downstream calibrated six-axis interpretation layer" "Policy" "Navigation semantics calibration is a THCI layer."
$items += New-AuditItem "boundary_check" "Future IB2D x THCI integration must be separate branch" $true "policy: future IB2D x THCI integration must be separate branch and must not overwrite current IB2D" "Policy" "Current package is not an IB2D integration branch."

$items | Export-Csv -LiteralPath $auditFp -NoTypeInformation -Encoding UTF8

$missingRequired = @($items | Where-Object { $_.required -and -not $_.exists })
$failRows = @($items | Where-Object { $_.status -eq "FAIL" })
$finalStatus = if ($missingRequired.Count -eq 0 -and $failRows.Count -eq 0) {
    "READY_FOR_COMMIT"
}
else {
    "FAIL"
}

$decision = [PSCustomObject]@{
    thci_v1_0b_final_package_status = $finalStatus
    required_item_count = @($items | Where-Object { $_.required }).Count
    existing_required_item_count = @($items | Where-Object { $_.required -and $_.exists }).Count
    missing_required_item_count = $missingRequired.Count
    fail_item_count = $failRows.Count
    ib2d_rerun_required = $false
    ib2d_boundary = "IB2D remains baseline route-risk visualization; THCI v1.0b remains downstream calibrated six-axis interpretation layer; future IB2D x THCI integration must be separate branch."
    audit_csv = $auditFp
}

$decision | Export-Csv -LiteralPath $decisionFp -NoTypeInformation -Encoding UTF8

foreach ($item in $items) {
    Write-Host (
        "{0}, {1}, required={2}, exists={3}, status={4}, path={5}" -f
        $item.item_type,
        $item.item_name,
        $item.required,
        $item.exists,
        $item.status,
        $item.path
    )
}

Write-Host "final decision: $finalStatus"
Write-Host "audit CSV: $auditFp"
Write-Host "decision CSV: $decisionFp"
