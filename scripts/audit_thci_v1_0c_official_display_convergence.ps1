param()

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\mountain_work\115_osm"
$Cases = @(
  "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
  "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
  "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
  "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
  "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b"
)

$AxisRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0c"
$RadarRoot = Join-Path $ProjectRoot "outputs\thci_radar_v1_0c"
$IntegratedAutoRoot = Join-Path $ProjectRoot "outputs\ib2d_thci_radar_v1_0c"
$IntegratedPngRoot = Join-Path $ProjectRoot "outputs\ib2d_thci_radar_v1_0c_ib2d_png"
$V10bAxisRoot = Join-Path $ProjectRoot "outputs\thci_axis_scores_v1_0b"
$V10bRadarRoot = Join-Path $ProjectRoot "outputs\thci_radar_v1_0b"
$OutRoot = Join-Path $ProjectRoot "outputs\thci_v1_0c_official_display_audit"
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

$Axes = @(
  "physical_difficulty_score",
  "technical_difficulty_score",
  "baseline_hazard_score",
  "navigation_risk_score",
  "support_difficulty_score",
  "weather_impact_score"
)

function Read-FirstCsvRow($Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  $rows = Import-Csv -LiteralPath $Path -Encoding UTF8
  if ($rows.Count -eq 0) { return $null }
  return @($rows)[0]
}

function Read-JsonObject($Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function To-DoubleOrNull($Value) {
  $text = [string]$Value
  $number = 0.0
  if ([double]::TryParse($text, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
    return $number
  }
  return $null
}

$Rows = @()
foreach ($CaseId in $Cases) {
  $AxisCsv = Join-Path $AxisRoot "$CaseId\$($CaseId)_thci_axis_scores_v1_0c.csv"
  $AxisJson = Join-Path $AxisRoot "$CaseId\$($CaseId)_thci_axis_score_summary_v1_0c.json"
  $RadarPng = Join-Path $RadarRoot "$CaseId\$($CaseId)_thci_radar_v1_0c.png"
  $RadarJson = Join-Path $RadarRoot "$CaseId\$($CaseId)_thci_radar_summary_v1_0c.json"
  $IntegratedAutoHtml = Join-Path $IntegratedAutoRoot "$CaseId\$($CaseId)_ib2d_thci_v1_0c_integrated_map.html"
  $IntegratedPngHtml = Join-Path $IntegratedPngRoot "$CaseId\$($CaseId)_ib2d_thci_v1_0c_integrated_map.html"
  $V10bCsv = Join-Path $V10bAxisRoot "$CaseId\$($CaseId)_thci_axis_scores_v1_0b.csv"

  $AxisRow = Read-FirstCsvRow $AxisCsv
  $V10bRow = Read-FirstCsvRow $V10bCsv
  $AxisSummary = Read-JsonObject $AxisJson
  $RadarSummary = Read-JsonObject $RadarJson

  $Issues = New-Object System.Collections.Generic.List[string]
  if (-not (Test-Path -LiteralPath $AxisCsv)) { $Issues.Add("missing_v1_0c_axis_csv") }
  if (-not (Test-Path -LiteralPath $AxisJson)) { $Issues.Add("missing_v1_0c_axis_summary_json") }
  if (-not (Test-Path -LiteralPath $RadarPng)) { $Issues.Add("missing_v1_0c_radar_png") }
  if (-not (Test-Path -LiteralPath $RadarJson)) { $Issues.Add("missing_v1_0c_radar_summary_json") }
  if (-not (Test-Path -LiteralPath $IntegratedAutoHtml)) { $Issues.Add("missing_v1_0c_integrated_auto_html") }
  if (-not (Test-Path -LiteralPath $IntegratedPngHtml)) { $Issues.Add("missing_v1_0c_integrated_ib2d_png_html") }
  if (-not (Test-Path -LiteralPath $V10bAxisRoot)) { $Issues.Add("missing_v1_0b_axis_root") }
  if (-not (Test-Path -LiteralPath $V10bRadarRoot)) { $Issues.Add("missing_v1_0b_radar_root") }

  $Weather = $null
  $PrevWeather = $null
  $WeatherRangeOk = $false
  $WeatherDiffers = $false
  if ($AxisRow -ne $null) {
    $Weather = To-DoubleOrNull $AxisRow.weather_impact_score
    $PrevWeather = To-DoubleOrNull $AxisRow.previous_v1_0b_weather_impact_score
    $WeatherRangeOk = ($Weather -ne $null -and $Weather -ge 0 -and $Weather -le 1)
    $WeatherDiffers = ($Weather -ne $null -and $PrevWeather -ne $null -and [math]::Abs($Weather - $PrevWeather) -gt 0.000000001)
    if ($AxisRow.scoring_version -ne "v1.0c") { $Issues.Add("axis_scoring_version_not_v1_0c") }
    if ([string]$AxisRow.calibrated_from_v1_0b -notin @("True","true","1")) { $Issues.Add("axis_calibrated_from_v1_0b_not_true") }
    if ([string]$AxisRow.weather_semantics_calibrated -notin @("True","true","1")) { $Issues.Add("axis_weather_semantics_calibrated_not_true") }
    foreach ($Axis in $Axes) {
      $Value = To-DoubleOrNull $AxisRow.$Axis
      if ($Value -eq $null -or $Value -lt 0 -or $Value -gt 1) { $Issues.Add("invalid_axis_score_$Axis") }
    }
  }
  if (-not $WeatherRangeOk) { $Issues.Add("weather_score_not_numeric_or_out_of_range") }
  if (-not $WeatherDiffers) { $Issues.Add("weather_impact_not_different_from_v1_0b") }

  if ($AxisSummary -ne $null) {
    if ($AxisSummary.scoring_version -ne "v1.0c") { $Issues.Add("summary_scoring_version_not_v1_0c") }
    if ($AxisSummary.calibrated_from_v1_0b -ne $true) { $Issues.Add("summary_calibrated_from_v1_0b_not_true") }
    if ($AxisSummary.weather_semantics_calibrated -ne $true) { $Issues.Add("summary_weather_semantics_calibrated_not_true") }
    if ($AxisSummary.runtime_llm_allowed -ne $false) { $Issues.Add("summary_runtime_llm_allowed_not_false") }
    if ($AxisSummary.non_weather_axes_copied_from_v1_0b -ne $true) { $Issues.Add("non_weather_axes_not_marked_copied_from_v1_0b") }
  }

  if ($RadarSummary -ne $null) {
    if ($RadarSummary.scoring_version -ne "v1.0c") { $Issues.Add("radar_scoring_version_not_v1_0c") }
    if ($RadarSummary.calibrated_from_v1_0b -ne $true) { $Issues.Add("radar_calibrated_from_v1_0b_not_true") }
    if ($RadarSummary.weather_semantics_calibrated -ne $true) { $Issues.Add("radar_weather_semantics_calibrated_not_true") }
    if ($RadarSummary.current_recommended_display_version -ne $true) { $Issues.Add("radar_current_recommended_display_version_not_true") }
    if ($RadarSummary.previous_recommended_version -ne "v1.0b") { $Issues.Add("radar_previous_recommended_version_not_v1_0b") }
    if ($RadarSummary.runtime_llm_allowed -ne $false) { $Issues.Add("radar_runtime_llm_allowed_not_false") }
    if ([string]::IsNullOrWhiteSpace([string]$RadarSummary.hydrology_topography_review_status)) { $Issues.Add("missing_hydrology_topography_review_status") }
  }

  $Status = if ($Issues.Count -eq 0) { "PASS" } else { "FAIL" }
  $Blocking = if ($Issues.Count -eq 0) { "" } else { ($Issues -join "|") }
  $Row = [pscustomobject]@{
    case_id = $CaseId
    case_status = $Status
    v1_0c_axis_scores_exists = (Test-Path -LiteralPath $AxisCsv)
    v1_0c_axis_summary_exists = (Test-Path -LiteralPath $AxisJson)
    v1_0c_radar_png_exists = (Test-Path -LiteralPath $RadarPng)
    v1_0c_radar_summary_exists = (Test-Path -LiteralPath $RadarJson)
    integrated_auto_html_exists = (Test-Path -LiteralPath $IntegratedAutoHtml)
    integrated_ib2d_png_html_exists = (Test-Path -LiteralPath $IntegratedPngHtml)
    scoring_version = if ($AxisRow -ne $null) { $AxisRow.scoring_version } else { "" }
    calibrated_from_v1_0b = if ($AxisSummary -ne $null) { $AxisSummary.calibrated_from_v1_0b } else { "" }
    weather_semantics_calibrated = if ($AxisSummary -ne $null) { $AxisSummary.weather_semantics_calibrated } else { "" }
    current_recommended_display_version = if ($RadarSummary -ne $null) { $RadarSummary.current_recommended_display_version } else { "" }
    previous_recommended_version = if ($RadarSummary -ne $null) { $RadarSummary.previous_recommended_version } else { "" }
    v1_0b_preserved = ((Test-Path -LiteralPath $V10bAxisRoot) -and (Test-Path -LiteralPath $V10bRadarRoot))
    weather_impact_score = $Weather
    previous_v1_0b_weather_impact_score = $PrevWeather
    weather_score_range_ok = $WeatherRangeOk
    weather_impact_differs_from_v1_0b = $WeatherDiffers
    hydrology_topography_review_status = if ($RadarSummary -ne $null) { $RadarSummary.hydrology_topography_review_status } else { "" }
    blocking_issue = $Blocking
  }
  $Rows += $Row
  Write-Host "$($Row.case_id), $($Row.case_status), v1_0c_radar_png_exists=$($Row.v1_0c_radar_png_exists), integrated_auto_html_exists=$($Row.integrated_auto_html_exists), integrated_ib2d_png_html_exists=$($Row.integrated_ib2d_png_html_exists), scoring_version=$($Row.scoring_version), current_recommended_display_version=$($Row.current_recommended_display_version), weather_score_range_ok=$($Row.weather_score_range_ok), blocking_issue=$($Row.blocking_issue)"
}

$AuditCsv = Join-Path $OutRoot "thci_v1_0c_official_display_convergence_audit.csv"
$DecisionCsv = Join-Path $OutRoot "thci_v1_0c_official_display_convergence_decision.csv"
$Rows | Export-Csv -LiteralPath $AuditCsv -Encoding UTF8 -NoTypeInformation

$FinalStatus = if (($Rows | Where-Object { $_.case_status -ne "PASS" }).Count -eq 0) {
  "CURRENT_RECOMMENDED_VERSION"
} else {
  "FAIL"
}

$Decision = [pscustomobject]@{
  THCI_V1_0C_OFFICIAL_DISPLAY_STATUS = $FinalStatus
  cases_n = $Cases.Count
  pass_n = @($Rows | Where-Object { $_.case_status -eq "PASS" }).Count
  v1_0b_preserved = ((Test-Path -LiteralPath $V10bAxisRoot) -and (Test-Path -LiteralPath $V10bRadarRoot))
  audit_csv = $AuditCsv
}
$Decision | Export-Csv -LiteralPath $DecisionCsv -Encoding UTF8 -NoTypeInformation

Write-Host "final decision: THCI_V1_0C_OFFICIAL_DISPLAY_STATUS=$FinalStatus"
