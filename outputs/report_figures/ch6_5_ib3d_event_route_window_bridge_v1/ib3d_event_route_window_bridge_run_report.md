# CH6.5 IB3D Event Route Window Bridge v1

Route folder: `qixing_lengshuikeng`
Window size: `50 m`

## Method

- IB3D events remain elapsed-time intervals.
- Each event is mapped to route windows only through IB3A2 activity rows where `elapsed_sec` falls within the event interval.
- Route distance uses `reliable_route_dist_m` when available, then falls back to `route_dist_m` or `projected_route_dist_m` only if needed.
- Events without safe point-level route distance are marked `REVIEW_REQUIRED` and are not force-filled into a route window.
- This bridge does not modify v2.2.2 behavior curves and does not generate ability, THCI, radar, or final-risk scores.

## Outputs

### 3_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_3_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\3_1\qixing_lengshuikeng_3_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7873`
- IB3C event rows: `8`
- Bridge event rows: `7`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:29 | ROUTE_WINDOW_OVERLAY_READY:55`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_3_1_ib3d_event_route_window_overlay.csv`

### 8_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_8_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\8_1\qixing_lengshuikeng_8_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `8433`
- IB3C event rows: `16`
- Bridge event rows: `13`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_8_1_ib3d_event_route_window_overlay.csv`

### 9_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_9_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\9_1\qixing_lengshuikeng_9_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `11399`
- IB3C event rows: `13`
- Bridge event rows: `13`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_9_1_ib3d_event_route_window_overlay.csv`

### 13_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_13_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\13_1\qixing_lengshuikeng_13_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `8325`
- IB3C event rows: `10`
- Bridge event rows: `9`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:29 | ROUTE_WINDOW_OVERLAY_READY:55`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_13_1_ib3d_event_route_window_overlay.csv`

### 14_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_14_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\14_1\qixing_lengshuikeng_14_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7202`
- IB3C event rows: `11`
- Bridge event rows: `6`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:41 | ROUTE_WINDOW_OVERLAY_READY:43`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_14_1_ib3d_event_route_window_overlay.csv`

### 15_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_15_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\15_1\qixing_lengshuikeng_15_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `17282`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:33 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:51`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_15_1_ib3d_event_route_window_overlay.csv`

### 16_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_16_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\16_1\qixing_lengshuikeng_16_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `10200`
- IB3C event rows: `32`
- Bridge event rows: `27`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_16_1_ib3d_event_route_window_overlay.csv`

### 20_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_20_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\20_1\qixing_lengshuikeng_20_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `17452`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:43 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:41`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_20_1_ib3d_event_route_window_overlay.csv`

### 23_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_23_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\23_1\qixing_lengshuikeng_23_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `34808`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_23_1_ib3d_event_route_window_overlay.csv`

### 28_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_28_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\28_1\qixing_lengshuikeng_28_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `8636`
- IB3C event rows: `14`
- Bridge event rows: `13`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:42 | ROUTE_WINDOW_OVERLAY_READY:42`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_28_1_ib3d_event_route_window_overlay.csv`

### 29_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_29_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\29_1\qixing_lengshuikeng_29_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `23534`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:39 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:45`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_29_1_ib3d_event_route_window_overlay.csv`

### 30_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_30_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\30_1\qixing_lengshuikeng_30_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `17563`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:42 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:42`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_30_1_ib3d_event_route_window_overlay.csv`

### 33_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_33_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\33_1\qixing_lengshuikeng_33_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `6582`
- IB3C event rows: `3`
- Bridge event rows: `1`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:42 | ROUTE_WINDOW_OVERLAY_READY:42`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_33_1_ib3d_event_route_window_overlay.csv`

### 35_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_35_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\35_1\qixing_lengshuikeng_35_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `23200`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:41 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:43`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_35_1_ib3d_event_route_window_overlay.csv`

### 36_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_36_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\36_1\qixing_lengshuikeng_36_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `8015`
- IB3C event rows: `14`
- Bridge event rows: `12`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:44 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:40`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_36_1_ib3d_event_route_window_overlay.csv`

### 37_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_37_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\37_1\qixing_lengshuikeng_37_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `9533`
- IB3C event rows: `27`
- Bridge event rows: `27`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:31 | ROUTE_WINDOW_OVERLAY_READY:53`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_37_1_ib3d_event_route_window_overlay.csv`

### 38_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_38_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\38_1\qixing_lengshuikeng_38_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `16606`
- IB3C event rows: `1`
- Bridge event rows: `1`
- Event review required count: `1`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY_WITH_EVENT_REVIEW:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_38_1_ib3d_event_route_window_overlay.csv`

### 40_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_40_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\40_1\qixing_lengshuikeng_40_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7714`
- IB3C event rows: `9`
- Bridge event rows: `8`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_40_1_ib3d_event_route_window_overlay.csv`

### 41_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_41_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\41_1\qixing_lengshuikeng_41_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7077`
- IB3C event rows: `8`
- Bridge event rows: `8`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:31 | ROUTE_WINDOW_OVERLAY_READY:53`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_41_1_ib3d_event_route_window_overlay.csv`

### 42_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_42_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\42_1\qixing_lengshuikeng_42_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `10287`
- IB3C event rows: `30`
- Bridge event rows: `23`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_42_1_ib3d_event_route_window_overlay.csv`

### 43_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_43_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\43_1\qixing_lengshuikeng_43_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `11451`
- IB3C event rows: `44`
- Bridge event rows: `39`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:42 | ROUTE_WINDOW_OVERLAY_READY:42`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_43_1_ib3d_event_route_window_overlay.csv`

### 44_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_44_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\44_1\qixing_lengshuikeng_44_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7010`
- IB3C event rows: `12`
- Bridge event rows: `11`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_44_1_ib3d_event_route_window_overlay.csv`

### 45_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_45_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\45_1\qixing_lengshuikeng_45_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `7227`
- IB3C event rows: `5`
- Bridge event rows: `4`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:29 | ROUTE_WINDOW_OVERLAY_READY:55`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_45_1_ib3d_event_route_window_overlay.csv`

### 46_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_46_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\46_1\qixing_lengshuikeng_46_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `10318`
- IB3C event rows: `39`
- Bridge event rows: `33`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:30 | ROUTE_WINDOW_OVERLAY_READY:54`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_46_1_ib3d_event_route_window_overlay.csv`

### 48_1

- IB3A2 input: `D:\mountain_work\115_osm\outputs\ib3a2_on_route_activity_filter_v4b_after_forced_route\qixing_lengshuikeng\qixing_lengshuikeng_48_1_mapmatched_activity_labeled.csv`
- IB3C input: `D:\mountain_work\115_osm\outputs\ib3c_activity_behavior_events_v1c_recovery_speed07_after_forced_route\qixing_lengshuikeng\48_1\qixing_lengshuikeng_48_1_ib3c_behavior_events.csv`
- Route distance source: `reliable_route_dist_m`
- Activity rows: `11622`
- IB3C event rows: `42`
- Bridge event rows: `34`
- Event review required count: `0`
- Overlay window rows: `84`
- Overlay status distribution: `NO_ACTIVITY_POINTS_IN_ROUTE_WINDOW:41 | ROUTE_WINDOW_OVERLAY_READY:43`
- Overlay CSV: `D:\mountain_work\115_osm\outputs\report_figures\ch6_5_ib3d_event_route_window_bridge_v1\activity_48_1_ib3d_event_route_window_overlay.csv`
