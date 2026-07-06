# Navigation risk definition update

更新目的：
- 將「迷航風險」明確定義為：走錯的機率 × 走錯後的恢復困難度。
- 新增「錯路後可恢復性」語意：山區岔路多、指標不足，且錯入支線後無法接回主線或車輛可達道路時，迷航風險提高。

產出檔案：
1. osm_semantic_risk_mapping_v1_4_navigation_updated.csv
   - 新增 junction_density_high
   - 新增 guidepost_deficit
   - 新增 poor_wrong_turn_recovery_access

2. thci_axis_definition_v1_1_navigation_updated.csv
   - 更新 navigation_risk_score 定義、include_features、exclude_features、note

3. thci_axis_scoring_rule_v1_1_navigation_updated.csv
   - 更新 navigation_risk_score score_inputs、formula_draft 與 threshold_policy
   - 新公式：0.35*route_choice_complexity_score + 0.30*navigation_support_deficit_score + 0.35*wrong_turn_recovery_difficulty_score

4. thci_feature_mapping_v1_2_navigation_updated.csv
   - 新增 network_junction_density_high_navigation_v1_2
   - 新增 osm_guidepost_deficit_navigation_v1_2
   - 新增 network_wrong_turn_recovery_access_navigation_v1_2

5. thci_normalization_threshold_v1_1_navigation_updated.csv
   - 新增 guidepost_deficit_ratio
   - 新增 wrong_turn_recovery_vehicle_road_access_km
   - 新增 wrong_turn_return_distance_m

注意：
- poor_wrong_turn_recovery_access 主要進 navigation_risk_score，secondary_axis 少量連結 support_difficulty_score。
- road/service/track/unclassified/residential 等道路可達性若用於「錯路後能否恢復」屬迷航風險；若用於「救援/撤退介入難易」屬支援不易，需避免重複計分。
