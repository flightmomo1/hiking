# Upslope high-score review radar axis method

右下角雷達圖聚焦 rank 1 高分複核區，而不是整條 GPX 平均。各軸先在 segment 層級算 0-1，再以 segment 長度加權平均；圖面顯示為 0-100。

雨水匯流沖刷敏感目前為靜態地形與圖資 proxy，不含活動當日雨勢加權，也不是正式水文模擬。

## 1. 落下距離長

- 資料欄位：max_source_relief_m
- 公式：clip(max_source_relief_m / 500, 0, 1)
- 0 分意義：上方複核來源與步道幾乎沒有高差。
- 100 分意義：上方複核來源與步道高差達 500 m 或以上。
- 限制：以等高線來源點推估高差，不是落石動能或真實落距模擬。

## 2. 下落路徑陡直

- 資料欄位：max_source_fall_gradient
- 公式：clip(max_source_fall_gradient / 1.0, 0, 1)
- 0 分意義：來源到步道的坡降比接近 0。
- 100 分意義：來源到步道的坡降比達 1.0 或以上。
- 限制：以來源點到步道的直線坡降比近似，未納入坡向、阻擋物或實際滾落路徑。

## 3. 上方可疑坡面密集

- 資料欄位：source_presence_score; fallback contributing_source_count
- 公式：source_presence_score if present, else clip(contributing_source_count / 10, 0, 1)
- 0 分意義：高分複核區上方幾乎沒有符合條件的可疑來源。
- 100 分意義：高分複核區上方可疑來源非常密集，或來源數達 10 個以上。
- 限制：來源密集代表需要複核，不等於每個來源都會崩落。

## 4. 步道受影響範圍廣

- 資料欄位：rank 1 hotspot length_m
- 公式：clip(hotspot_length_m / 600, 0, 1)
- 0 分意義：高分複核區不是連續路段或長度接近 0。
- 100 分意義：高分複核區連續長度達 600 m 或以上。
- 限制：此軸描述高分區沿步道延伸長度，不使用 direction spread / directional concentration。

## 5. 上方有崩塌地

- 資料欄位：collapse_mask_score
- 公式：collapse_mask_score
- 0 分意義：高分複核區上方或附近未命中既有崩塌遮罩 proxy。
- 100 分意義：高分複核區上方或附近與既有崩塌遮罩 proxy 強烈重疊。
- 限制：NLSC 崩塌遮罩是靜態圖資 proxy，不是即時崩塌或正式崩塌潛勢判定。

## 6. 雨水匯流沖刷敏感

- 資料欄位：watercourse_channel_score
- 公式：watercourse_channel_score
- 0 分意義：高分複核區附近未命中水系或溪溝 proxy。
- 100 分意義：高分複核區鄰近水系、溪溝或集水線 proxy，雨天可能較敏感。
- 限制：目前為靜態地形與圖資 proxy，不含活動當日雨勢加權，也不是正式水文模擬。

## V2 terrain-derived flowline / flow accumulation proxy proposal

可行方向：以 NLSC 等高線建立局部 DEM/TIN 或 raster surface，從坡面梯度推估 D8/D-infinity flow direction，再計算 flow accumulation、凹谷線與步道交會或近距離關係；同時用 NLSC watercourse / OSM waterway 作為校正與驗證層。

所需資料：足夠密度且拓樸合理的等高線、可靠的水系線、研究區邊界外擴 buffer、必要時補入 DEM 或 LiDAR-derived DEM 以避免等高線內插造成假谷線。

主要風險：等高線內插 DEM 可能產生平坦區與假洼地；沒有降雨資料時只能描述地形集水敏感度；flow accumulation 對解析度、填洼、外擴範圍非常敏感，若直接併入主分數容易過度精確化。
