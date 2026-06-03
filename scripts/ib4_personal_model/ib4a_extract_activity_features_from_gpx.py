# -*- coding: utf-8 -*-
from pathlib import Path
import math
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# =========================================================
# A. Input / Output
# =========================================================
ACTIVITY_GPX = Path(
    "/Users/iddmini/Documents/115_Motion改造/FY115_登山/gpx/"
    "冷水坑上-七星山東峰-主峰-下小油坑.gpx"
)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

OUT_DIR = BASE_DIR / "ib4_activity_output"
OUT_POINTS_CSV = OUT_DIR / "qixing_activity_track_points.csv"
OUT_SUMMARY_CSV = OUT_DIR / "qixing_activity_summary.csv"
OUT_STATIONARY_CSV = OUT_DIR / "qixing_activity_stationary_segments.csv"
OUT_MICRO_REST_CSV = OUT_DIR / "qixing_activity_micro_rest_segments.csv"


# =========================================================
# B. Parameters
# =========================================================
EARTH_RADIUS_M = 6371008.8

# -----------------------------
# 長停留 stationary
# -----------------------------
MOVING_SPEED_THRESHOLD_M_S = 0.25
STATIONARY_MIN_DURATION_S = 60

# -----------------------------
# 短暫休息 micro-rest
# -----------------------------
# 用來抓「上坡喘一下」、「短暫停步」、「幾乎沒前進但未滿 60 秒」。
MICRO_REST_SPEED_THRESHOLD_M_S = 0.35
MICRO_REST_MIN_DURATION_S = 15
MICRO_REST_MAX_DURATION_S = 59
MICRO_REST_MAX_NET_DISPLACEMENT_M = 10.0

# GPS 雜訊過濾
MAX_REASONABLE_SPEED_M_S = 4.0
MAX_REASONABLE_ELE_JUMP_M = 30.0

# 能力視窗
WINDOW_SECONDS = 300


# =========================================================
# C. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def haversine_m(lat1, lon1, lat2, lon2):
    if any(pd.isna(v) for v in [lat1, lon1, lat2, lon2]):
        return np.nan

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def strip_namespace(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_gpx_points(gpx_path: Path):
    ensure_exists(gpx_path)

    tree = ET.parse(gpx_path)
    root = tree.getroot()

    points = []

    for elem in root.iter():
        if strip_namespace(elem.tag) != "trkpt":
            continue

        lat = elem.attrib.get("lat")
        lon = elem.attrib.get("lon")

        ele = None
        time = None

        for child in elem:
            child_tag = strip_namespace(child.tag)
            if child_tag == "ele":
                ele = child.text
            elif child_tag == "time":
                time = child.text

        points.append(
            {
                "time_raw": time,
                "lat": float(lat) if lat is not None else np.nan,
                "lon": float(lon) if lon is not None else np.nan,
                "ele_m": float(ele) if ele is not None else np.nan,
            }
        )

    df = pd.DataFrame(points)

    if df.empty:
        raise ValueError(f"GPX 沒有讀到任何 trkpt：{gpx_path}")

    df["time"] = pd.to_datetime(df["time_raw"], errors="coerce", utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    df["point_idx"] = np.arange(len(df))

    return df


def compute_track_deltas(df: pd.DataFrame):
    out = df.copy()

    out["lat_prev"] = out["lat"].shift(1)
    out["lon_prev"] = out["lon"].shift(1)
    out["ele_prev_m"] = out["ele_m"].shift(1)
    out["time_prev"] = out["time"].shift(1)

    out["delta_dist_m"] = [
        0.0 if i == 0 else haversine_m(
            out.loc[i, "lat_prev"],
            out.loc[i, "lon_prev"],
            out.loc[i, "lat"],
            out.loc[i, "lon"],
        )
        for i in range(len(out))
    ]

    out["delta_time_s"] = (
        out["time"] - out["time_prev"]
    ).dt.total_seconds()
    out.loc[out.index[0], "delta_time_s"] = 0.0
    out.loc[out["delta_time_s"] < 0, "delta_time_s"] = np.nan

    out["delta_ele_m"] = out["ele_m"] - out["ele_prev_m"]
    out.loc[out.index[0], "delta_ele_m"] = 0.0

    out["speed_m_s"] = np.where(
        out["delta_time_s"] > 0,
        out["delta_dist_m"] / out["delta_time_s"],
        np.nan,
    )
    out["speed_km_h"] = out["speed_m_s"] * 3.6

    out["speed_outlier_flag"] = out["speed_m_s"] > MAX_REASONABLE_SPEED_M_S
    out["ele_jump_flag"] = out["delta_ele_m"].abs() > MAX_REASONABLE_ELE_JUMP_M

    out["delta_dist_m_clean"] = out["delta_dist_m"]
    out.loc[out["speed_outlier_flag"], "delta_dist_m_clean"] = np.nan

    out["delta_ele_m_clean"] = out["delta_ele_m"]
    out.loc[out["ele_jump_flag"], "delta_ele_m_clean"] = np.nan

    out["slope_pct"] = np.where(
        out["delta_dist_m_clean"] > 0,
        out["delta_ele_m_clean"] / out["delta_dist_m_clean"] * 100.0,
        np.nan,
    )

    out["cum_dist_m"] = out["delta_dist_m_clean"].fillna(0).cumsum()

    out["gain_m"] = out["delta_ele_m_clean"].clip(lower=0).fillna(0)
    out["loss_m"] = (-out["delta_ele_m_clean"].clip(upper=0)).fillna(0)

    out["cum_gain_m"] = out["gain_m"].cumsum()
    out["cum_loss_m"] = out["loss_m"].cumsum()

    out["moving_flag"] = (
        (out["speed_m_s"] >= MOVING_SPEED_THRESHOLD_M_S)
        & (~out["speed_outlier_flag"])
        & (out["delta_time_s"] > 0)
    )

    out["stationary_candidate_flag"] = (
        (out["speed_m_s"] < MOVING_SPEED_THRESHOLD_M_S)
        & (out["delta_time_s"] > 0)
        & (~out["speed_outlier_flag"])
    )

    out["micro_rest_candidate_flag"] = (
        (out["speed_m_s"] < MICRO_REST_SPEED_THRESHOLD_M_S)
        & (out["delta_time_s"] > 0)
        & (~out["speed_outlier_flag"])
    )

    return out


def build_segment_row(df, start_idx, end_idx, duration_s, segment_type):
    g = df.loc[start_idx:end_idx].copy()

    start_lat = g["lat"].iloc[0]
    start_lon = g["lon"].iloc[0]
    end_lat = g["lat"].iloc[-1]
    end_lon = g["lon"].iloc[-1]

    net_displacement_m = haversine_m(start_lat, start_lon, end_lat, end_lon)

    path_distance_m = (
        g["delta_dist_m_clean"].sum()
        if "delta_dist_m_clean" in g.columns
        else g["delta_dist_m"].sum()
    )

    return {
        "segment_type": segment_type,
        "start_point_idx": int(start_idx),
        "end_point_idx": int(end_idx),
        "start_time": g["time"].iloc[0],
        "end_time": g["time"].iloc[-1],
        "duration_s": float(duration_s),
        "duration_min": float(duration_s) / 60.0,
        "start_dist_m": g["cum_dist_m"].iloc[0],
        "end_dist_m": g["cum_dist_m"].iloc[-1],
        "path_distance_m": path_distance_m,
        "net_displacement_m": net_displacement_m,
        "mean_lat": g["lat"].mean(),
        "mean_lon": g["lon"].mean(),
        "mean_ele_m": g["ele_m"].mean(),
        "start_ele_m": g["ele_m"].iloc[0],
        "end_ele_m": g["ele_m"].iloc[-1],
        "ele_change_m": g["ele_m"].iloc[-1] - g["ele_m"].iloc[0],
        "point_count": len(g),
        "mean_speed_m_s": g["speed_m_s"].mean(),
        "max_speed_m_s": g["speed_m_s"].max(),
    }


def detect_segments_by_candidate(
    df: pd.DataFrame,
    candidate_col: str,
    min_duration_s: float,
    max_duration_s: float | None,
    segment_type: str,
    max_net_displacement_m: float | None = None,
):
    """
    通用連續低速段偵測器。
    - stationary：min_duration_s=60, max_duration_s=None
    - micro_rest：min_duration_s=15, max_duration_s=59, max_net_displacement_m=10
    """
    rows = []
    in_seg = False
    start_idx = None
    acc_time = 0.0

    for i, row in df.iterrows():
        is_candidate = bool(row.get(candidate_col, False))
        dt = row.get("delta_time_s", 0.0)

        if pd.isna(dt):
            dt = 0.0

        if is_candidate and not in_seg:
            in_seg = True
            start_idx = i
            acc_time = dt

        elif is_candidate and in_seg:
            acc_time += dt

        elif (not is_candidate) and in_seg:
            end_idx = i - 1

            maybe_row = evaluate_segment(
                df=df,
                start_idx=start_idx,
                end_idx=end_idx,
                duration_s=acc_time,
                min_duration_s=min_duration_s,
                max_duration_s=max_duration_s,
                segment_type=segment_type,
                max_net_displacement_m=max_net_displacement_m,
            )

            if maybe_row is not None:
                rows.append(maybe_row)

            in_seg = False
            start_idx = None
            acc_time = 0.0

    if in_seg and start_idx is not None:
        end_idx = len(df) - 1

        maybe_row = evaluate_segment(
            df=df,
            start_idx=start_idx,
            end_idx=end_idx,
            duration_s=acc_time,
            min_duration_s=min_duration_s,
            max_duration_s=max_duration_s,
            segment_type=segment_type,
            max_net_displacement_m=max_net_displacement_m,
        )

        if maybe_row is not None:
            rows.append(maybe_row)

    return pd.DataFrame(rows)


def evaluate_segment(
    df,
    start_idx,
    end_idx,
    duration_s,
    min_duration_s,
    max_duration_s,
    segment_type,
    max_net_displacement_m=None,
):
    if duration_s < min_duration_s:
        return None

    if max_duration_s is not None and duration_s > max_duration_s:
        return None

    row = build_segment_row(df, start_idx, end_idx, duration_s, segment_type)

    if max_net_displacement_m is not None:
        if pd.isna(row["net_displacement_m"]):
            return None
        if row["net_displacement_m"] > max_net_displacement_m:
            return None

    return row


def detect_stationary_and_micro_rest_segments(df: pd.DataFrame):
    out = df.copy()

    # 長停留
    stationary_df = detect_segments_by_candidate(
        df=out,
        candidate_col="stationary_candidate_flag",
        min_duration_s=STATIONARY_MIN_DURATION_S,
        max_duration_s=None,
        segment_type="stationary",
        max_net_displacement_m=None,
    )

    out["stationary_flag"] = False

    if not stationary_df.empty:
        for _, seg in stationary_df.iterrows():
            out.loc[
                int(seg["start_point_idx"]): int(seg["end_point_idx"]),
                "stationary_flag",
            ] = True

    # 短暫休息：排除已經被 stationary 包含的點
    micro_source = out.copy()
    micro_source.loc[micro_source["stationary_flag"], "micro_rest_candidate_flag"] = False

    micro_rest_df = detect_segments_by_candidate(
        df=micro_source,
        candidate_col="micro_rest_candidate_flag",
        min_duration_s=MICRO_REST_MIN_DURATION_S,
        max_duration_s=MICRO_REST_MAX_DURATION_S,
        segment_type="micro_rest",
        max_net_displacement_m=MICRO_REST_MAX_NET_DISPLACEMENT_M,
    )

    out["micro_rest_flag"] = False

    if not micro_rest_df.empty:
        for _, seg in micro_rest_df.iterrows():
            out.loc[
                int(seg["start_point_idx"]): int(seg["end_point_idx"]),
                "micro_rest_flag",
            ] = True

    return out, stationary_df, micro_rest_df


def compute_window_features(df: pd.DataFrame, window_s=300):
    if df["time"].isna().all():
        return {
            "max_300s_gain_m": np.nan,
            "max_300s_loss_m": np.nan,
            "max_300s_horizontal_distance_m": np.nan,
            "max_300s_vertical_speed_m_h": np.nan,
            "max_300s_horizontal_speed_km_h": np.nan,
            "max_300s_gain_start_time": None,
            "max_300s_gain_end_time": None,
            "max_300s_dist_start_time": None,
            "max_300s_dist_end_time": None,
        }

    cum_gain = df["cum_gain_m"].to_numpy()
    cum_loss = df["cum_loss_m"].to_numpy()
    cum_dist = df["cum_dist_m"].to_numpy()

    n = len(df)

    best_gain = -np.inf
    best_loss = -np.inf
    best_dist = -np.inf

    best_gain_pair = (None, None)
    best_dist_pair = (None, None)

    j = 0

    for i in range(n):
        while j < n and (df.loc[j, "time"] - df.loc[i, "time"]).total_seconds() <= window_s:
            j += 1

        end = j - 1

        if end <= i:
            continue

        actual_window_s = (df.loc[end, "time"] - df.loc[i, "time"]).total_seconds()
        if actual_window_s <= 0:
            continue

        gain = cum_gain[end] - cum_gain[i]
        loss = cum_loss[end] - cum_loss[i]
        dist = cum_dist[end] - cum_dist[i]

        if gain > best_gain:
            best_gain = gain
            best_gain_pair = (i, end)

        if loss > best_loss:
            best_loss = loss

        if dist > best_dist:
            best_dist = dist
            best_dist_pair = (i, end)

    if best_gain == -np.inf:
        best_gain = np.nan
    if best_loss == -np.inf:
        best_loss = np.nan
    if best_dist == -np.inf:
        best_dist = np.nan

    max_300s_vertical_speed_m_h = (
        best_gain / window_s * 3600.0 if pd.notna(best_gain) else np.nan
    )
    max_300s_horizontal_speed_km_h = (
        best_dist / window_s * 3.6 if pd.notna(best_dist) else np.nan
    )

    gain_start_time = None
    gain_end_time = None
    dist_start_time = None
    dist_end_time = None

    if best_gain_pair[0] is not None:
        gain_start_time = df.loc[best_gain_pair[0], "time"]
        gain_end_time = df.loc[best_gain_pair[1], "time"]

    if best_dist_pair[0] is not None:
        dist_start_time = df.loc[best_dist_pair[0], "time"]
        dist_end_time = df.loc[best_dist_pair[1], "time"]

    return {
        "max_300s_gain_m": best_gain,
        "max_300s_loss_m": best_loss,
        "max_300s_horizontal_distance_m": best_dist,
        "max_300s_vertical_speed_m_h": max_300s_vertical_speed_m_h,
        "max_300s_horizontal_speed_km_h": max_300s_horizontal_speed_km_h,
        "max_300s_gain_start_time": gain_start_time,
        "max_300s_gain_end_time": gain_end_time,
        "max_300s_dist_start_time": dist_start_time,
        "max_300s_dist_end_time": dist_end_time,
    }


def compute_activity_summary(
    df: pd.DataFrame,
    stationary_df: pd.DataFrame,
    micro_rest_df: pd.DataFrame,
):
    total_distance_m = df["cum_dist_m"].iloc[-1]
    total_gain_m = df["cum_gain_m"].iloc[-1]
    total_loss_m = df["cum_loss_m"].iloc[-1]

    if df["time"].notna().any():
        start_time = df["time"].min()
        end_time = df["time"].max()
        total_duration_s = (end_time - start_time).total_seconds()
    else:
        start_time = None
        end_time = None
        total_duration_s = np.nan

    moving_duration_s = df.loc[df["moving_flag"], "delta_time_s"].sum()

    stationary_duration_s = (
        stationary_df["duration_s"].sum()
        if not stationary_df.empty
        else 0.0
    )

    micro_rest_duration_s = (
        micro_rest_df["duration_s"].sum()
        if not micro_rest_df.empty
        else 0.0
    )

    avg_speed_km_h = (
        total_distance_m / total_duration_s * 3.6
        if pd.notna(total_duration_s) and total_duration_s > 0
        else np.nan
    )

    moving_avg_speed_km_h = (
        df.loc[df["moving_flag"], "delta_dist_m_clean"].sum()
        / moving_duration_s
        * 3.6
        if moving_duration_s and moving_duration_s > 0
        else np.nan
    )

    moving_df = df[df["moving_flag"]].copy()

    uphill_dist_m = moving_df.loc[moving_df["slope_pct"] > 3, "delta_dist_m_clean"].sum()
    downhill_dist_m = moving_df.loc[moving_df["slope_pct"] < -3, "delta_dist_m_clean"].sum()
    flat_dist_m = moving_df.loc[
        moving_df["slope_pct"].between(-3, 3, inclusive="both"),
        "delta_dist_m_clean",
    ].sum()

    moving_dist_m = moving_df["delta_dist_m_clean"].sum()

    if moving_dist_m > 0:
        uphill_ratio = uphill_dist_m / moving_dist_m
        downhill_ratio = downhill_dist_m / moving_dist_m
        flat_ratio = flat_dist_m / moving_dist_m
    else:
        uphill_ratio = np.nan
        downhill_ratio = np.nan
        flat_ratio = np.nan

    micro_rest_total_net_displacement_m = (
        micro_rest_df["net_displacement_m"].sum()
        if not micro_rest_df.empty
        else 0.0
    )

    micro_rest_total_path_distance_m = (
        micro_rest_df["path_distance_m"].sum()
        if not micro_rest_df.empty
        else 0.0
    )

    window_features = compute_window_features(df, WINDOW_SECONDS)

    summary = {
        "activity_gpx": str(ACTIVITY_GPX),
        "start_time": start_time,
        "end_time": end_time,
        "point_count": len(df),

        "total_distance_m": total_distance_m,
        "total_distance_km": total_distance_m / 1000.0,

        "total_duration_s": total_duration_s,
        "total_duration_min": total_duration_s / 60.0 if pd.notna(total_duration_s) else np.nan,

        "moving_duration_s": moving_duration_s,
        "moving_duration_min": moving_duration_s / 60.0,

        "stationary_duration_s": stationary_duration_s,
        "stationary_duration_min": stationary_duration_s / 60.0,
        "stationary_count": len(stationary_df),

        "micro_rest_duration_s": micro_rest_duration_s,
        "micro_rest_duration_min": micro_rest_duration_s / 60.0,
        "micro_rest_count": len(micro_rest_df),
        "micro_rest_total_net_displacement_m": micro_rest_total_net_displacement_m,
        "micro_rest_total_path_distance_m": micro_rest_total_path_distance_m,

        "total_gain_m": total_gain_m,
        "total_loss_m": total_loss_m,

        "avg_speed_km_h": avg_speed_km_h,
        "moving_avg_speed_km_h": moving_avg_speed_km_h,

        "uphill_dist_m": uphill_dist_m,
        "downhill_dist_m": downhill_dist_m,
        "flat_dist_m": flat_dist_m,

        "uphill_ratio": uphill_ratio,
        "downhill_ratio": downhill_ratio,
        "flat_ratio": flat_ratio,

        "speed_outlier_count": int(df["speed_outlier_flag"].sum()),
        "ele_jump_count": int(df["ele_jump_flag"].sum()),

        "moving_speed_threshold_m_s": MOVING_SPEED_THRESHOLD_M_S,
        "stationary_min_duration_s": STATIONARY_MIN_DURATION_S,

        "micro_rest_speed_threshold_m_s": MICRO_REST_SPEED_THRESHOLD_M_S,
        "micro_rest_min_duration_s": MICRO_REST_MIN_DURATION_S,
        "micro_rest_max_duration_s": MICRO_REST_MAX_DURATION_S,
        "micro_rest_max_net_displacement_m": MICRO_REST_MAX_NET_DISPLACEMENT_M,

        "window_seconds": WINDOW_SECONDS,
    }

    summary.update(window_features)

    return pd.DataFrame([summary])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("讀取 GPX:", ACTIVITY_GPX.resolve())

    raw_df = parse_gpx_points(ACTIVITY_GPX)
    track_df = compute_track_deltas(raw_df)

    track_df, stationary_df, micro_rest_df = detect_stationary_and_micro_rest_segments(track_df)

    summary_df = compute_activity_summary(
        track_df,
        stationary_df,
        micro_rest_df,
    )

    track_df.to_csv(OUT_POINTS_CSV, index=False, encoding="utf-8-sig")
    stationary_df.to_csv(OUT_STATIONARY_CSV, index=False, encoding="utf-8-sig")
    micro_rest_df.to_csv(OUT_MICRO_REST_CSV, index=False, encoding="utf-8-sig")
    summary_df.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print("\n完成！")
    print("track points CSV:", OUT_POINTS_CSV.resolve())
    print("summary CSV:", OUT_SUMMARY_CSV.resolve())
    print("stationary segments CSV:", OUT_STATIONARY_CSV.resolve())
    print("micro-rest segments CSV:", OUT_MICRO_REST_CSV.resolve())

    print("\n=== activity summary ===")
    print(summary_df.T.to_string(header=False))

    print("\n=== stationary segments ===")
    if stationary_df.empty:
        print("(empty)")
    else:
        cols = [
            "start_point_idx",
            "end_point_idx",
            "duration_s",
            "duration_min",
            "start_dist_m",
            "end_dist_m",
            "net_displacement_m",
            "path_distance_m",
            "mean_ele_m",
        ]
        print(stationary_df[cols].to_string(index=False))

    print("\n=== micro-rest segments ===")
    if micro_rest_df.empty:
        print("(empty)")
    else:
        cols = [
            "start_point_idx",
            "end_point_idx",
            "duration_s",
            "duration_min",
            "start_dist_m",
            "end_dist_m",
            "net_displacement_m",
            "path_distance_m",
            "mean_ele_m",
        ]
        print(micro_rest_df[cols].to_string(index=False))


if __name__ == "__main__":
    main()