# -*- coding: utf-8 -*-
"""
ib3c_detect_activity_behavior_events.py

IB3C V1: Activity behavior event detection

定位：
- 不取代 IB3A / IB3A2。
- IB3A 負責 activity sequence mapmatching。
- IB3A2 負責 route-core model filter。
- IB3C 負責把低速、停留、離線、繞行、心率恢復、導航確認等解釋成活動行為事件。

Input:
- IB3A sequence mapmatched CSV
- IB3A2 labeled CSV
- IB1E OSM + NLSC terrain/risk enriched route profile CSV

Output:
- event CSV
- point-labeled CSV
- summary TXT
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# =========================================================
# A. Utility
# =========================================================

def read_csv_utf8(fp: Path) -> pd.DataFrame:
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp}")
    return pd.read_csv(fp, encoding="utf-8-sig")


def write_csv_utf8(df: pd.DataFrame, fp: Path) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(fp, index=False, encoding="utf-8-sig")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def first_existing_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def to_num(s, default=np.nan):
    return pd.to_numeric(s, errors="coerce").fillna(default)


def safe_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def mode_text(series: pd.Series, default: str = "") -> str:
    if series is None or len(series) == 0:
        return default
    s = series.dropna().astype(str)
    s = s[s.str.strip() != ""]
    if s.empty:
        return default
    return s.value_counts().idxmax()


def safe_float(v, default=np.nan):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def build_default_path(args) -> dict[str, Path]:
    route_folder = args.route_folder
    activity_id = args.activity_id
    case_id = args.case_id

    mapmatched_csv = Path(args.mapmatched_root) / route_folder / f"{activity_id}_mapmatched.csv"

    labeled_csv = (
        Path(args.ib3a2_root)
        / route_folder
        / f"{route_folder}_{activity_id}_mapmatched_activity_labeled.csv"
    )

    route_context_csv = (
        Path("outputs")
        / "ib1e_route_profile_contour_window_terrain"
        / case_id
        / f"{case_id}_route_profile_contour_window_terrain_enriched.csv"
    )

    out_dir = Path(args.out_dir) / route_folder / activity_id

    return {
        "mapmatched_csv": mapmatched_csv,
        "labeled_csv": labeled_csv,
        "route_context_csv": route_context_csv,
        "out_dir": out_dir,
    }


# =========================================================
# B. Input merge
# =========================================================

def load_activity(args) -> pd.DataFrame:
    paths = build_default_path(args)

    mapmatched_fp = Path(args.mapmatched_csv) if args.mapmatched_csv else paths["mapmatched_csv"]
    labeled_fp = Path(args.labeled_csv) if args.labeled_csv else paths["labeled_csv"]

    mm = normalize_columns(read_csv_utf8(mapmatched_fp))
    lab = normalize_columns(read_csv_utf8(labeled_fp))

    if "row_index" not in mm.columns:
        mm["row_index"] = np.arange(len(mm))

    if "row_index" not in lab.columns:
        lab["row_index"] = np.arange(len(lab))

    # IB3A2 labeled 可能含 usable_on_route / excluded_reason 等欄位。
    # 以 row_index 合併；若重複欄位，保留 IB3A 原欄位，IB3A2 欄位加 _ib3a2。
    keep_lab_cols = []
    for c in lab.columns:
        if c == "row_index":
            keep_lab_cols.append(c)
        elif c not in mm.columns:
            keep_lab_cols.append(c)
        elif c in [
            "usable_on_route",
            "excluded_reason",
            "manual_event_type",
            "manual_interpretation",
            "analysis_scope",
        ]:
            keep_lab_cols.append(c)

    lab2 = lab[keep_lab_cols].copy()

    df = mm.merge(
        lab2,
        on="row_index",
        how="left",
        suffixes=("", "_ib3a2"),
    )

    df["activity_id"] = args.activity_id
    df["route_folder"] = args.route_folder

    return df


def attach_route_context(activity: pd.DataFrame, route_context: pd.DataFrame) -> pd.DataFrame:
    df = activity.copy()
    ctx = route_context.copy()

    route_dist_col = first_existing_col(
        df,
        ["reliable_route_dist_m", "route_dist_m", "dist_m"],
    )
    if route_dist_col is None:
        raise ValueError("activity 缺少 route_dist 欄位：需要 reliable_route_dist_m 或 route_dist_m")

    ctx_dist_col = first_existing_col(ctx, ["dist_m", "route_dist_m"])
    if ctx_dist_col is None:
        raise ValueError("route context 缺少距離欄位：需要 dist_m 或 route_dist_m")

    df["_join_route_dist_m"] = pd.to_numeric(df[route_dist_col], errors="coerce")
    ctx["_ctx_dist_m"] = pd.to_numeric(ctx[ctx_dist_col], errors="coerce")

    # merge_asof 不接受 key 為 NaN。
    # IB3C 必須保留 off-route / endpoint artifact / low-confidence 點，
    # 因此只對有 route distance 的點補 route context，無距離點保留但 context 為空。
    df["_original_order"] = np.arange(len(df))

    df_valid = df[df["_join_route_dist_m"].notna()].copy()
    df_null = df[df["_join_route_dist_m"].isna()].copy()

    ctx2 = (
        ctx[ctx["_ctx_dist_m"].notna()]
        .sort_values("_ctx_dist_m")
        .reset_index(drop=True)
    )

    ctx_keep = [
        "_ctx_dist_m",
        "osm_highway",
        "osm_surface",
        "surface_class",
        "route_semantic_class",
        "facility_flags",
        "rest_flags",
        "support_flags",
        "hydrology_flags",
        "visibility_class",
        "osm_difficulty_class",
        "slope_band_window_nlsc",
        "terrain_window_risk_score",
        "hydro_terrain_amplifier_score",
        "osm_terrain_combined_risk_score",
        "osm_terrain_combined_risk_band",
    ]
    ctx_keep = [c for c in ctx_keep if c in ctx2.columns]

    if df_valid.empty:
        merged_valid = df_valid.copy()
        for c in ctx_keep:
            if c not in merged_valid.columns:
                merged_valid[c] = np.nan
        merged_valid["route_context_dist_diff_m"] = np.nan
    else:
        df2 = df_valid.sort_values("_join_route_dist_m").reset_index(drop=True)

        merged_valid = pd.merge_asof(
            df2,
            ctx2[ctx_keep],
            left_on="_join_route_dist_m",
            right_on="_ctx_dist_m",
            direction="nearest",
            tolerance=20.0,
        )

        merged_valid["route_context_dist_diff_m"] = (
            merged_valid["_join_route_dist_m"] - merged_valid["_ctx_dist_m"]
        ).abs()

    # 讓沒有 route_dist 的點也有同樣欄位，方便 concat
    for c in ctx_keep:
        if c not in df_null.columns:
            df_null[c] = np.nan
    if "route_context_dist_diff_m" not in df_null.columns:
        df_null["route_context_dist_diff_m"] = np.nan

    merged = pd.concat([merged_valid, df_null], ignore_index=True, sort=False)
    merged = merged.sort_values("_original_order").drop(columns=["_original_order"]).reset_index(drop=True)

    return merged


# =========================================================
# C. Derived fields
# =========================================================

def prepare_activity_fields(df: pd.DataFrame, args) -> pd.DataFrame:
    out = df.copy()

    if "elapsed_sec" not in out.columns:
        if "time" in out.columns:
            t = pd.to_datetime(out["time"], errors="coerce")
            out["elapsed_sec"] = (t - t.min()).dt.total_seconds()
        else:
            out["elapsed_sec"] = np.arange(len(out), dtype=float)

    out["elapsed_sec"] = pd.to_numeric(out["elapsed_sec"], errors="coerce")
    out = out.sort_values("elapsed_sec").reset_index(drop=True)

    out["dt_sec"] = out["elapsed_sec"].diff().fillna(0)
    out["dt_sec"] = out["dt_sec"].clip(lower=0, upper=args.max_gap_sec)

    # -----------------------------------------------------
    # speed
    # -----------------------------------------------------
    speed_col = None
    if args.speed_col and args.speed_col != "auto":
        if args.speed_col not in out.columns:
            raise ValueError(f"--speed-col 指定欄位不存在：{args.speed_col}")
        speed_col = args.speed_col
    else:
        speed_col = first_existing_col(
            out,
            [
                "raw_speed_mps",
                "walking_speed_mps",
                "speed_mps",
                "forward_speed_route_mps",
                "forward_speed_route_mps_smooth",
                "forward_speed_route_mps_raw",
            ],
        )

    if speed_col:
        out["ib3c_speed_mps"] = pd.to_numeric(out[speed_col], errors="coerce")
        out["ib3c_speed_source"] = speed_col
    else:
        dist_col = first_existing_col(out, ["reliable_route_dist_m", "route_dist_m"])
        if dist_col is None:
            raise ValueError("無法取得速度欄位，也無 route distance 可推估速度")
        d = pd.to_numeric(out[dist_col], errors="coerce")
        dt = out["elapsed_sec"].diff()
        out["ib3c_speed_mps"] = (d.diff().abs() / dt.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        out["ib3c_speed_source"] = f"derived_abs_delta_{dist_col}"

    # -----------------------------------------------------
    # HR
    # -----------------------------------------------------
    hr_col = first_existing_col(
        out,
        [
            "heart_rate",
            "heart_rate_bpm",
            "hr_bpm",
            "raw_hr_bpm",
            "heartrate",
            "bpm",
        ],
    )

    if hr_col:
        out["ib3c_hr_bpm"] = pd.to_numeric(out[hr_col], errors="coerce")
        out["ib3c_hr_source"] = hr_col
    else:
        out["ib3c_hr_bpm"] = np.nan
        out["ib3c_hr_source"] = ""

    # -----------------------------------------------------
    # usable / excluded
    # -----------------------------------------------------
    if "usable_on_route" in out.columns:
        out["ib3c_usable_on_route"] = safe_bool_series(out["usable_on_route"])
    else:
        out["ib3c_usable_on_route"] = True

    if "excluded_reason" in out.columns:
        out["ib3c_excluded_reason"] = out["excluded_reason"].fillna("").astype(str)
    else:
        out["ib3c_excluded_reason"] = ""

    if "offset_m" in out.columns:
        out["ib3c_offset_m"] = pd.to_numeric(out["offset_m"], errors="coerce")
    elif "offset_to_mainline_m" in out.columns:
        out["ib3c_offset_m"] = pd.to_numeric(out["offset_to_mainline_m"], errors="coerce")
    else:
        out["ib3c_offset_m"] = np.nan

    return out


# =========================================================
# D. Stationary / low-speed block detection
# =========================================================

def detect_low_speed_blocks(df: pd.DataFrame, args) -> pd.DataFrame:
    out = df.copy()

    out["ib3c_low_speed_flag"] = (
        pd.to_numeric(out["ib3c_speed_mps"], errors="coerce") <= getattr(args, 'effective_low_speed_threshold_mps', args.speed_threshold_mps)
    )

    # 若 speed 缺失但 IB3A 原本已有 stationary，也納入
    if "is_stationary" in out.columns:
        out["ib3c_low_speed_flag"] = (
            out["ib3c_low_speed_flag"] | safe_bool_series(out["is_stationary"])
        )

    # V1b: off-route / low-confidence / ambiguous / endpoint artifact
    # 也視為 activity behavior candidate block。
    # 原因：off-route 區間常沒有 reliable_route_dist_m，因此由 route distance 推估的 speed 會是 NaN；
    # 若只靠 speed threshold，會漏掉「移動中的離線繞行、找路、休息再接回主線」事件。
    reason = out.get("ib3c_excluded_reason", pd.Series([""] * len(out))).fillna("").astype(str)
    usable = out.get("ib3c_usable_on_route", pd.Series([True] * len(out)))

    if not isinstance(usable, pd.Series):
        usable = pd.Series([True] * len(out))

    off_route_reason_flag = reason.str.contains(
        "off_route|low_confidence|branch_ambiguous|endpoint_artifact",
        case=False,
        regex=True,
        na=False,
    )

    out["ib3c_off_route_behavior_flag"] = (~usable.astype(bool)) & off_route_reason_flag

    out["ib3c_behavior_candidate_flag"] = (
        out["ib3c_low_speed_flag"] | out["ib3c_off_route_behavior_flag"]
    )

    # gap 太大就切 block
    elapsed_gap = out["elapsed_sec"].diff().fillna(0)
    new_block = (
        out["ib3c_behavior_candidate_flag"].ne(out["ib3c_behavior_candidate_flag"].shift(1))
        | (elapsed_gap > args.block_gap_break_sec)
    )

    out["_tmp_block_id"] = new_block.cumsum()

    out["ib3c_stationary_block_id"] = np.nan

    block_id = 0
    for _, g in out.groupby("_tmp_block_id", sort=True):
        if not bool(g["ib3c_behavior_candidate_flag"].iloc[0]):
            continue
        block_id += 1
        out.loc[g.index, "ib3c_stationary_block_id"] = block_id

    out = out.drop(columns=["_tmp_block_id"])

    return out


# =========================================================
# E. Event classification
# =========================================================

def classify_duration(duration_s: float, args) -> str:
    """
    多尺度停留時間分層：
    Y1: 短暫停步
    Y2: 明顯停留 / 導航確認
    Y3: 實質休息
    Y4: 長休息 / 用餐
    Y5: 超長停留 / 避雨 / 等待
    Y6: 紮營 / 夜宿 / 長時間滯留候選
    """
    if duration_s >= args.y6_sec:
        return "Y6_camp_or_overnight"
    if duration_s >= args.y5_sec:
        return "Y5_extended_stop"
    if duration_s >= args.y4_sec:
        return "Y4_long_rest_or_meal"
    if duration_s >= args.y3_sec:
        return "Y3_rest"
    if duration_s >= args.y2_sec:
        return "Y2_short_rest_or_navigation"
    if duration_s >= args.y1_sec:
        return "Y1_micro_pause"
    return "below_threshold"


def classify_recovery_effect(duration_s: float, hr_delta_bpm, event_type: str, args):
    """
    估計停留對體能恢復的可能效果。
    注意：長停留不一定全是體能恢復，也可能是用餐、等待、避雨、紮營或夜宿。
    terminal_artifact 屬於終點後活動紀錄，不納入 route-core recovery score。
    """
    rest_duration_tier = classify_duration(duration_s, args)

    # -----------------------------------------------------
    # terminal artifact:
    # 終點後活動紀錄或終點周邊停留，應保留於 observed behavior，
    # 但不應計入主線體能恢復評估。
    # -----------------------------------------------------
    if event_type == "terminal_artifact":
        if pd.isna(hr_delta_bpm):
            hr_recovery_effect = "hr_unknown"
        elif hr_delta_bpm <= -10:
            hr_recovery_effect = "hr_recovered_after_finish"
        elif hr_delta_bpm <= -3:
            hr_recovery_effect = "hr_partially_recovered_after_finish"
        elif hr_delta_bpm < 5:
            hr_recovery_effect = "hr_stable_after_finish"
        else:
            hr_recovery_effect = "hr_increased_after_finish"

        return {
            "rest_duration_tier": rest_duration_tier,
            "recovery_level": "terminal_post_route_stop",
            "hr_recovery_effect": hr_recovery_effect,
            "estimated_recovery_score": np.nan,
            "recovery_interpretation": "終點後活動紀錄或終點周邊停留；保留於 observed activity behavior profile，但不納入 route-core recovery 評估。",
        }

    if rest_duration_tier == "Y6_camp_or_overnight":
        recovery_level = "camp_or_overnight_scale_stop"
        base_score = 0.95
    elif rest_duration_tier == "Y5_extended_stop":
        recovery_level = "extended_stop_recovery_or_waiting"
        base_score = 0.90
    elif rest_duration_tier == "Y4_long_rest_or_meal":
        recovery_level = "long_rest_or_meal_recovery"
        base_score = 0.85
    elif rest_duration_tier == "Y3_rest":
        recovery_level = "substantial_recovery"
        base_score = 0.70
    elif rest_duration_tier == "Y2_short_rest_or_navigation":
        recovery_level = "partial_recovery"
        base_score = 0.45
    elif rest_duration_tier == "Y1_micro_pause":
        recovery_level = "micro_recovery"
        base_score = 0.20
    else:
        recovery_level = "no_recovery_estimate"
        base_score = 0.0

    if pd.isna(hr_delta_bpm):
        hr_recovery_effect = "hr_unknown"
        hr_adj = 0.0
    elif hr_delta_bpm <= -10:
        hr_recovery_effect = "hr_recovered"
        hr_adj = 0.10
    elif hr_delta_bpm <= -3:
        hr_recovery_effect = "hr_partially_recovered"
        hr_adj = 0.05
    elif hr_delta_bpm < 5:
        hr_recovery_effect = "hr_not_recovered"
        hr_adj = 0.0
    else:
        hr_recovery_effect = "hr_increased"
        hr_adj = -0.10

    estimated_recovery_score = min(max(base_score + hr_adj, 0.0), 1.0)

    if rest_duration_tier == "Y6_camp_or_overnight":
        interpretation = "紮營、夜宿、長時間滯留或救援等待候選；需人工檢查，不應直接視為一般休息。"
    elif rest_duration_tier == "Y5_extended_stop":
        interpretation = "超長停留，可能是避雨、等待、午休、設施停留或異常滯留。"
    elif rest_duration_tier == "Y4_long_rest_or_meal":
        interpretation = "長休息或用餐尺度停留，可能有明顯體能恢復，也可能包含景點、設施或離線繞行。"
    elif "off_route" in str(event_type):
        interpretation = "離線停留或繞行候選，可能包含導航確認、休息、景點／設施偏離或再接回主線。"
    elif "recovery" in str(event_type):
        interpretation = "低速或停留伴隨心率狀態，可能代表體能恢復或高負荷後調整。"
    elif rest_duration_tier in ["Y1_micro_pause", "Y2_short_rest_or_navigation"]:
        interpretation = "短暫停留，可能是看路、調整節奏、拍照、補水或導航確認。"
    else:
        interpretation = "一般停留事件，需結合路線語意、心率與天候判讀。"

    return {
        "rest_duration_tier": rest_duration_tier,
        "recovery_level": recovery_level,
        "hr_recovery_effect": hr_recovery_effect,
        "estimated_recovery_score": estimated_recovery_score,
        "recovery_interpretation": interpretation,
    }


def merge_terminal_artifact_events(events: pd.DataFrame, args) -> pd.DataFrame:
    """
    Merge fragmented terminal_artifact events into one event per activity.

    Rationale:
    IB3A2 already treats endpoint long-tail records as one route_endpoint_artifact block.
    IB3C should preserve that behavior-level meaning and should not split the same
    terminal artifact into many Y1/Y2/Y3 low-speed fragments.
    """
    if events is None or len(events) == 0:
        return events

    if "event_type" not in events.columns:
        return events

    terminal = events[events["event_type"] == "terminal_artifact"].copy()
    non_terminal = events[events["event_type"] != "terminal_artifact"].copy()

    if len(terminal) <= 1:
        return events

    def min_num(col: str):
        if col not in terminal.columns:
            return np.nan
        s = pd.to_numeric(terminal[col], errors="coerce")
        return s.min(skipna=True)

    def max_num(col: str):
        if col not in terminal.columns:
            return np.nan
        s = pd.to_numeric(terminal[col], errors="coerce")
        return s.max(skipna=True)

    def first_nonblank(col: str, default=""):
        if col not in terminal.columns:
            return default
        for v in terminal[col].tolist():
            if pd.notna(v) and str(v).strip() != "":
                return v
        return default

    start_elapsed = min_num("start_elapsed_sec")
    end_elapsed = max_num("end_elapsed_sec")
    duration_s = end_elapsed - start_elapsed if pd.notna(start_elapsed) and pd.notna(end_elapsed) else max_num("duration_sec")

    hr_start = first_nonblank("hr_start_bpm", np.nan)
    hr_end = first_nonblank("hr_end_bpm", np.nan)
    hr_delta = np.nan
    try:
        if pd.notna(float(hr_start)) and pd.notna(float(hr_end)):
            hr_delta = float(hr_end) - float(hr_start)
    except Exception:
        hr_delta = np.nan

    recovery_info = classify_recovery_effect(
        duration_s=duration_s,
        hr_delta_bpm=hr_delta,
        event_type="terminal_artifact",
        args=args,
    )

    merged = terminal.iloc[0].copy()

    merged["event_type"] = "terminal_artifact"
    merged["event_subtype"] = "endpoint_artifact"
    merged["start_elapsed_sec"] = start_elapsed
    merged["end_elapsed_sec"] = end_elapsed
    merged["duration_sec"] = duration_s

    if "start_route_dist_m" in merged.index:
        merged["start_route_dist_m"] = first_nonblank("start_route_dist_m", np.nan)
    if "end_route_dist_m" in merged.index:
        merged["end_route_dist_m"] = first_nonblank("end_route_dist_m", np.nan)

    if "max_offset_m" in merged.index:
        merged["max_offset_m"] = max_num("max_offset_m")
    if "max_hr_bpm" in merged.index:
        merged["max_hr_bpm"] = max_num("max_hr_bpm")
    if "hr_start_bpm" in merged.index:
        merged["hr_start_bpm"] = hr_start
    if "hr_end_bpm" in merged.index:
        merged["hr_end_bpm"] = hr_end
    if "hr_delta_bpm" in merged.index:
        merged["hr_delta_bpm"] = hr_delta

    for k, v in recovery_info.items():
        if k in merged.index:
            merged[k] = v

    # Terminal artifact is not route-context based.
    for col in [
        "terrain_risk_context",
        "facility_context",
        "rest_context",
        "support_context",
        "route_semantic_context",
        "surface_context",
        "hydrology_context",
        "slope_context",
    ]:
        if col in merged.index:
            merged[col] = first_nonblank(col, "")

    if "confidence" in merged.index:
        merged["confidence"] = max_num("confidence")

    out = pd.concat([non_terminal, pd.DataFrame([merged])], ignore_index=True)

    if "start_elapsed_sec" in out.columns:
        out["_sort_elapsed"] = pd.to_numeric(out["start_elapsed_sec"], errors="coerce")
        out = out.sort_values("_sort_elapsed").drop(columns=["_sort_elapsed"]).reset_index(drop=True)

    if "event_id" in out.columns:
        out["event_id"] = range(1, len(out) + 1)

    return out


def has_meaningful_flag(value: str) -> bool:
    s = "" if pd.isna(value) else str(value).strip().lower()
    return s not in ["", "none", "normal", "nan"]


def classify_event(g: pd.DataFrame, args) -> tuple[str, str, str, float]:
    duration_s = safe_float(g["elapsed_sec"].max() - g["elapsed_sec"].min(), 0.0)
    duration_tier = classify_duration(duration_s, args)

    usable_ratio = float(g["ib3c_usable_on_route"].mean()) if len(g) else 0.0
    off_route_ratio = 1.0 - usable_ratio

    excluded_reason = mode_text(g["ib3c_excluded_reason"], default="")
    match_quality = mode_text(g["match_quality"], default="") if "match_quality" in g.columns else ""

    hr_mean = pd.to_numeric(g["ib3c_hr_bpm"], errors="coerce").mean()
    hr_max = pd.to_numeric(g["ib3c_hr_bpm"], errors="coerce").max()
    high_hr = False
    if pd.notna(hr_max):
        high_hr = hr_max >= args.high_hr_bpm

    slope = mode_text(g.get("slope_band_window_nlsc", pd.Series(dtype=str)), default="")
    risk_band = mode_text(g.get("osm_terrain_combined_risk_band", pd.Series(dtype=str)), default="")
    facility_flags = mode_text(g.get("facility_flags", pd.Series(dtype=str)), default="")
    rest_flags = mode_text(g.get("rest_flags", pd.Series(dtype=str)), default="")
    support_flags = mode_text(g.get("support_flags", pd.Series(dtype=str)), default="")
    hydrology_flags = mode_text(g.get("hydrology_flags", pd.Series(dtype=str)), default="")

    has_facility = (
        has_meaningful_flag(facility_flags)
        or has_meaningful_flag(rest_flags)
        or has_meaningful_flag(support_flags)
    )

    steep_context = str(slope).lower() in ["steep", "very_steep"]
    high_risk_context = str(risk_band).lower() in ["high", "very_high"]
    hydro_context = has_meaningful_flag(hydrology_flags)

    # -----------------------------------------------------
    # primary rules
    # -----------------------------------------------------
    if "route_endpoint_artifact" in excluded_reason:
        event_type = "terminal_artifact"
        subtype = "endpoint_artifact"
        confidence = 0.90

    elif off_route_ratio >= 0.50:
        route_span = (
            pd.to_numeric(g["reliable_route_dist_m"], errors="coerce").max()
            - pd.to_numeric(g["reliable_route_dist_m"], errors="coerce").min()
            if "reliable_route_dist_m" in g.columns
            else np.nan
        )

        if duration_s >= args.y3_sec and (pd.isna(route_span) or route_span <= args.stationary_route_span_m):
            event_type = "off_route_rest"
            subtype = "off_route_exploration_navigation_rejoin_candidate"
            confidence = 0.75
        elif duration_s >= args.y2_sec:
            event_type = "off_route_detour"
            subtype = "off_route_detour_or_rejoin_candidate"
            confidence = 0.70
        else:
            event_type = "route_uncertainty_stop"
            subtype = "short_off_route_uncertainty"
            confidence = 0.60

    elif has_facility and duration_s >= args.y2_sec:
        event_type = "facility_rest"
        subtype = "near_facility_or_rest_poi"
        confidence = 0.75

    elif high_hr and duration_s >= args.y1_sec:
        event_type = "high_hr_recovery_stop"
        subtype = "high_hr_low_speed"
        confidence = 0.80

    elif (steep_context or high_risk_context or hydro_context) and duration_s >= args.y2_sec:
        event_type = "recovery_stop"
        subtype = "terrain_or_risk_context_low_speed"
        confidence = 0.70

    elif duration_s >= args.y2_sec:
        event_type = "navigation_check"
        subtype = "on_route_rest_or_navigation_check"
        confidence = 0.60

    elif duration_s >= args.y1_sec:
        event_type = "short_pause"
        subtype = "micro_pause"
        confidence = 0.55

    else:
        event_type = "unknown_stationary"
        subtype = "below_duration_threshold"
        confidence = 0.30

    modifiers = []
    if high_hr:
        modifiers.append("high_hr")
    if has_facility:
        modifiers.append("facility_context")
    if steep_context:
        modifiers.append(f"slope={slope}")
    if high_risk_context:
        modifiers.append(f"risk={risk_band}")
    if hydro_context:
        modifiers.append(f"hydrology={hydrology_flags}")
    if off_route_ratio >= 0.50:
        modifiers.append("off_route")
    if args.weather_mode != "baseline":
        modifiers.append(f"weather_mode={args.weather_mode}")
    if args.weather_scenario_name:
        modifiers.append(f"weather_scenario={args.weather_scenario_name}")

    return event_type, subtype, "|".join(modifiers), confidence


def build_events(df: pd.DataFrame, args) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    events = []

    event_id = 0

    valid_blocks = out["ib3c_stationary_block_id"].dropna().unique()
    valid_blocks = sorted(valid_blocks)

    out["ib3c_event_id"] = np.nan
    out["ib3c_event_type"] = ""
    out["ib3c_event_subtype"] = ""

    for block_id in valid_blocks:
        g = out[out["ib3c_stationary_block_id"] == block_id].copy()
        if g.empty:
            continue

        start_elapsed = safe_float(g["elapsed_sec"].min(), 0.0)
        end_elapsed = safe_float(g["elapsed_sec"].max(), 0.0)
        duration_s = end_elapsed - start_elapsed

        if duration_s < args.y1_sec:
            continue

        event_id += 1

        event_type, event_subtype, modifiers, confidence = classify_event(g, args)

        route_dist_col = first_existing_col(g, ["reliable_route_dist_m", "route_dist_m"])

        if route_dist_col:
            route_dist = pd.to_numeric(g[route_dist_col], errors="coerce")
            start_route_dist_m = safe_float(route_dist.iloc[0])
            end_route_dist_m = safe_float(route_dist.iloc[-1])
            route_dist_span_m = safe_float(route_dist.max() - route_dist.min())
        else:
            start_route_dist_m = np.nan
            end_route_dist_m = np.nan
            route_dist_span_m = np.nan

        speed = pd.to_numeric(g["ib3c_speed_mps"], errors="coerce")
        hr = pd.to_numeric(g["ib3c_hr_bpm"], errors="coerce")
        offset = pd.to_numeric(g["ib3c_offset_m"], errors="coerce")

        hr_start = safe_float(hr.dropna().iloc[0]) if hr.dropna().shape[0] else np.nan
        hr_end = safe_float(hr.dropna().iloc[-1]) if hr.dropna().shape[0] else np.nan
        hr_delta = hr_end - hr_start if pd.notna(hr_start) and pd.notna(hr_end) else np.nan
        hr_recovery_slope = (hr_delta / duration_s * 60.0) if duration_s > 0 and pd.notna(hr_delta) else np.nan

        recovery_info = classify_recovery_effect(
            duration_s=duration_s,
            hr_delta_bpm=hr_delta,
            event_type=event_type,
            args=args,
        )

        usable_ratio = float(g["ib3c_usable_on_route"].mean()) if len(g) else np.nan
        off_route_ratio = 1.0 - usable_ratio if pd.notna(usable_ratio) else np.nan

        event_row = {
            "event_id": event_id,
            "route_folder": args.route_folder,
            "activity_id": args.activity_id,
            "event_type": event_type,
            "event_subtype": event_subtype,
            "event_modifiers": modifiers,
            "start_elapsed_sec": start_elapsed,
            "end_elapsed_sec": end_elapsed,
            "duration_sec": duration_s,
            "duration_tier": classify_duration(duration_s, args),
            "start_row_index": mode_text(g["row_index"].head(1), default=""),
            "end_row_index": mode_text(g["row_index"].tail(1), default=""),
            "start_route_dist_m": start_route_dist_m,
            "end_route_dist_m": end_route_dist_m,
            "route_dist_span_m": route_dist_span_m,
            "mean_speed_mps": speed.mean(),
            "min_speed_mps": speed.min(),
            "max_speed_mps": speed.max(),
            "median_offset_m": offset.median(),
            "max_offset_m": offset.max(),
            "on_route_ratio": usable_ratio,
            "off_route_ratio": off_route_ratio,
            "mean_hr_bpm": hr.mean(),
            "max_hr_bpm": hr.max(),
            "hr_start_bpm": hr_start,
            "hr_end_bpm": hr_end,
            "hr_delta_bpm": hr_delta,
            "hr_recovery_slope_bpm_per_min": hr_recovery_slope,
            "rest_duration_tier": recovery_info["rest_duration_tier"],
            "recovery_level": recovery_info["recovery_level"],
            "hr_recovery_effect": recovery_info["hr_recovery_effect"],
            "estimated_recovery_score": recovery_info["estimated_recovery_score"],
            "recovery_interpretation": recovery_info["recovery_interpretation"],
            "route_semantic_context": mode_text(g.get("route_semantic_class", pd.Series(dtype=str))),
            "surface_context": mode_text(g.get("surface_class", pd.Series(dtype=str))),
            "facility_context": mode_text(g.get("facility_flags", pd.Series(dtype=str))),
            "rest_context": mode_text(g.get("rest_flags", pd.Series(dtype=str))),
            "support_context": mode_text(g.get("support_flags", pd.Series(dtype=str))),
            "hydrology_context": mode_text(g.get("hydrology_flags", pd.Series(dtype=str))),
            "slope_context": mode_text(g.get("slope_band_window_nlsc", pd.Series(dtype=str))),
            "terrain_risk_context": mode_text(g.get("osm_terrain_combined_risk_band", pd.Series(dtype=str))),
            "terrain_risk_score_mean": pd.to_numeric(
                g.get("osm_terrain_combined_risk_score", pd.Series(dtype=float)),
                errors="coerce",
            ).mean(),
            "weather_mode": args.weather_mode,
            "weather_scenario_name": args.weather_scenario_name,
            "weather_context": args.weather_mode,
            "weather_event_modifier": args.weather_scenario_name if args.weather_scenario_name else "",
            "activity_risk_context": mode_text(g.get("match_quality", pd.Series(dtype=str))),
            "excluded_reason_context": mode_text(g.get("ib3c_excluded_reason", pd.Series(dtype=str))),
            "candidate_reason": event_subtype,
            "confidence": confidence,
            "points_n": len(g),
        }

        events.append(event_row)

        out.loc[g.index, "ib3c_event_id"] = event_id
        out.loc[g.index, "ib3c_event_type"] = event_type
        out.loc[g.index, "ib3c_event_subtype"] = event_subtype

    events_df = pd.DataFrame(events)

    return out, events_df



def compute_adaptive_low_speed_threshold(points: pd.DataFrame, args) -> float:
    """
    Phase 1 helper:
    - Computes an activity-specific low-speed threshold from the prepared point table.
    - Does NOT change event detection yet.
    - Used only for summary / QA in this first adaptive-speed branch.

    Formula:
        adaptive = min(global_reference, max(floor, percentile(speed)))
    """
    speed_col_candidates = [
        "ib3c_speed_mps",
        "gps_speed_mps",
        "speed_mps",
    ]

    speed_col = None
    for c in speed_col_candidates:
        if c in points.columns:
            speed_col = c
            break

    if speed_col is None:
        return float("nan")

    speeds = pd.to_numeric(points[speed_col], errors="coerce")
    speeds = speeds.replace([np.inf, -np.inf], np.nan).dropna()

    # Conservative cleanup: human hiking speed should not require extreme outliers.
    speeds = speeds[(speeds >= 0) & (speeds <= 5.0)]

    if speeds.empty:
        return float("nan")

    p = float(getattr(args, "adaptive_speed_percentile", 0.25))
    floor_mps = float(getattr(args, "adaptive_speed_floor_mps", 0.25))
    global_ref = float(getattr(args, "global_low_speed_reference_mps", 0.7))

    raw = float(speeds.quantile(p))
    adaptive = min(global_ref, max(floor_mps, raw))
    return float(adaptive)




def add_phase3_semantic_annotations(events: pd.DataFrame, args) -> pd.DataFrame:
    """
    Phase 3-A:
    Add semantic annotation columns without changing original event_type.

    This function is intentionally conservative:
    - does not overwrite event_type
    - does not overwrite event_subtype
    - does not change confidence
    - only adds candidate semantic labels for QA
    """
    out = events.copy()

    if out.empty:
        for c in [
            "semantic_low_speed_class",
            "semantic_hr_response_class",
            "semantic_motion_class",
            "semantic_event_type_candidate",
        ]:
            out[c] = []
        return out

    effective_thr = float(getattr(args, "effective_low_speed_threshold_mps", getattr(args, "speed_threshold_mps", 0.7)))

    mean_speed = pd.to_numeric(out.get("mean_speed_mps"), errors="coerce")
    max_speed = pd.to_numeric(out.get("max_speed_mps"), errors="coerce")
    duration = pd.to_numeric(out.get("duration_sec"), errors="coerce")
    route_span = pd.to_numeric(out.get("route_dist_span_m"), errors="coerce")
    max_hr = pd.to_numeric(out.get("max_hr_bpm"), errors="coerce")

    # ---------------------------------------------------------
    # Low-speed semantic class
    # ---------------------------------------------------------
    def low_speed_class(ms):
        if pd.isna(ms):
            return "unknown"
        if ms <= max(0.05, effective_thr * 0.25):
            return "near_stop"
        if ms <= effective_thr:
            return "very_slow"
        if ms <= 0.7:
            return "slow"
        return "moving"

    out["semantic_low_speed_class"] = mean_speed.apply(low_speed_class)

    # ---------------------------------------------------------
    # Motion class
    # Use route_dist_span_m when available.
    # A low route span over a long duration is stationary-like.
    # ---------------------------------------------------------
    def motion_class(span, dur, ms):
        if pd.isna(dur) or dur <= 0:
            return "unknown"

        if pd.notna(span):
            if span <= 5 and dur >= 15:
                return "stationary_like"
            if span <= 20 and dur >= 20:
                return "low_motion"
            return "moving_like"

        if pd.notna(ms):
            if ms <= max(0.05, effective_thr * 0.25):
                return "stationary_like"
            if ms <= effective_thr:
                return "low_motion"
            return "moving_like"

        return "unknown"

    out["semantic_motion_class"] = [
        motion_class(s, d, m)
        for s, d, m in zip(route_span, duration, mean_speed)
    ]

    # ---------------------------------------------------------
    # HR response class
    # Phase 3-A only has event-level max_hr in most outputs.
    # We therefore classify by HR level, not true HR delta yet.
    # Later Phase 3-B can use event start/end HR if available.
    # ---------------------------------------------------------
    high_hr_threshold = float(getattr(args, "high_hr_bpm", 150))

    def hr_response_class(hr):
        if pd.isna(hr):
            return "no_hr"
        if hr >= high_hr_threshold:
            return "high_hr_level"
        return "non_high_hr_level"

    out["semantic_hr_response_class"] = max_hr.apply(hr_response_class)

    # ---------------------------------------------------------
    # Candidate semantic event type
    # Conservative mapping:
    # - terminal/off-route/facility/navigation preserve original type
    # - high HR + stationary/low motion -> high_hr_recovery_stop_candidate
    # - non-high HR + stationary/low motion -> recovery_candidate or short_pause_candidate
    # - slow but moving-like -> slow_movement_candidate
    # ---------------------------------------------------------
    preserve_types = {
        "terminal_artifact",
        "off_route_rest",
        "off_route_detour",
        "facility_rest",
        "navigation_check",
    }

    def candidate(row):
        et = str(row.get("event_type", ""))
        dur = pd.to_numeric(row.get("duration_sec"), errors="coerce")
        motion = row.get("semantic_motion_class", "unknown")
        lowcls = row.get("semantic_low_speed_class", "unknown")
        hrcls = row.get("semantic_hr_response_class", "no_hr")

        if et in preserve_types:
            return et

        if motion in ["stationary_like", "low_motion"]:
            if hrcls == "high_hr_level":
                return "high_hr_recovery_stop_candidate"
            if pd.notna(dur) and dur >= 30:
                return "recovery_candidate"
            return "short_pause_candidate"

        if lowcls in ["very_slow", "slow"] and motion == "moving_like":
            return "slow_movement_candidate"

        return et

    out["semantic_event_type_candidate"] = out.apply(candidate, axis=1)

    return out




def add_phase3b_hr_delta_annotations(events: pd.DataFrame, points_df: pd.DataFrame, args) -> pd.DataFrame:
    """
    Phase 3-B:
    Add event-level HR delta fields without changing original event_type or
    semantic_event_type_candidate.

    Added columns:
    - hr_start_bpm
    - hr_end_bpm
    - hr_delta_bpm
    - hr_drop_bpm
    - hr_recovery_slope_bpm_per_min
    - semantic_hr_delta_class
    """
    out = events.copy()

    added_cols = [
        "hr_start_bpm",
        "hr_end_bpm",
        "hr_delta_bpm",
        "hr_drop_bpm",
        "hr_recovery_slope_bpm_per_min",
        "semantic_hr_delta_class",
    ]

    if out.empty:
        for c in added_cols:
            out[c] = []
        return out

    # Default values
    for c in added_cols:
        if c == "semantic_hr_delta_class":
            out[c] = "no_hr"
        else:
            out[c] = pd.NA

    if points_df is None or len(points_df) == 0:
        return out

    pts = points_df.copy()

    if "elapsed_sec" not in pts.columns:
        return out

    # HR column fallback
    hr_col = None
    for c in ["heart_rate_bpm", "hr_bpm", "heart_rate", "hr"]:
        if c in pts.columns:
            hr_col = c
            break

    if hr_col is None:
        return out

    pts["__elapsed_sec"] = pd.to_numeric(pts["elapsed_sec"], errors="coerce")
    pts["__hr_bpm"] = pd.to_numeric(pts[hr_col], errors="coerce")
    pts = pts.dropna(subset=["__elapsed_sec"]).sort_values("__elapsed_sec")

    def classify_hr_delta(delta):
        if pd.isna(delta):
            return "no_hr"

        # delta = hr_end - hr_start
        if delta <= -10:
            return "hr_drop_strong"
        if delta <= -5:
            return "hr_drop_moderate"
        if delta < 5:
            return "hr_stable"
        if delta < 10:
            return "hr_rise_moderate"
        return "hr_rise_strong"

    for idx, row in out.iterrows():
        start_t = pd.to_numeric(row.get("start_elapsed_sec"), errors="coerce")
        end_t = pd.to_numeric(row.get("end_elapsed_sec"), errors="coerce")
        dur_sec = pd.to_numeric(row.get("duration_sec"), errors="coerce")

        if pd.isna(start_t) or pd.isna(end_t):
            continue

        if end_t < start_t:
            start_t, end_t = end_t, start_t

        win = pts[
            (pts["__elapsed_sec"] >= start_t) &
            (pts["__elapsed_sec"] <= end_t)
        ].dropna(subset=["__hr_bpm"])

        if win.empty:
            continue

        hr_start = float(win.iloc[0]["__hr_bpm"])
        hr_end = float(win.iloc[-1]["__hr_bpm"])
        hr_delta = hr_end - hr_start
        hr_drop = max(0.0, hr_start - hr_end)

        if pd.notna(dur_sec) and dur_sec > 0:
            slope = hr_delta / (dur_sec / 60.0)
        else:
            slope = pd.NA

        out.at[idx, "hr_start_bpm"] = round(hr_start, 3)
        out.at[idx, "hr_end_bpm"] = round(hr_end, 3)
        out.at[idx, "hr_delta_bpm"] = round(hr_delta, 3)
        out.at[idx, "hr_drop_bpm"] = round(hr_drop, 3)
        out.at[idx, "hr_recovery_slope_bpm_per_min"] = round(slope, 3) if pd.notna(slope) else pd.NA
        out.at[idx, "semantic_hr_delta_class"] = classify_hr_delta(hr_delta)

    return out



# =========================================================
# F. Summary
# =========================================================

def write_summary(events: pd.DataFrame, points: pd.DataFrame, fp: Path, args) -> None:
    lines = []

    lines.append("IB3C activity behavior event detection summary")
    lines.append("")
    lines.append(f"route_folder: {args.route_folder}")
    lines.append(f"activity_id: {args.activity_id}")
    lines.append(f"case_id: {args.case_id}")
    lines.append("")
    lines.append(f"speed_threshold_mps: {args.speed_threshold_mps}")
    lines.append(f"global_low_speed_reference_mps: {getattr(args, 'global_low_speed_reference_mps', '')}")
    lines.append(f"adaptive_speed_threshold_enabled: {getattr(args, 'adaptive_speed_threshold', False)}")
    lines.append(f"adaptive_speed_percentile: {getattr(args, 'adaptive_speed_percentile', '')}")
    lines.append(f"adaptive_speed_floor_mps: {getattr(args, 'adaptive_speed_floor_mps', '')}")
    lines.append(f"adaptive_low_speed_threshold_mps: {getattr(args, 'adaptive_low_speed_threshold_mps', '')}")
    lines.append(f"effective_low_speed_threshold_mps: {getattr(args, 'effective_low_speed_threshold_mps', getattr(args, 'effective_low_speed_threshold_mps', args.speed_threshold_mps))}")
    lines.append(f"Y1_sec: {args.y1_sec}")
    lines.append(f"Y2_sec: {args.y2_sec}")
    lines.append(f"Y3_sec: {args.y3_sec}")
    lines.append(f"high_hr_bpm: {args.high_hr_bpm}")
    lines.append(f"weather_mode: {args.weather_mode}")
    lines.append(f"weather_scenario_name: {args.weather_scenario_name}")
    lines.append("")
    lines.append(f"points_total: {len(points)}")
    lines.append(f"low_speed_points: {int(points['ib3c_low_speed_flag'].sum()) if 'ib3c_low_speed_flag' in points.columns else 0}")
    lines.append(f"events_total: {len(events)}")
    lines.append("")

    if events.empty:
        lines.append("event_type counts: (none)")
    else:
        lines.append("event_type counts:")
        for k, v in events["event_type"].value_counts(dropna=False).items():
            lines.append(f"  {k}: {v}")

        lines.append("")
        lines.append("duration by event_type:")
        for k, g in events.groupby("event_type"):
            lines.append(f"  {k}: {g['duration_sec'].sum():.1f} sec")

        lines.append("")
        lines.append("events:")
        for _, r in events.iterrows():
            lines.append(
                f"- event_id={r['event_id']} "
                f"type={r['event_type']} "
                f"subtype={r['event_subtype']} "
                f"elapsed={r['start_elapsed_sec']:.1f}-{r['end_elapsed_sec']:.1f} "
                f"duration={r['duration_sec']:.1f}s "
                f"route={r['start_route_dist_m']:.1f}-{r['end_route_dist_m']:.1f}m "
                f"off_route_ratio={r['off_route_ratio']:.2f} "
                f"max_hr={r['max_hr_bpm'] if pd.notna(r['max_hr_bpm']) else 'nan'} "
                f"confidence={r['confidence']:.2f}"
            )

    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("\n".join(lines), encoding="utf-8")


# =========================================================
# G. CLI
# =========================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="IB3C V1: detect activity behavior events from IB3A/IB3A2 outputs"
    )

    p.add_argument("--route-folder", required=True)
    p.add_argument("--case-id", required=True)
    p.add_argument("--activity-id", required=True)

    p.add_argument(
        "--mapmatched-root",
        default="outputs/ib3a_sequence_mapmatched_activity_v4b_after_forced_route",
    )
    p.add_argument(
        "--ib3a2-root",
        default="outputs/ib3a2_on_route_activity_filter_v4b_after_forced_route",
    )
    p.add_argument(
        "--mapmatched-csv",
        default=None,
        help="Optional explicit IB3A sequence mapmatched CSV",
    )
    p.add_argument(
        "--labeled-csv",
        default=None,
        help="Optional explicit IB3A2 labeled CSV",
    )
    p.add_argument(
        "--route-context-csv",
        default=None,
        help="Optional explicit IB1E route context CSV",
    )

    p.add_argument(
        "--out-dir",
        default="outputs/ib3c_activity_behavior_events_v1",
    )

    p.add_argument("--speed-col", default="auto")
    p.add_argument("--speed-threshold-mps", type=float, default=0.30)
    p.add_argument(
        "--adaptive-speed-threshold",
        action="store_true",
        help="Enable adaptive low-speed threshold QA calculation. Phase 1 only records summary fields and does not change event detection.",
    )
    p.add_argument(
        "--adaptive-speed-percentile",
        type=float,
        default=0.25,
        help="Percentile used for adaptive low-speed threshold, e.g. 0.25 for P25.",
    )
    p.add_argument(
        "--adaptive-speed-floor-mps",
        type=float,
        default=0.25,
        help="Lower bound for adaptive low-speed threshold.",
    )
    p.add_argument(
        "--global-low-speed-reference-mps",
        type=float,
        default=0.7,
        help="Global low-speed reference threshold. Kept for QA and plotting reference.",
    )
    p.add_argument("--y1-sec", type=float, default=15.0)
    p.add_argument("--y2-sec", type=float, default=60.0)
    p.add_argument("--y3-sec", type=float, default=180.0)
    p.add_argument("--y4-sec", type=float, default=600.0)
    p.add_argument("--y5-sec", type=float, default=1800.0)
    p.add_argument("--y6-sec", type=float, default=7200.0)
    p.add_argument("--high-hr-bpm", type=float, default=150.0)

    p.add_argument("--max-gap-sec", type=float, default=10.0)
    p.add_argument("--block-gap-break-sec", type=float, default=10.0)
    p.add_argument("--stationary-route-span-m", type=float, default=50.0)

    p.add_argument(
        "--weather-mode",
        choices=["baseline", "scenario", "observed"],
        default="baseline",
    )
    p.add_argument("--weather-scenario-name", default="")

    return p.parse_args()


def main():
    args = parse_args()
    paths = build_default_path(args)

    route_context_fp = (
        Path(args.route_context_csv)
        if args.route_context_csv
        else paths["route_context_csv"]
    )

    out_dir = paths["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    out_points_csv = out_dir / f"{args.route_folder}_{args.activity_id}_ib3c_points_labeled.csv"
    out_events_csv = out_dir / f"{args.route_folder}_{args.activity_id}_ib3c_behavior_events.csv"
    out_summary_txt = out_dir / f"{args.route_folder}_{args.activity_id}_ib3c_behavior_events_summary.txt"

    print("route_folder:", args.route_folder)
    print("case_id:", args.case_id)
    print("activity_id:", args.activity_id)
    print("mapmatched root:", args.mapmatched_root)
    print("ib3a2 root:", args.ib3a2_root)
    print("route context CSV:", route_context_fp)
    print("out_dir:", out_dir)

    activity = load_activity(args)
    route_context = normalize_columns(read_csv_utf8(route_context_fp))

    merged = attach_route_context(activity, route_context)
    prepared = prepare_activity_fields(merged, args)

    # Phase 1 adaptive speed QA:
    # Compute but do not apply to event detection yet.
    adaptive_threshold = compute_adaptive_low_speed_threshold(prepared, args)
    args.adaptive_low_speed_threshold_mps = adaptive_threshold
    args.effective_low_speed_threshold_mps = (
        adaptive_threshold if args.adaptive_speed_threshold else getattr(args, 'effective_low_speed_threshold_mps', args.speed_threshold_mps)
    )

    points = detect_low_speed_blocks(prepared, args)

    # Phase 2 threshold QA columns.
    points["global_low_speed_reference_mps"] = getattr(args, "global_low_speed_reference_mps", np.nan)
    points["adaptive_speed_threshold_enabled"] = getattr(args, "adaptive_speed_threshold", False)
    points["adaptive_low_speed_threshold_mps"] = getattr(args, "adaptive_low_speed_threshold_mps", np.nan)
    points["effective_low_speed_threshold_mps"] = getattr(
        args,
        "effective_low_speed_threshold_mps",
        getattr(args, "speed_threshold_mps", np.nan),
    )
    points_labeled, events = build_events(points, args)

    events = merge_terminal_artifact_events(events, args)

    # Phase 3-A semantic annotations:
    # Add candidate semantic labels without overwriting original event_type.
    events = add_phase3_semantic_annotations(events, args)

    # Phase 3-B HR delta annotations:
    # Add event-level HR delta fields without changing event_type or semantic_event_type_candidate.
    _points_for_hr_delta = None
    for _name in ["points_labeled", "points", "df", "activity_df", "core_df"]:
        if _name in locals():
            _candidate = locals().get(_name)
            try:
                if _candidate is not None and hasattr(_candidate, "columns") and "elapsed_sec" in _candidate.columns:
                    _points_for_hr_delta = _candidate
                    break
            except Exception:
                pass

    events = add_phase3b_hr_delta_annotations(events, _points_for_hr_delta, args)

    write_csv_utf8(points_labeled, out_points_csv)
    write_csv_utf8(events, out_events_csv)
    write_summary(events, points_labeled, out_summary_txt, args)

    print("\n完成！")
    print("points labeled CSV:", out_points_csv.resolve())
    print("events CSV:", out_events_csv.resolve())
    print("summary TXT:", out_summary_txt.resolve())

    print("\n=== event_type ===")
    if events.empty:
        print("(none)")
    else:
        print(events["event_type"].value_counts(dropna=False))

    print("\n=== events preview ===")
    show_cols = [
        "event_id",
        "event_type",
        "event_subtype",
        "start_elapsed_sec",
        "end_elapsed_sec",
        "duration_sec",
        "start_route_dist_m",
        "end_route_dist_m",
        "max_offset_m",
        "max_hr_bpm",
        "terrain_risk_context",
        "facility_context",
        "confidence",
    ]
    show_cols = [c for c in show_cols if c in events.columns]
    if events.empty:
        print("(none)")
    else:
        print(events[show_cols].to_string(index=False))


if __name__ == "__main__":
    main()






