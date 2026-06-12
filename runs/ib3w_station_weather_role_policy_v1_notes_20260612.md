# IB3W Station Weather Role Policy v1 Notes

- 日期：2026-06-12
- 分支：codex/ib3w-station-weather-role-policy-v1
- 上游基底：bbcf164 Add IB3W station elevation 1D 2D map
- 本分支範圍：定義 IB3W station weather role policy
- 非本分支範圍：weather/hydro observation join、weather/hydro fusion、route risk / radar / THCI 調整

## 1. Background

前一階段完成 weather / water station elevation final evidence 與 1D/2D HTML QA。

目前已知問題：

    elevation_final_status 只代表測站高程 evidence 是否可信。
    它不代表該測站是否適合代表七星山登山路線的局部天氣。

例如，台北盆地測站可能因為 NLSC contour lookup 較穩定而得到 FINAL_ACCEPTABLE，
但它仍可能只是 basin contrast / regional background station，而不是 route-local representative station。

## 2. Purpose

本分支定義 station weather role policy v1，將以下概念拆開：

    elevation_confidence
    observation_quality
    route_weather_relevance
    station_weather_role

此 policy 是後續 weather context fusion 的前置規格，不直接進行 fusion。

## 3. Policy file

新增：

    configs\weather_context\ib3w_station_weather_role_policy_v1.csv

此 CSV 定義：

    concept
    station_weather_role
    scoring_dimension
    status
    guardrail

## 4. Station weather roles

v1 定義六種 station role：

    ROUTE_NEAR
    TERRAIN_SIMILAR
    UPWIND_MONITOR
    BASIN_CONTRAST
    REGIONAL_BACKGROUND
    LOW_RELEVANCE_REVIEW

### ROUTE_NEAR

測站接近登山路線，可作為局部天氣候選代表站。

### TERRAIN_SIMILAR

測站不一定最近，但海拔帶、坡向、稜線/谷地/迎風面等地形條件與路線相似。

### UPWIND_MONITOR

測站位於當下或典型風場的上風處，可用於監控即將進入路線的天氣變化。

### BASIN_CONTRAST

測站位於台北盆地或低海拔區，可作為山區與盆地的背景差異或對照站。

### REGIONAL_BACKGROUND

測站描述區域大氣背景狀態，但不直接代表路線局部天氣。

### LOW_RELEVANCE_REVIEW

測站距離、地形、觀測品質或角色不明確，需保留 review，不作為 primary route-local weather context。

## 5. Scoring dimensions

後續 station role assignment 可以參考以下維度：

    distance_to_route_m
    elevation_delta_m
    observation_age_min
    observation_update_interval_min
    variable_coverage_pressure
    variable_coverage_temperature
    variable_coverage_humidity
    variable_coverage_wind
    variable_coverage_rainfall
    variable_coverage_cloud_visibility
    terrain_similarity
    upwind_relevance
    basin_mountain_contrast

其中 observation quality 應包含：

    資料是否即時
    更新頻率是否穩定
    變數是否完整
    是否有 pressure / wind / temperature / humidity / rainfall / cloud or visibility proxy
    是否超出可接受時間窗

## 6. Relationship to NLSC / IB1E route terrain

未來 route-local weather context 可以結合：

    IB1E route profile
    NLSC elevation / contour window
    route slope
    route terrain exposure
    ridge / valley / slope context
    distance to waterway / wetland
    station elevation
    station-to-route distance
    station-to-route elevation delta

用於判斷測站與路線區段之間的天氣代表性。

## 7. Interpretation rule

不可將 elevation_final_status 直接解讀為 station weather relevance。

正確語意：

    elevation_final_status
    = 測站高程 evidence 的可信度

    observation_quality
    = 測站觀測資料是否新、完整、穩定

    route_weather_relevance
    = 測站是否有助於推估該路線的局部天氣

    station_weather_role
    = 測站在監控網絡中的功能角色

## 8. Guardrails

本分支延續 IB3W weather/hydro context guardrails：

    Missing weather is not normal.
    Missing rainfall is not 0 mm.
    Missing wind/temp/hydro is not unchanged.
    0 mm rainfall only valid when trusted source explicitly reports zero.
    No zero fallback.
    No route risk adjustment.
    No radar adjustment.
    No THCI adjustment.
    No weather/hydro fusion in this branch.

## 9. Downstream usage

後續可新增 station role assignment script，輸出欄位例如：

    station_weather_role
    station_weather_role_status
    elevation_confidence
    observation_quality_score
    route_weather_relevance_score
    monitoring_priority_score
    route_context_use_policy

可能的下游邏輯：

    ROUTE_NEAR + high observation quality
    → candidate primary local weather station

    TERRAIN_SIMILAR + good observation quality
    → terrain analog weather station

    UPWIND_MONITOR + timely wind/rain/humidity
    → incoming weather monitor

    BASIN_CONTRAST + high observation quality
    → basin/mountain contrast station

    LOW_RELEVANCE_REVIEW
    → audit only or downweighted candidate

## 10. Boundary

本分支只定義 policy，不產出觀測融合結果。

本分支不宣稱任何 weather station 已足以代表七星山路線。
本分支也不調整既有 route risk / radar / THCI。
