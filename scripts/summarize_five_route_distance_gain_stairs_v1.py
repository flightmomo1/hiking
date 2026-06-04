from pathlib import Path
import pandas as pd
import math

ROOT = Path(r"C:\mountain_work\115_osm")

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
    "qixing_lengshuikeng_xiaoyoukeng_gpx_osmrefresh_v1_3b",
]

IB1E_ROOT = ROOT / "outputs" / "ib1e_route_profile_contour_window_terrain_v1_3b_contract_qa"
IB1C_ROOT = ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
IB1A_ROOT = ROOT / "outputs" / "ib1_route_profile_v1_3b_contract_qa"

OUT_DIR = ROOT / "outputs" / "thci_route_metric_summary_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "five_route_distance_gain_stairs_summary.csv"

def first_existing(candidates):
    for fp in candidates:
        if fp.exists():
            return fp
    return None

def read_csv(fp):
    return pd.read_csv(fp, encoding="utf-8-sig", low_memory=False)

def find_profile_csv(case_id):
    return first_existing([
        IB1E_ROOT / case_id / f"{case_id}_route_profile_contour_window_terrain_enriched.csv",
        IB1A_ROOT / case_id / f"{case_id}_route_profile.csv",
    ])

def find_semantic_csv(case_id):
    case_dir = IB1C_ROOT / case_id
    if not case_dir.exists():
        return None
    candidates = list(case_dir.glob("*.csv"))
    if not candidates:
        return None

    # 優先找 route_profile_semantics 類型
    ranked = sorted(
        candidates,
        key=lambda p: (
            0 if "semantics" in p.name.lower() else 1,
            0 if "route_profile" in p.name.lower() else 1,
            p.name.lower()
        )
    )
    return ranked[0]

def choose_elevation_col(df):
    for col in ["ele_smooth", "ele_gpx_m", "elevation_m", "elev_m", "elevation", "ele"]:
        if col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce")
            if v.notna().any():
                return col
    return None

def ensure_delta_cols(df):
    df = df.sort_values("dist_m").reset_index(drop=True).copy()

    if "delta_dist_m" not in df.columns:
        df["delta_dist_m"] = pd.to_numeric(df["dist_m"], errors="coerce").diff().fillna(0)
    else:
        df["delta_dist_m"] = pd.to_numeric(df["delta_dist_m"], errors="coerce").fillna(0)

    if "delta_ele_m" not in df.columns:
        elev_col = choose_elevation_col(df)
        if elev_col:
            df["delta_ele_m"] = pd.to_numeric(df[elev_col], errors="coerce").diff().fillna(0)
        else:
            df["delta_ele_m"] = 0.0
    else:
        df["delta_ele_m"] = pd.to_numeric(df["delta_ele_m"], errors="coerce").fillna(0)

    return df

def merge_semantics(profile_df, semantic_df):
    if semantic_df is None or semantic_df.empty:
        return profile_df

    if "dist_m" not in semantic_df.columns or "dist_m" not in profile_df.columns:
        return profile_df

    p = profile_df.sort_values("dist_m").copy()
    s = semantic_df.sort_values("dist_m").copy()

    p["dist_m"] = pd.to_numeric(p["dist_m"], errors="coerce")
    s["dist_m"] = pd.to_numeric(s["dist_m"], errors="coerce")
    p = p.dropna(subset=["dist_m"])
    s = s.dropna(subset=["dist_m"])

    # 避免欄位撞名，semantic 欄位加 sem_ 前綴，dist_m 保留
    keep_cols = ["dist_m"]
    for c in s.columns:
        if c == "dist_m":
            continue
        if c not in p.columns:
            keep_cols.append(c)
        else:
            s = s.rename(columns={c: f"sem_{c}"})
            keep_cols.append(f"sem_{c}")

    s = s[keep_cols]

    return pd.merge_asof(
        p,
        s,
        on="dist_m",
        direction="nearest",
        tolerance=3.0
    )

def is_steps_mask(df):
    # 優先檢查較可能的語意欄位；若不存在，就掃描所有 object 欄位中是否有 steps/stairs
    candidate_cols = [
        "highway", "sem_highway",
        "osm_highway", "sem_osm_highway",
        "source_key", "sem_source_key",
        "source_value", "sem_source_value",
        "normalized_class", "sem_normalized_class",
        "semantic_class", "sem_semantic_class",
        "route_semantic_class", "sem_route_semantic_class",
    ]

    masks = []
    for col in candidate_cols:
        if col in df.columns:
            s = df[col].astype(str).str.lower()
            masks.append(s.str.contains(r"\bsteps\b|stairs|stair", regex=True, na=False))

    # 保守 fallback：若 candidate 欄位完全抓不到，才掃描所有文字欄位
    if not masks:
        for col in df.select_dtypes(include=["object"]).columns:
            s = df[col].astype(str).str.lower()
            if s.str.contains("steps|stairs|stair", regex=True, na=False).any():
                masks.append(s.str.contains("steps|stairs|stair", regex=True, na=False))

    if not masks:
        return pd.Series(False, index=df.index)

    out = masks[0].copy()
    for m in masks[1:]:
        out = out | m
    return out.fillna(False)

rows = []

for case_id in CASES:
    profile_fp = find_profile_csv(case_id)
    semantic_fp = find_semantic_csv(case_id)

    if profile_fp is None:
        rows.append({
            "case_id": case_id,
            "status": "FAIL_missing_profile_csv",
        })
        continue

    profile = read_csv(profile_fp)
    if "dist_m" not in profile.columns:
        rows.append({
            "case_id": case_id,
            "status": "FAIL_missing_dist_m",
            "profile_csv": str(profile_fp),
        })
        continue

    semantic = read_csv(semantic_fp) if semantic_fp else None
    df = merge_semantics(profile, semantic)
    df = ensure_delta_cols(df)

    dist = pd.to_numeric(df["dist_m"], errors="coerce")
    total_dist_m = float(dist.max() - dist.min())

    if "cum_gain_m" in df.columns:
        cum_gain_m = float(pd.to_numeric(df["cum_gain_m"], errors="coerce").max())
    else:
        cum_gain_m = float(df.loc[df["delta_ele_m"] > 0, "delta_ele_m"].sum())

    if "cum_loss_m" in df.columns:
        cum_loss_m = float(pd.to_numeric(df["cum_loss_m"], errors="coerce").max())
    else:
        cum_loss_m = float(abs(df.loc[df["delta_ele_m"] < 0, "delta_ele_m"].sum()))

    steps = is_steps_mask(df)
    ascent_steps_m = float(df.loc[steps & (df["delta_ele_m"] > 0), "delta_dist_m"].sum())
    descent_steps_m = float(df.loc[steps & (df["delta_ele_m"] < 0), "delta_dist_m"].sum())
    total_steps_m = float(df.loc[steps, "delta_dist_m"].sum())

    rows.append({
        "case_id": case_id,
        "status": "PASS",
        "total_route_distance_m": total_dist_m,
        "total_route_distance_km": total_dist_m / 1000.0,
        "cum_gain_m": cum_gain_m,
        "cum_loss_m": cum_loss_m,
        "ascent_steps_length_m": ascent_steps_m,
        "descent_steps_length_m": descent_steps_m,
        "total_steps_length_m": total_steps_m,
        "steps_rows_n": int(steps.sum()),
        "profile_csv": str(profile_fp),
        "semantic_csv": str(semantic_fp) if semantic_fp else "",
    })

out = pd.DataFrame(rows)
out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

print("=== five route distance / gain / stairs summary ===")
print(
    out[[
        "case_id",
        "status",
        "total_route_distance_km",
        "cum_gain_m",
        "cum_loss_m",
        "ascent_steps_length_m",
        "descent_steps_length_m",
        "total_steps_length_m",
        "steps_rows_n",
    ]].to_string(index=False)
)

print()
print("wrote:", OUT_CSV)
