cd "C:\mountain_work\115_osm"

# =========================================================
# THCI config bundle v1.0 convergence audit
# Checks axis definition, mapping spec, feature mapping,
# scoring rules, and normalization thresholds.
# =========================================================

$axisFp      = ".\configs\risk_semantics\thci_axis_definition_v1_0.csv"
$specFp      = ".\configs\risk_semantics\thci_feature_mapping_spec_v1_0.csv"
$mappingFp   = ".\configs\risk_semantics\thci_feature_mapping_v1_0.csv"
$scoringFp   = ".\configs\risk_semantics\thci_axis_scoring_rule_v1_0.csv"
$thresholdFp = ".\configs\risk_semantics\thci_normalization_threshold_v1_0.csv"

$outDir = ".\outputs\thci_v1_0_convergence_audit"
$outCsv = Join-Path $outDir "thci_config_bundle_v1_0_convergence_audit.csv"
$outDecisionCsv = Join-Path $outDir "thci_config_bundle_v1_0_convergence_decision.csv"

New-Item -ItemType Directory -Force $outDir | Out-Null

$files = @(
  [pscustomobject]@{ name = "axis_definition"; path = $axisFp; required = $true },
  [pscustomobject]@{ name = "feature_mapping_spec"; path = $specFp; required = $true },
  [pscustomobject]@{ name = "feature_mapping"; path = $mappingFp; required = $true },
  [pscustomobject]@{ name = "axis_scoring_rule"; path = $scoringFp; required = $true },
  [pscustomobject]@{ name = "normalization_threshold"; path = $thresholdFp; required = $true }
)

$fileRows = foreach ($f in $files) {
  $exists = Test-Path $f.path
  $rowCount = if ($exists) {
    @(Import-Csv $f.path).Count
  } else {
    0
  }

  [pscustomobject]@{
    item_type = "file"
    item_name = $f.name
    path = $f.path
    exists = $exists
    row_count = $rowCount
    status = if ($exists -and $rowCount -gt 0) { "PASS" } else { "FAIL" }
    issue = if (-not $exists) { "missing_file" } elseif ($rowCount -le 0) { "empty_csv" } else { "" }
  }
}

$blocking = @()

foreach ($r in $fileRows) {
  if ($r.status -ne "PASS") {
    $blocking += "$($r.item_name):$($r.issue)"
  }
}

if ($blocking.Count -gt 0) {
  $fileRows | Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

  $decision = [pscustomobject]@{
    thci_config_bundle_status = "FAIL"
    reason = ($blocking -join ";")
    axis_n = 0
    mapping_n = 0
    scoring_rule_n = 0
    threshold_n = 0
    runtime_llm_allowed_any = ""
    mapping_needs_review_n = ""
    audit_csv = $outCsv
  }

  $decision | Export-Csv $outDecisionCsv -NoTypeInformation -Encoding UTF8
  $fileRows | Format-Table -AutoSize
  $decision | Format-List
  throw "THCI config bundle FAIL: $($blocking -join ';')"
}

$axis = @(Import-Csv $axisFp)
$mapping = @(Import-Csv $mappingFp)
$scoring = @(Import-Csv $scoringFp)
$threshold = @(Import-Csv $thresholdFp)

$axisIds = @($axis | ForEach-Object { "$($_.axis_id)".Trim() })

# ---------------------------------------------------------
# Axis definition QA
# ---------------------------------------------------------
$axisDuplicate = @(
  $axis |
    Group-Object axis_id |
    Where-Object { $_.Count -gt 1 } |
    ForEach-Object { $_.Name }
)

$axisRows = foreach ($a in $axis) {
  $issues = @()

  if ([string]::IsNullOrWhiteSpace("$($a.axis_id)")) { $issues += "empty_axis_id" }
  if ([string]::IsNullOrWhiteSpace("$($a.display_name_zh)")) { $issues += "empty_display_name_zh" }
  if ([string]::IsNullOrWhiteSpace("$($a.concept_definition)")) { $issues += "empty_concept_definition" }
  if ("$($a.direction)".Trim() -ne "higher_is_riskier") { $issues += "unexpected_direction" }
  if ("$($a.score_range)".Trim() -ne "0-1") { $issues += "unexpected_score_range" }
  if ($axisDuplicate -contains "$($a.axis_id)") { $issues += "duplicate_axis_id" }

  [pscustomobject]@{
    item_type = "axis_definition"
    item_name = $a.axis_id
    path = $axisFp
    exists = $true
    row_count = 1
    status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
    issue = ($issues -join ";")
  }
}

# ---------------------------------------------------------
# Feature mapping QA summary
# ---------------------------------------------------------
$mappingUnknownPrimaryAxis = @(
  $mapping |
    Where-Object { $axisIds -notcontains "$($_.primary_axis)".Trim() }
)

$mappingUnknownSecondaryAxis = @(
  $mapping |
    Where-Object {
      $sec = "$($_.secondary_axis)".Trim()
      $sec -ne "" -and $axisIds -notcontains $sec
    }
)

$mappingNeedsReview = @(
  $mapping | Where-Object { "$($_.review_status)".Trim() -eq "needs_review" }
)

$mappingAccepted = @(
  $mapping | Where-Object { "$($_.review_status)".Trim() -in @("draft_accepted", "accepted") }
)

$mappingAxisCoverage = $mapping |
  Group-Object primary_axis |
  ForEach-Object {
    [pscustomobject]@{
      axis_id = $_.Name
      mapping_count = $_.Count
      axis_known = ($axisIds -contains $_.Name)
    }
  }

$mappingMissingAxisCoverage = @(
  $axisIds |
    Where-Object {
      $axisId = $_
      -not ($mappingAxisCoverage | Where-Object { $_.axis_id -eq $axisId })
    }
)

$mappingSummaryIssues = @()
if ($mappingUnknownPrimaryAxis.Count -gt 0) { $mappingSummaryIssues += "unknown_primary_axis" }
if ($mappingUnknownSecondaryAxis.Count -gt 0) { $mappingSummaryIssues += "unknown_secondary_axis" }
if ($mappingMissingAxisCoverage.Count -gt 0) { $mappingSummaryIssues += "missing_axis_coverage=" + ($mappingMissingAxisCoverage -join "|") }

$mappingSummaryRow = [pscustomobject]@{
  item_type = "feature_mapping_summary"
  item_name = "thci_feature_mapping_v1_0"
  path = $mappingFp
  exists = $true
  row_count = $mapping.Count
  status = if ($mappingSummaryIssues.Count -eq 0) { "PASS" } else { "FAIL" }
  issue = ($mappingSummaryIssues -join ";")
}

# ---------------------------------------------------------
# Scoring rule QA
# ---------------------------------------------------------
$scoringRows = foreach ($s in $scoring) {
  $issues = @()
  $axisId = "$($s.axis_id)".Trim()

  if ($axisIds -notcontains $axisId) { $issues += "unknown_axis_id" }
  if ("$($s.runtime_llm_allowed)".Trim().ToLower() -ne "false") { $issues += "runtime_llm_allowed_not_false" }
  if ("$($s.output_range)".Trim() -ne "0-1") { $issues += "unexpected_output_range" }
  if ("$($s.clip_policy)".Trim() -ne "clip_0_1") { $issues += "unexpected_clip_policy" }
  if ([string]::IsNullOrWhiteSpace("$($s.aggregation_method)")) { $issues += "empty_aggregation_method" }
  if ([string]::IsNullOrWhiteSpace("$($s.normalization_method)")) { $issues += "empty_normalization_method" }

  [pscustomobject]@{
    item_type = "axis_scoring_rule"
    item_name = $axisId
    path = $scoringFp
    exists = $true
    row_count = 1
    status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
    issue = ($issues -join ";")
  }
}

$scoringAxisIds = @($scoring | ForEach-Object { "$($_.axis_id)".Trim() })
$missingScoringAxis = @($axisIds | Where-Object { $scoringAxisIds -notcontains $_ })

$scoringCoverageRow = [pscustomobject]@{
  item_type = "axis_scoring_coverage"
  item_name = "all_axes"
  path = $scoringFp
  exists = $true
  row_count = $scoring.Count
  status = if ($missingScoringAxis.Count -eq 0) { "PASS" } else { "FAIL" }
  issue = if ($missingScoringAxis.Count -gt 0) { "missing_scoring_axis=" + ($missingScoringAxis -join "|") } else { "" }
}

# ---------------------------------------------------------
# Threshold QA
# ---------------------------------------------------------
$thresholdRows = foreach ($t in $threshold) {
  $issues = @()
  $axisId = "$($t.axis_id)".Trim()

  if ($axisIds -notcontains $axisId) { $issues += "unknown_axis_id" }
  if ([string]::IsNullOrWhiteSpace("$($t.threshold_id)")) { $issues += "empty_threshold_id" }
  if ("$($t.normalization_method)".Trim() -ne "piecewise_linear") { $issues += "unexpected_normalization_method" }
  if ("$($t.clip_policy)".Trim() -ne "clip_0_1") { $issues += "unexpected_clip_policy" }

  $v0 = $null
  $v25 = $null
  $v50 = $null
  $v75 = $null
  $v1 = $null
  $numericOk = $true

  try { $v0 = [double]$t.score_0 } catch { $numericOk = $false }
  try { $v25 = [double]$t.score_0_25 } catch { $numericOk = $false }
  try { $v50 = [double]$t.score_0_50 } catch { $numericOk = $false }
  try { $v75 = [double]$t.score_0_75 } catch { $numericOk = $false }
  try { $v1 = [double]$t.score_1 } catch { $numericOk = $false }

  if (-not $numericOk) {
    $issues += "threshold_not_numeric"
  } elseif (-not ($v0 -le $v25 -and $v25 -le $v50 -and $v50 -le $v75 -and $v75 -le $v1)) {
    $issues += "threshold_not_monotonic"
  }

  [pscustomobject]@{
    item_type = "normalization_threshold"
    item_name = $t.threshold_id
    path = $thresholdFp
    exists = $true
    row_count = 1
    status = if ($issues.Count -eq 0) { "PASS" } else { "FAIL" }
    issue = ($issues -join ";")
  }
}

$thresholdAxisCoverage = $threshold |
  Group-Object axis_id |
  ForEach-Object {
    [pscustomobject]@{
      axis_id = $_.Name
      threshold_count = $_.Count
      axis_known = ($axisIds -contains $_.Name)
    }
  }

# Threshold table is not required to cover all axes in v1.0,
# because technical and baseline hazard can use mapping base_score.
$thresholdCoverageRow = [pscustomobject]@{
  item_type = "normalization_threshold_coverage"
  item_name = "threshold_axes"
  path = $thresholdFp
  exists = $true
  row_count = $threshold.Count
  status = "PASS"
  issue = "threshold_not_required_for_all_axes_v1_0"
}

# ---------------------------------------------------------
# Combine rows and decision
# ---------------------------------------------------------
$rows = @()
$rows += $fileRows
$rows += $axisRows
$rows += $mappingSummaryRow
$rows += $scoringRows
$rows += $scoringCoverageRow
$rows += $thresholdRows
$rows += $thresholdCoverageRow

$rows |
  Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

$failRows = @($rows | Where-Object { $_.status -eq "FAIL" })

$runtimeLlmAllowedAny = @(
  $scoring | Where-Object { "$($_.runtime_llm_allowed)".Trim().ToLower() -ne "false" }
).Count -gt 0

$decisionStatus = if (
  $failRows.Count -eq 0 -and
  $axis.Count -eq 6 -and
  $scoring.Count -eq 6 -and
  $mappingMissingAxisCoverage.Count -eq 0 -and
  -not $runtimeLlmAllowedAny
) {
  if ($mappingNeedsReview.Count -gt 0) {
    "CONVERGED_WITH_NEEDS_REVIEW"
  } else {
    "CONVERGED"
  }
} else {
  "FAIL"
}

$decision = [pscustomobject]@{
  axis_n = $axis.Count
  feature_mapping_n = $mapping.Count
  scoring_rule_n = $scoring.Count
  threshold_n = $threshold.Count
  fail_rows_n = $failRows.Count
  mapping_needs_review_n = $mappingNeedsReview.Count
  mapping_accepted_or_draft_accepted_n = $mappingAccepted.Count
  runtime_llm_allowed_any = $runtimeLlmAllowedAny
  mapping_axis_coverage_missing = ($mappingMissingAxisCoverage -join ";")
  scoring_axis_missing = ($missingScoringAxis -join ";")
  thci_config_bundle_status = $decisionStatus
  axis_definition_csv = $axisFp
  mapping_spec_csv = $specFp
  mapping_csv = $mappingFp
  scoring_rule_csv = $scoringFp
  threshold_csv = $thresholdFp
  audit_csv = $outCsv
}

$decision |
  Export-Csv $outDecisionCsv -NoTypeInformation -Encoding UTF8

Write-Host "--- THCI config bundle v1.0 convergence audit ---"

$rows |
  Select-Object item_type, item_name, status, row_count, issue |
  Format-Table -AutoSize

Write-Host ""
Write-Host "=== THCI config bundle convergence decision ==="
$decision | Format-List

Write-Host "wrote: $outCsv"
Write-Host "wrote: $outDecisionCsv"