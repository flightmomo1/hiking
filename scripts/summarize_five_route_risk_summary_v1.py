from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\mountain_work\115_osm")

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

OUT_DIR = ROOT / "outputs" / "thci_route_metric_summary_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "five_route_risk_summary.csv"

RISK_BANDS = ["low", "moderate", "high", "very_high", "unknown"]

def first_existing(candidates):
    for fp in candidates:
        if fp.exists():
            return fp
    return None

def find_risk_csv(case_id):
    candidates = [
        ROOT / "outputs" / "ib2_v2_route_risk_v1_3b_contract_qa" / case_id / f"{case_id}_route_risk_v2.csv",
        ROOT / "outputs" / "ib2_route_risk_v1_3b_contract_qa" / case_id / f"{case_id}_route_risk_v2.csv",
        ROOT / "outputs" / "ib2_v2_route_risk" / case_id / f"{case_id}_route_risk_v2.csv",
        ROOT / "outputs" / "ib2_route_risk" / case_id / f"{case_id}_route_risk_v2.csv",
        ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa" / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
    ]

    fp = first_existing(candidates)
    if fp:
        return fp

    # 最後 fallback：在 outputs 裡搜尋該 case 的 route_risk CSV
    matches = list((ROOT / "outputs").rglob(f"{case_id}*route*risk*.csv"))
    if matches:
        ranked = sorted(
            matches,
            key=lambda p: (
                0 if "v1_3b" in str(p).lower() else 1,
                0 if "ib2" in str(p).lower() else 1,
                len(str(p)),
            )
        )
        return ranked[0]

    return None

def norm_band(v):
    if pd.isna(v):
        return "unknown"
    s = str(v).strip().lower().replace("-", "_").replace(" ", "_")
    if s in RISK_BANDS:
        return s
    if s == "veryhigh":
        return "very_high"
    return "unknown"

def choose_risk_band_col(df):
    for col in [
        "risk_band",
        "route_risk_band",
        "ib2_risk_band",
        "osm_terrain_combined_risk_band",
        "terrain_risk_band",
    ]:
        if col in df.columns:
            return col
    return None

def choose_risk_score_col(df):
    for col in [
        "risk_score_smooth",
        "risk_score",
        "route_risk_score",
        "ib2_risk_score",
        "osm_terrain_combined_risk_score",
        "terrain_risk_score",
    ]:
        if col in df.columns:
            return col
    return None

def ensure_delta_dist(df):
    df = df.sort_values("dist_m").reset_index(drop=True).copy()
    if "delta_dist_m" in df.columns:
        df["delta_dist_m"] = pd.to_numeric(df["delta_dist_m"], errors="coerce").fillna(0)
    else:
        df["delta_dist_m"] = pd.to_numeric(df["dist_m"], errors="coerce").diff().fillna(0)

    # 避免 diff 因資料倒序或異常造成負值
    df.loc[df["delta_dist_m"] < 0, "delta_dist_m"] = 0
    return df

rows = []

for case_id in CASES:
    risk_fp = find_risk_csv(case_id)

    if risk_fp is None:
        row = {
            "case_id": case_id,
            "status": "FAIL_missing_risk_csv",
            "risk_csv": "",
        }
        rows.append(row)
        continue

    df = pd.read_csv(risk_fp, encoding="utf-8-sig", low_memory=False)

    if "dist_m" not in df.columns:
        row = {
            "case_id": case_id,
            "status": "FAIL_missing_dist_m",
            "risk_csv": str(risk_fp),
        }
        rows.append(row)
        continue

    df["dist_m"] = pd.to_numeric(df["dist_m"], errors="coerce")
    df = df.dropna(subset=["dist_m"]).sort_values("dist_m").reset_index(drop=True)

    if df.empty:
        row = {
            "case_id": case_id,
            "status": "FAIL_empty_risk_csv",
            "risk_csv": str(risk_fp),
        }
        rows.append(row)
        continue

    df = ensure_delta_dist(df)

    band_col = choose_risk_band_col(df)
    score_col = choose_risk_score_col(df)

    if band_col:
        df["risk_band_norm"] = df[band_col].map(norm_band)
    else:
        df["risk_band_norm"] = "unknown"

    if score_col:
        score = pd.to_numeric(df[score_col], errors="coerce")
    else:
        score = pd.Series([None] * len(df))

    total_dist_m = float(df["dist_m"].max() - df["dist_m"].min())
    total_segment_m = float(df["delta_dist_m"].sum())

    row = {
        "case_id": case_id,
        "status": "PASS",
        "total_route_distance_m": total_dist_m,
        "total_route_distance_km": total_dist_m / 1000.0,
        "risk_rows_n": len(df),
        "risk_band_col": band_col or "",
        "risk_score_col": score_col or "",
        "risk_score_min": float(score.min()) if score.notna().any() else "",
        "risk_score_mean": float(score.mean()) if score.notna().any() else "",
        "risk_score_max": float(score.max()) if score.notna().any() else "",
        "risk_csv": str(risk_fp),
    }

    high_plus_len = 0.0

    for band in RISK_BANDS:
        mask = df["risk_band_norm"] == band
        count = int(mask.sum())
        length_m = float(df.loc[mask, "delta_dist_m"].sum())
        ratio = length_m / total_segment_m if total_segment_m > 0 else 0.0

        row[f"{band}_rows_n"] = count
        row[f"{band}_length_m"] = length_m
        row[f"{band}_length_ratio"] = ratio

        if band in ["high", "very_high"]:
            high_plus_len += length_m

    row["high_plus_very_high_length_m"] = high_plus_len
    row["high_plus_very_high_length_ratio"] = high_plus_len / total_segment_m if total_segment_m > 0 else 0.0

    rows.append(row)

out = pd.DataFrame(rows)

# 欄位排序
front_cols = [
    "case_id",
    "status",
    "total_route_distance_km",
    "total_route_distance_m",
    "risk_rows_n",
    "risk_score_min",
    "risk_score_mean",
    "risk_score_max",
    "high_plus_very_high_length_m",
    "high_plus_very_high_length_ratio",
]
band_cols = []
for band in RISK_BANDS:
    band_cols += [
        f"{band}_rows_n",
        f"{band}_length_m",
        f"{band}_length_ratio",
    ]
tail_cols = [
    "risk_band_col",
    "risk_score_col",
    "risk_csv",
]
cols = [c for c in front_cols + band_cols + tail_cols if c in out.columns]
out = out[cols]

out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("=== five route risk summary ===")
display_cols = [
    "case_id",
    "status",
    "total_route_distance_km",
    "risk_score_min",
    "risk_score_mean",
    "risk_score_max",
    "low_rows_n",
    "moderate_rows_n",
    "high_rows_n",
    "very_high_rows_n",
    "high_plus_very_high_length_ratio",
]
display_cols = [c for c in display_cols if c in out.columns]
print(out[display_cols].to_string(index=False))

print()
print("wrote:", OUT_CSV)
