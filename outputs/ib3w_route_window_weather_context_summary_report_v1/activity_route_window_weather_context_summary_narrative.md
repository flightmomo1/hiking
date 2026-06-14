# IB3W Route-window Weather Context Summary Report v1

- activity_id: `qixing_lengshuikeng_xiaoyoukeng_20260410_biji_gpx`
- route_window_count: 16
- route_distance_range_m: 0–4000
- local_time_range: 2026-04-11 05:35:47 → 2026-04-11 07:54:30

## 路段當下環境變化

- 氣溫：19.3°C → 21.5°C，變化 2.2°C。
- 相對濕度：92.6% → 87.7%，變化 -4.9%。
- 風速：1.1 m/s → 1.8 m/s，變化 0.7 m/s。

活動通過不同路段時，氣溫隨時間與路段逐步上升、相對濕度下降、風速略增；但全路段 heat index 未達標準計算門檻，available weather 不支持 heat/humid stress。

## 前期天氣背景

出發前 6h 觀測降雨背景值：0.5；出發前 24h 觀測降雨背景值：0.5；出發前 72h 觀測降雨背景值：7.5；出發前 7d 觀測降雨背景值：61.0；最後一次觀測降雨時間：2026-04-10T16:00:00+00:00；距活動開始約 5.596 小時前仍有觀測降雨；最後降雨測站：C0AC40

前期降雨是 lookback context：代表活動前某段時間曾發生觀測降雨，不能直接當成活動當下正在下雨。

## 時間語意與判讀邊界

- temperature / humidity / wind：近即時或短時段狀態，適合對應活動通過路段。
- precipitation：區間累積，代表觀測時間之前一段時間已發生的雨量。
- antecedent rain：活動前 lookback 背景，不能直接宣稱路面濕滑或土壤含水。
- water level 若未來納入：水位是近即時狀態，但造成水位的降雨可能有延後效應。
- 本報告不宣稱 WBGT、UV、直接日照、中暑/熱傷害、醫療判斷、THCI 或 final hiking risk。
- missing weather remains missing；zero_fallback_true_count 必須為 0。
