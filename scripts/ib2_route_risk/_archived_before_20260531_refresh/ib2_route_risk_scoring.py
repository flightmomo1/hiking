# =========================================================
# ib2_route_risk_scoring.py
# 讀取 ib1c semantic profile，建立路線風險分數
# 輸出 risk_score / risk_band / high-risk segments
# =========================================================

from pathlib import Path

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt


# =========================================================
# 0. 路徑設定
# =========================================================
IN_CSV = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.csv")
IN_GEOJSON = Path("ib1c_route_profile_semantic_output/qixing_route_profile_semantic_enriched.geojson")

OUT_DIR = Path("ib2_route_risk_output")
OUT_DIR.mkdir(exist_ok=True)

OUT_CSV = OUT_DIR / "qixing_route_risk_profile.csv"
OUT_GEOJSON = OUT_DIR / "qixing_route_risk_profile.geojson"
OUT_PNG = OUT_DIR / "qixing_route_risk_score.png"


# =========================================================
# 1. 風險權重設定
# =========================================================
RISK_WEIGHTS = {
    # technical
    "safety_rope": 2.0,
    "handrail": 1.0,
    "ladder": 4.0,
    "rungs": 3.0,
    "via_ferrata": 5.0,
    "assisted_trail": 3.0,

    # hazard
    "cliff": 4.0,
    "scree": 2.5,
    "bare_rock": 2.0,
    "landslide": 5.0,

    # hydrology
    "waterway": 1.5,
    "water_area": 1.5,
    "wetland": 2.0,
}

SUPPORT_WEIGHTS = {
    # 服務設施降低風險，不是路況本身
    "shelter": -1.0,
    "bench": -0.3,
    "picnic_table": -0.2,
    "picnic_site": -0.2,
    "drinking_water": -0.5,
    "toilets": -0.3,
    "information_office": -0.5,
    "visitor_centre": -0.8,
    "trailhead": -0.5,
    "guidepost": -0.3,
    "peak": 0.0,
}

SLOPE_RISK = {
    "flat": 0.0,
    "gentle": 0.3,
    "moderate": 0.8,
    "steep": 1.5,
    "very_steep": 2.5,
    "unknown": 0.0,
}


# =========================================================
# 2. 工具函式
# =========================================================
def split_flags(value):
    if pd.isna(value):
        return []
    text = str(value).strip()
    if text in ["", "normal", "none", "nan"]:
        return []
    return [x for x in text.split("|") if x]


def score_flags(value, weight_map):
    flags = split_flags(value)
    score = 0.0
    for f in flags:
        score += weight_map.get(f, 0.0)
    return score


def risk_band(score):
    if score < 1.0:
        return "low"
    elif score < 3.0:
        return "moderate"
    elif score < 5.0:
        return "high"
    else:
        return "very_high"


def build_risk_reason(row):
    reasons = []

    for col in [
        "technical_flags",
        "hazard_flags",
        "hydrology_flags",
    ]:
        for f in split_flags(row.get(col, "")):
            reasons.append(f)

    slope = str(row.get("slope_band", "unknown"))
    if slope in ["steep", "very_steep"]:
        reasons.append(slope)

    return "|".join(reasons) if reasons else "normal"


def build_runs(df, band_col="risk_band"):
    runs = []
    if df.empty:
        return runs

    start_idx = 0
    values = df[band_col].tolist()

    for i in range(1, len(values)):
        if values[i] != values[start_idx]:
            runs.append((start_idx, i - 1, values[start_idx]))
            start_idx = i

    runs.append((start_idx, len(values) - 1, values[start_idx]))
    return runs


# =========================================================
# 3. 檢查輸入
# =========================================================
for fp in [IN_CSV, IN_GEOJSON]:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}，請先執行 ib1c")


# =========================================================
# 4. 讀資料
# =========================================================
df = pd.read_csv(IN_CSV)
gdf = gpd.read_file(IN_GEOJSON).to_crs("EPSG:4326")

print("input points:", len(df))


# =========================================================
# 5. 計算 risk score
# =========================================================
df["risk_technical"] = df["technical_flags"].apply(lambda x: score_flags(x, RISK_WEIGHTS))

def score_hazard_max(value):
    flags = split_flags(value)
    if not flags:
        return 0.0
    return max([RISK_WEIGHTS.get(f, 0.0) for f in flags])

df["risk_hazard"] = df["hazard_flags"].apply(score_hazard_max)



df["risk_hydrology"] = df["hydrology_flags"].apply(lambda x: score_flags(x, RISK_WEIGHTS))

df["risk_slope"] = df["slope_band"].apply(
    lambda x: min(1.5, SLOPE_RISK.get(str(x), 0.0))
)

df["risk_support_adjustment"] = (
    df["facility_flags"].apply(lambda x: score_flags(x, SUPPORT_WEIGHTS)) +
    df["rest_flags"].apply(lambda x: score_flags(x, SUPPORT_WEIGHTS)) +
    df["support_flags"].apply(lambda x: score_flags(x, SUPPORT_WEIGHTS)) +
    df["landmark_flags"].apply(lambda x: score_flags(x, SUPPORT_WEIGHTS))
)

df["risk_score_raw"] = (
    df["risk_technical"] +
    df["risk_hazard"] +
    df["risk_hydrology"] +
    df["risk_slope"] +
    df["risk_support_adjustment"]
)

# 不讓 support 把風險扣到負數
df["risk_score"] = df["risk_score_raw"].clip(lower=0)

df["risk_band"] = df["risk_score"].apply(risk_band)
df["risk_reason"] = df.apply(build_risk_reason, axis=1)


# =========================================================
# 6. 合併回 GeoJSON
# =========================================================
for col in [
    "risk_technical",
    "risk_hazard",
    "risk_hydrology",
    "risk_slope",
    "risk_support_adjustment",
    "risk_score_raw",
    "risk_score",
    "risk_band",
    "risk_reason",
]:
    gdf[col] = df[col].values


# =========================================================
# 7. 輸出 CSV / GeoJSON
# =========================================================
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

print("risk CSV:", OUT_CSV.resolve())
print("risk GeoJSON:", OUT_GEOJSON.resolve())


# =========================================================
# 8. 風險剖面圖
# =========================================================
BAND_COLOR = {
    "low": "#2ecc71",
    "moderate": "#f1c40f",
    "high": "#e67e22",
    "very_high": "#e74c3c",
}

plt.figure(figsize=(14, 4))

plt.plot(
    df["dist_m"],
    df["risk_score"],
    linewidth=1.8,
    label="risk_score",
)

for s, e, band in build_runs(df, "risk_band"):
    x0 = df.loc[s, "dist_m"]
    x1 = df.loc[e, "dist_m"]

    if e + 1 < len(df):
        x1 = df.loc[e + 1, "dist_m"]

    plt.axvspan(
        x0,
        x1,
        color=BAND_COLOR.get(band, "#cccccc"),
        alpha=0.18,
    )

plt.xlabel("Distance (m)")
plt.ylabel("Risk score")
plt.title("Qixing Route Risk Score Profile")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200)
plt.close()

print("risk PNG:", OUT_PNG.resolve())


# =========================================================
# 9. 摘要
# =========================================================
print("\n=== risk_band distribution ===")
print(df["risk_band"].value_counts(dropna=False))

print("\n=== top risk points ===")
cols = [
    "sample_idx",
    "dist_m",
    "ele_gpx_m",
    "slope_band",
    "technical_flags",
    "hazard_flags",
    "hydrology_flags",
    "risk_score",
    "risk_band",
    "risk_reason",
]
exist_cols = [c for c in cols if c in df.columns]

print(
    df.sort_values("risk_score", ascending=False)[exist_cols]
    .head(15)
    .to_string(index=False)
)