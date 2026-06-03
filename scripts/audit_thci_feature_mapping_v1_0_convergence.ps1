cd "C:\mountain_work\115_osm"

# =========================================================
# THCI feature mapping v1.0 convergence audit
# axis definition + mapping spec + mapping table QA
# =========================================================

$axisFp = ".\configs\risk_semantics\thci_axis_definition_v1_0.csv"
$specFp = ".\configs\risk_semantics\thci_feature_mapping_spec_v1_0.csv"
$mapFp  = ".\configs\risk_semantics\thci_feature_mapping_v1_0.csv"

$outDir = ".\outputs\thci_v1_0_convergence_audit"
$outCsv = Join-Path $outDir "thci_feature_mapping_v1_0_convergence_audit.csv"
$outDecisionCsv = Join-Path $outDir "thci_feature_mapping_v1_0_convergence_decision.csv"

New-Item -ItemType Directory -Force $outDir | Out-Null

if (-not (Test-Path $axisFp)) {
  throw "MISSING axis definition CSV: $axisFp"
}
if (-not (Test-Path $specFp)) {
  throw "MISSING feature mapping spec CSV: $specFp"
}
if (-not (Test-Path $mapFp)) {
  throw "MISSING feature mapping CSV: $mapFp"
}

$axis = @(Import-Csv $axisFp)
$spec = @(Import-Csv $specFp)
$map  = @(Import-Csv $mapFp)

$axisIds = @($axis | ForEach-Object { $_.axis_id })

$requiredColumns = @(
  $spec |
    Where-Object { "$($_.required)".Trim().ToLower() -eq "true" } |
    ForEach-Object { $_.column_name }
)

$mapCols = if ($map.Count -gt 0) {
  @($map[0].PSObject.Properties.Name)
} else {
  @()
}

$missingRequiredColumns = @(
  $requiredColumns |
    Where-Object { $mapCols -notcontains $_ }
)

$duplicateMappingIds = @(
  $map |
    Group-Object mapping_id |
    Where-Object { $_.Count -gt 1 } |
    ForEach-Object { $_.Name }
)

$rows = foreach ($r in $map) {
  $issues = @()

  foreach ($col in $requiredColumns) {
    if ($mapCols -notcontains $col) {
      $issues += "missing_required_column:$col"
    } elseif ([string]::IsNullOrWhiteSpace("$($r.$col)")) {
      $issues += "empty_required_value:$col"
    }
  }

  $primaryAxis = "$($r.primary_axis)".Trim()
  $secondaryAxis = "$($r.secondary_axis)".Trim()

  if ($axisIds -notcontains $primaryAxis) {
    $issues += "unknown_primary_axis"
  }

  if ($secondaryAxis -ne "" -and $axisIds -notcontains $secondaryAxis) {
    $issues += "unknown_secondary_axis"
  }

  $effectDirection = "$($r.effect_direction)".Trim()
  if ($effectDirection -notin @("increase", "decrease", "contextual")) {
    $issues += "invalid_effect_direction"
  }

  $baseWeightOk = $true
  $baseScoreOk = $true
  $baseWeight = $null
  $baseScore = $null

  try {
    $baseWeight = [double]$r.base_weight
  } catch {
    $baseWeightOk = $false
  }

  try {
    $baseScore = [double]$r.base_score
  } catch {
    $baseScoreOk = $false
  }

  if (-not $baseWeightOk) {
    $issues += "base_weight_not_numeric"
  } elseif ($baseWeight -lt 0 -or $baseWeight -gt 1) {
    $issues += "base_weight_out_of_range_0_1"
  }

  if (-not $baseScoreOk) {
    $issues += "base_score_not_numeric"
  } elseif ($baseScore -lt -1 -or $baseScore -gt 1) {
    $issues += "base_score_out_of_range_minus1_1"
  } elseif ($effectDirection -eq "increase" -and ($baseScore -lt 0 -or $baseScore -gt 1)) {
    $issues += "increase_base_score_not_0_1"
  } elseif ($effectDirection -eq "decrease" -and ($baseScore -gt 0)) {
    $issues += "decrease_base_score_positive"
  }

  $reviewStatus = "$($r.review_status)".Trim()
  if ($reviewStatus -notin @("draft", "draft_accepted", "needs_review", "deprecated", "accepted")) {
    $issues += "invalid_review_status"
  }

  if ($secondaryAxis -ne "" -and [string]::IsNullOrWhiteSpace("$($r.double_count_guard)")) {
    $issues += "missing_double_count_guard_for_secondary_axis"
  }

  if ($duplicateMappingIds -contains "$($r.mapping_id)") {
    $issues += "duplicate_mapping_id"
  }

  [pscustomobject]@{
    mapping_id = $r.mapping_id
    normalized_class = $r.normalized_class
    primary_axis = $primaryAxis
    secondary_axis = $secondaryAxis
    effect_direction = $effectDirection
    base_weight = $r.base_weight
    base_score = $r.base_score
    review_status = $reviewStatus
    issue_count = $issues.Count
    issues = ($issues -join ";")
  }
}

$rows |
  Export-Csv $outCsv -NoTypeInformation -Encoding UTF8

$axisCoverage = $map |
  Group-Object primary_axis |
  ForEach-Object {
    [pscustomobject]@{
      axis_id = $_.Name
      mapping_count = $_.Count
      axis_known = ($axisIds -contains $_.Name)
    }
  }

$missingAxisCoverage = @(
  $axisIds |
    Where-Object {
      $axisId = $_
      -not ($axisCoverage | Where-Object { $_.axis_id -eq $axisId })
    }
)

$failRows = @($rows | Where-Object { $_.issue_count -gt 0 })
$needsReviewRows = @($rows | Where-Object { $_.review_status -eq "needs_review" })
$acceptedRows = @($rows | Where-Object { $_.review_status -in @("draft_accepted", "accepted") })

$decisionStatus = if (
  $map.Count -gt 0 -and
  $missingRequiredColumns.Count -eq 0 -and
  $failRows.Count -eq 0 -and
  $missingAxisCoverage.Count -eq 0
) {
  if ($needsReviewRows.Count -gt 0) {
    "CONVERGED_WITH_NEEDS_REVIEW"
  } else {
    "CONVERGED"
  }
} else {
  "FAIL"
}

$decision = [pscustomobject]@{
  mapping_rows = $map.Count
  axis_rows = $axis.Count
  required_columns_n = $requiredColumns.Count
  missing_required_columns = ($missingRequiredColumns -join ";")
  duplicate_mapping_ids = ($duplicateMappingIds -join ";")
  axis_coverage_missing = ($missingAxisCoverage -join ";")
  issue_rows_n = $failRows.Count
  needs_review_n = $needsReviewRows.Count
  accepted_or_draft_accepted_n = $acceptedRows.Count
  thci_mapping_status = $decisionStatus
  axis_definition_csv = $axisFp
  mapping_spec_csv = $specFp
  mapping_csv = $mapFp
  audit_csv = $outCsv
}

$decision |
  Export-Csv $outDecisionCsv -NoTypeInformation -Encoding UTF8

Write-Host "--- THCI feature mapping v1.0 convergence audit ---"

$rows |
  Select-Object mapping_id, primary_axis, secondary_axis, effect_direction, base_weight, base_score, review_status, issue_count, issues |
  Format-Table -AutoSize

Write-Host ""
Write-Host "=== Axis coverage ==="
$axisCoverage | Format-Table -AutoSize

Write-Host ""
Write-Host "=== THCI mapping convergence decision ==="
$decision | Format-List

Write-Host "wrote: $outCsv"
Write-Host "wrote: $outDecisionCsv"