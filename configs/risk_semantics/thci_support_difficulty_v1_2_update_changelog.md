# THCI support_difficulty_score v1.2 update changelog

## 更新重點

本次更新將「支援不易」由概念式公式修正為四項子分數加權，並補入遊客中心、警察站、管理站、臨時起降場、吊掛空地與關鍵橋梁／通行節點瓶頸等語意。

## 新版定義

支援不易描述登山路線在發生體力不支、受傷、迷途、天候惡化或其他突發事件時，外部支援、撤退、救援、暫時避難與後送作業取得的困難程度。

核心語意：出事後，不容易走出去，也不容易讓人進來救。

## 新版公式

```text
support_difficulty_score =
0.40 * evacuation_access_difficulty_score
+ 0.25 * support_facility_deficit_score
+ 0.20 * rescue_operation_difficulty_score
+ 0.15 * critical_link_bottleneck_score
```

## 新增 risk semantics

- visitor_center_available
- police_station_available
- ranger_or_management_station_available
- emergency_landing_site_available
- poor_vehicle_access_branch
- long_route_without_exit
- support_facility_deficit
- poor_aerial_rescue_condition
- critical_bridge_or_access_bottleneck

## 檔案輸出

- osm_semantic_risk_mapping_v1_5_support_updated.csv
- thci_axis_definition_v1_2_support_updated.csv
- thci_axis_scoring_rule_v1_2_support_updated.csv
- thci_feature_mapping_v1_3_support_updated.csv
- thci_normalization_threshold_v1_2_support_updated.csv
