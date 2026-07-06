from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(r"D:\mountain_work\115_osm")

DEFAULT_CASE_ID = "taichung_guguan_butterfly_valley_waterfall_20260630"

IB2D_ROOT = PROJECT_ROOT / "outputs" / "ib2d_upslope_contributing_hazard_map"
THCI_WEATHER_DIAG_ROOT = PROJECT_ROOT / "outputs" / "thci_weather_sensitivity_diagnostics_v1_0b"

OUT_ROOT = PROJECT_ROOT / "outputs" / "ib2d_weather_terrain_fusion_scenarios_v1"


# Official CWA rain classes are used as red-line thresholds.
# Route-sensitive thresholds below official warning levels are review triggers, not official alerts.
RAIN_THRESHOLDS = {
    "route_wet_review": {
        "p24h_mm": 20.0,
        "p72h_mm": 50.0,
    },
    "route_rainfall_sensitive": {
        "p24h_mm": 50.0,
        "p72h_mm": 100.0,
    },
    "route_high_sensitivity": {
        "p1h_mm": 20.0,
        "p3h_mm": 50.0,
        "p24h_mm": 80.0,
        "p72h_mm": 150.0,
    },
    "cwa_heavy_rain": {
        "p1h_mm": 40.0,
        "p24h_mm": 80.0,
    },
    "cwa_extremely_heavy_rain": {
        "p3h_mm": 100.0,
        "p24h_mm": 200.0,
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _first_existing_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def _to_float(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None or pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _parse_boolish(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"true", "1", "yes", "y", "pass"}


def _parse_summary(summary_fp: Path) -> dict[str, Any]:
    if not summary_fp.exists():
        return {}

    df = _read_csv(summary_fp)
    if df.empty:
        return {}

    cols = list(df.columns)
    lower_cols = [c.lower() for c in cols]

    # Long format: metric,value or key,value
    key_col = None
    value_col = None
    for cand in ["metric", "key", "name", "field"]:
        if cand in lower_cols:
            key_col = cols[lower_cols.index(cand)]
            break
    for cand in ["value", "val"]:
        if cand in lower_cols:
            value_col = cols[lower_cols.index(cand)]
            break

    if key_col and value_col:
        return {str(r[key_col]): r[value_col] for _, r in df.iterrows()}

    # Two-column generic long format
    if len(cols) == 2:
        return {str(r[cols[0]]): r[cols[1]] for _, r in df.iterrows()}

    # Wide single-row format
    row = df.iloc[0].to_dict()
    return row


def _parse_list_like_scores(v: Any) -> list[float]:
    if v is None or pd.isna(v):
        return []
    s = str(v).strip()
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return [float(x) for x in data]
    except Exception:
        pass

    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    return [float(x) for x in nums]


def _read_weather(weather_csv: Path, as_of: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = _read_csv(weather_csv)

    time_col = _first_existing_col(
        df,
        [
            "datetime",
            "time",
            "obs_time",
            "obstime",
            "data_time",
            "timestamp",
            "time_local",
            "DateTime",
        ],
    )
    if time_col is None:
        raise ValueError(f"Cannot find datetime column in {weather_csv}. Columns={list(df.columns)}")

    df["_time"] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=["_time"]).sort_values("_time").reset_index(drop=True)

    if df.empty:
        raise ValueError(f"No valid datetime rows in {weather_csv}")

    if as_of:
        as_of_ts = pd.to_datetime(as_of)
    else:
        as_of_ts = df["_time"].max()

    df = df[df["_time"] <= as_of_ts].copy()
    if df.empty:
        raise ValueError(f"No weather rows <= as_of={as_of_ts}")

    precip_1h_col = _first_existing_col(
        df,
        [
            "precipitation_1hr_mm",
            "rain_1hr_mm",
            "rainfall_1hr_mm",
            "precip_1h_mm",
        ],
    )
    precip_cum_col = _first_existing_col(
        df,
        [
            "precipitation_mm",
            "rain_mm",
            "rainfall_mm",
            "precip_mm",
        ],
    )

    if precip_1h_col is not None and pd.to_numeric(df[precip_1h_col], errors="coerce").notna().any():
        df["_rain_1h_mm"] = pd.to_numeric(df[precip_1h_col], errors="coerce").fillna(0.0).clip(lower=0.0)
        rain_source = precip_1h_col
    elif precip_cum_col is not None:
        cum = pd.to_numeric(df[precip_cum_col], errors="coerce").ffill().fillna(0.0)
        diff = cum.diff()
        # If cumulative rainfall resets, use the current cumulative value as the new increment.
        diff = diff.where(diff >= 0.0, cum)
        df["_rain_1h_mm"] = diff.fillna(0.0).clip(lower=0.0)
        rain_source = f"{precip_cum_col}_diff"
    else:
        df["_rain_1h_mm"] = 0.0
        rain_source = "missing_precipitation_assumed_zero"

    rh_col = _first_existing_col(
        df,
        [
            "relative_humidity_pct",
            "humidity_pct",
            "rh_pct",
            "RH",
        ],
    )
    if rh_col:
        df["_rh_pct"] = pd.to_numeric(df[rh_col], errors="coerce")
    else:
        df["_rh_pct"] = math.nan

    def window_sum(hours: int) -> float:
        start = as_of_ts - pd.Timedelta(hours=hours)
        return float(df.loc[df["_time"] > start, "_rain_1h_mm"].sum())

    def rh_ge_90_hours(hours: int) -> int | None:
        if "_rh_pct" not in df or df["_rh_pct"].notna().sum() == 0:
            return None
        start = as_of_ts - pd.Timedelta(hours=hours)
        return int((df.loc[df["_time"] > start, "_rh_pct"] >= 90.0).sum())

    metrics = {
        "as_of": str(as_of_ts),
        "weather_rows_used": int(len(df)),
        "weather_time_start": str(df["_time"].min()),
        "weather_time_end": str(df["_time"].max()),
        "rain_source": rain_source,
        "p1h_mm": window_sum(1),
        "p3h_mm": window_sum(3),
        "p24h_mm": window_sum(24),
        "p72h_mm": window_sum(72),
        "rh_ge_90h_24h": rh_ge_90_hours(24),
        "rh_ge_90h_72h": rh_ge_90_hours(72),
        "max_est_1h_mm_in_used_range": float(df["_rain_1h_mm"].max()),
    }
    return df, metrics


def _classify_rain(metrics: dict[str, Any]) -> tuple[str, list[str], float]:
    p1 = float(metrics.get("p1h_mm") or 0.0)
    p3 = float(metrics.get("p3h_mm") or 0.0)
    p24 = float(metrics.get("p24h_mm") or 0.0)
    p72 = float(metrics.get("p72h_mm") or 0.0)

    flags: list[str] = []

    if p1 >= RAIN_THRESHOLDS["cwa_heavy_rain"]["p1h_mm"] or p24 >= RAIN_THRESHOLDS["cwa_heavy_rain"]["p24h_mm"]:
        flags.append("CWA_HEAVY_RAIN_THRESHOLD")
    if p3 >= RAIN_THRESHOLDS["cwa_extremely_heavy_rain"]["p3h_mm"] or p24 >= RAIN_THRESHOLDS["cwa_extremely_heavy_rain"]["p24h_mm"]:
        flags.append("CWA_EXTREMELY_HEAVY_RAIN_THRESHOLD")

    if p24 >= RAIN_THRESHOLDS["route_wet_review"]["p24h_mm"] or p72 >= RAIN_THRESHOLDS["route_wet_review"]["p72h_mm"]:
        flags.append("ROUTE_WET_REVIEW")
    if p24 >= RAIN_THRESHOLDS["route_rainfall_sensitive"]["p24h_mm"] or p72 >= RAIN_THRESHOLDS["route_rainfall_sensitive"]["p72h_mm"]:
        flags.append("RECENT_RAINFALL_SENSITIVE")
    if (
        p1 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p1h_mm"]
        or p3 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p3h_mm"]
        or p24 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p24h_mm"]
        or p72 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p72h_mm"]
    ):
        flags.append("RAINWASH_HOTSPOT_HIGH_SENSITIVITY")

    if "CWA_EXTREMELY_HEAVY_RAIN_THRESHOLD" in flags:
        scenario = "extreme_rain_warning"
    elif "CWA_HEAVY_RAIN_THRESHOLD" in flags:
        scenario = "heavy_rain_warning"
    elif "RAINWASH_HOTSPOT_HIGH_SENSITIVITY" in flags:
        # Distinguish current rain from antecedent rain.
        # This matters because a 72h accumulated-rain signal should raise
        # rain-sensitive segments, but should not behave like an active storm.
        current_rain_high = (
            p1 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p1h_mm"]
            or p3 >= RAIN_THRESHOLDS["route_high_sensitivity"]["p3h_mm"]
        )
        if current_rain_high:
            scenario = "rain_event_high_sensitivity"
        else:
            scenario = "antecedent_rain_high_sensitivity"
    elif "RECENT_RAINFALL_SENSITIVE" in flags:
        scenario = "antecedent_rainfall_sensitive"
    elif "ROUTE_WET_REVIEW" in flags:
        scenario = "wet_review"
    else:
        scenario = "baseline"

    rain_factor = max(
        p1 / RAIN_THRESHOLDS["route_high_sensitivity"]["p1h_mm"],
        p3 / RAIN_THRESHOLDS["route_high_sensitivity"]["p3h_mm"],
        p24 / RAIN_THRESHOLDS["route_high_sensitivity"]["p24h_mm"],
        p72 / RAIN_THRESHOLDS["route_high_sensitivity"]["p72h_mm"],
    )
    rain_factor = _clip(rain_factor, 0.0, 1.25)

    return scenario, flags, rain_factor


def _read_hotspot(summary: dict[str, Any], hotspot_fp: Path) -> tuple[float | None, float | None, float | None]:
    # Try hotspot CSV first.
    if hotspot_fp.exists():
        try:
            df = _read_csv(hotspot_fp)
            if not df.empty:
                cols = list(df.columns)
                lower = {c.lower(): c for c in cols}

                start_col = None
                end_col = None
                len_col = None

                for c in cols:
                    lc = c.lower()
                    if start_col is None and "start" in lc and ("m" in lc or "dist" in lc or "route" in lc):
                        start_col = c
                    if end_col is None and "end" in lc and ("m" in lc or "dist" in lc or "route" in lc):
                        end_col = c
                    if len_col is None and ("length" in lc and "m" in lc):
                        len_col = c

                row = df.iloc[0]
                hs_start = _to_float(row[start_col]) if start_col else None
                hs_end = _to_float(row[end_col]) if end_col else None
                hs_len = _to_float(row[len_col]) if len_col else None

                if hs_start is not None and hs_end is not None:
                    if hs_len is None:
                        hs_len = abs(hs_end - hs_start)
                    return hs_start, hs_end, hs_len
        except Exception:
            pass

    # Fallback: parse summary text like "2460.0-3020.0 m, length 560.0 m"
    s = str(summary.get("hotspot_used_for_radar", ""))
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*m", s)
    if m:
        hs_start = float(m.group(1))
        hs_end = float(m.group(2))
        hs_len = abs(hs_end - hs_start)
        return hs_start, hs_end, hs_len

    return None, None, None


def _make_segments(
    route_len_m: float,
    summary: dict[str, Any],
    hotspot_start_m: float | None,
    hotspot_end_m: float | None,
) -> list[dict[str, Any]]:
    trail_start_km = _to_float(summary.get("trail_start_route_km"), None)
    trail_end_km = _to_float(summary.get("trail_end_route_km"), None)

    boundaries = [0.0, route_len_m]

    if trail_start_km is not None:
        boundaries.append(trail_start_km * 1000.0)
    if trail_end_km is not None:
        boundaries.append(trail_end_km * 1000.0)
    if hotspot_start_m is not None:
        boundaries.append(hotspot_start_m)
    if hotspot_end_m is not None:
        boundaries.append(hotspot_end_m)

    boundaries = sorted({round(_clip(b, 0.0, route_len_m), 3) for b in boundaries})
    boundaries = [b for b in boundaries if 0.0 <= b <= route_len_m]

    segments = []
    for i in range(len(boundaries) - 1):
        s = boundaries[i]
        e = boundaries[i + 1]
        if e - s < 1.0:
            continue

        overlap_hotspot = False
        if hotspot_start_m is not None and hotspot_end_m is not None:
            overlap = max(0.0, min(e, hotspot_end_m) - max(s, hotspot_start_m))
            overlap_hotspot = overlap > 1.0

        in_butterfly_trail = False
        if trail_start_km is not None and trail_end_km is not None:
            ts = trail_start_km * 1000.0
            te = trail_end_km * 1000.0
            overlap = max(0.0, min(e, te) - max(s, ts))
            in_butterfly_trail = overlap > 1.0

        if overlap_hotspot:
            name = "高分複核區 / 雨水匯流敏感段"
        elif in_butterfly_trail:
            name = "蝴蝶谷瀑布步道一般段"
        elif trail_start_km is not None and e <= trail_start_km * 1000.0:
            name = "起登至蝴蝶谷瀑布步道銜接前"
        else:
            name = "回程或非熱點段"

        segments.append(
            {
                "segment_id": f"S{i+1:02d}",
                "segment_name": name,
                "start_m": s,
                "end_m": e,
                "length_m": e - s,
                "overlap_hotspot": overlap_hotspot,
                "in_butterfly_trail": in_butterfly_trail,
            }
        )

    return segments




def _df_to_markdown_simple(df: pd.DataFrame) -> str:
    """Write a dependency-free GitHub-style markdown table.

    This avoids pandas.DataFrame.to_markdown(), which requires the optional
    tabulate package and may not exist in the runtime environment.
    """
    if df is None or df.empty:
        return "_No rows_"

    cols = [str(c) for c in df.columns]

    def fmt(v: Any) -> str:
        if v is None or pd.isna(v):
            return ""
        s = str(v)
        s = s.replace("|", "\\|")
        s = s.replace("\n", " ")
        return s

    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")

    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in df.columns) + " |")

    return "\n".join(lines)


def _risk_label(v: float) -> str:
    if v >= 0.88:
        return "avoid_or_manual_review"
    if v >= 0.82:
        return "high_review"
    if v >= 0.76:
        return "elevated_review"
    return "baseline_review"


def _segment_rain_sensitivity(row: dict[str, Any], rainwash_axis_score: float | None) -> float:
    if row["overlap_hotspot"]:
        base = 0.90
    elif row["in_butterfly_trail"]:
        base = 0.65
    else:
        base = 0.35

    if rainwash_axis_score is not None and rainwash_axis_score >= 0.8 and row["overlap_hotspot"]:
        base += 0.05

    return _clip(base, 0.0, 1.0)


def build_fusion(case_id: str, weather_csv: Path, as_of: str | None = None) -> dict[str, Any]:
    case_out = OUT_ROOT / case_id
    case_out.mkdir(parents=True, exist_ok=True)

    ib2d_dir = IB2D_ROOT / case_id
    summary_fp = ib2d_dir / f"{case_id}_upslope_contributing_hazard_map_summary.csv"
    hotspot_fp = ib2d_dir / f"{case_id}_upslope_contributing_hazard_hotspots.csv"

    summary = _parse_summary(summary_fp)

    thci_weather_fp = (
        THCI_WEATHER_DIAG_ROOT
        / case_id
        / f"{case_id}_weather_sensitivity_diagnostic_v1_0b.csv"
    )
    thci_weather = _read_csv(thci_weather_fp).iloc[0].to_dict() if thci_weather_fp.exists() else {}

    route_len_m = _to_float(thci_weather.get("total_route_distance_m"), None)
    if route_len_m is None:
        route_len_m = _to_float(summary.get("total_route_distance_m"), None)
    if route_len_m is None:
        route_len_m = _to_float(summary.get("route_len_m"), None)
    if route_len_m is None:
        route_len_m = 5478.912140050307

    score_min = _to_float(summary.get("score_min"), 0.70) or 0.70
    score_mean = _to_float(summary.get("score_mean"), 0.75) or 0.75
    score_max = _to_float(summary.get("score_max"), 0.84) or 0.84

    hotspot_start_m, hotspot_end_m, hotspot_len_m = _read_hotspot(summary, hotspot_fp)

    radar_scores = _parse_list_like_scores(summary.get("upslope_radar_axis_scores"))
    rainwash_axis_score = radar_scores[5] if len(radar_scores) >= 6 else None

    _, weather_metrics = _read_weather(weather_csv, as_of=as_of)
    scenario, rain_flags, rain_factor = _classify_rain(weather_metrics)

    segments = _make_segments(route_len_m, summary, hotspot_start_m, hotspot_end_m)

    out_rows = []
    for seg in segments:
        rain_sens = _segment_rain_sensitivity(seg, rainwash_axis_score)
        static_hazard = score_max if seg["overlap_hotspot"] else (score_mean if seg["in_butterfly_trail"] else score_min)
        # Separate active-rain amplification from antecedent-rain amplification.
        # Active rain can modify the route more strongly. Antecedent rain should
        # raise rain-sensitive segments but should preserve hotspot contrast.
        p1h = float(weather_metrics.get("p1h_mm") or 0.0)
        p3h = float(weather_metrics.get("p3h_mm") or 0.0)
        p24h = float(weather_metrics.get("p24h_mm") or 0.0)
        p72h = float(weather_metrics.get("p72h_mm") or 0.0)

        is_official_heavy = (
            p1h >= RAIN_THRESHOLDS["cwa_heavy_rain"]["p1h_mm"]
            or p24h >= RAIN_THRESHOLDS["cwa_heavy_rain"]["p24h_mm"]
            or p3h >= RAIN_THRESHOLDS["cwa_extremely_heavy_rain"]["p3h_mm"]
        )
        is_active_route_rain = (
            p1h >= 10.0
            or p3h >= 20.0
        )
        is_antecedent_high = (
            p24h >= 50.0
            or p72h >= 150.0
        )
        is_antecedent_review = (
            p24h >= 20.0
            or p72h >= 50.0
        )

        if is_official_heavy:
            weather_scale = 0.15
            effective_rain_factor = _clip(rain_factor, 0.0, 1.25)
        elif is_active_route_rain:
            weather_scale = 0.12
            effective_rain_factor = _clip(rain_factor, 0.0, 1.0)
        elif is_antecedent_high:
            weather_scale = 0.08
            effective_rain_factor = _clip(rain_factor, 0.0, 1.0)
        elif is_antecedent_review:
            weather_scale = 0.05
            effective_rain_factor = _clip(rain_factor, 0.0, 1.0)
        else:
            weather_scale = 0.0
            effective_rain_factor = 0.0

        weather_add = weather_scale * effective_rain_factor * rain_sens

        # Give the actual rainwash hotspot a small explicit bump under rain context,
        # but avoid saturating to 1.0 unless later field evidence justifies it.
        if seg["overlap_hotspot"] and weather_scale > 0.0:
            weather_add += 0.02 * effective_rain_factor

        adjusted_hazard = _clip(static_hazard + weather_add, 0.0, 0.96)

        flags = []
        if seg["overlap_hotspot"]:
            flags.append("RAINWASH_HOTSPOT_PRESENT")
        if seg["overlap_hotspot"] and rain_factor > 0.0:
            flags.append("RAINWASH_HOTSPOT_WEATHER_ADJUSTED")
        flags.extend(rain_flags)

        out_rows.append(
            {
                "case_id": case_id,
                "scenario": scenario,
                "segment_id": seg["segment_id"],
                "segment_name": seg["segment_name"],
                "start_m": round(seg["start_m"], 1),
                "end_m": round(seg["end_m"], 1),
                "length_m": round(seg["length_m"], 1),
                "overlap_hotspot": seg["overlap_hotspot"],
                "in_butterfly_trail": seg["in_butterfly_trail"],
                "static_hazard_score": round(static_hazard, 4),
                "rain_sensitivity": round(rain_sens, 4),
                "rain_factor": round(rain_factor, 4),
                "effective_rain_factor": round(effective_rain_factor, 4),
                "weather_scale": round(weather_scale, 4),
                "weather_adjusted_hazard_score": round(adjusted_hazard, 4),
                "weather_adjusted_label": _risk_label(adjusted_hazard),
                "flags": "|".join(dict.fromkeys(flags)),
            }
        )

    seg_df = pd.DataFrame(out_rows)
    seg_csv = case_out / f"{case_id}_weather_terrain_fusion_segment_risk.csv"
    seg_md = case_out / f"{case_id}_weather_terrain_fusion_segment_risk.md"
    summary_json = case_out / f"{case_id}_weather_terrain_fusion_summary.json"
    summary_md = case_out / f"{case_id}_weather_terrain_fusion_summary.md"

    seg_df.to_csv(seg_csv, index=False, encoding="utf-8-sig")
    seg_md.write_text(_df_to_markdown_simple(seg_df), encoding="utf-8")

    fusion_summary = {
        "case_id": case_id,
        "weather_csv": str(weather_csv),
        "as_of": weather_metrics["as_of"],
        "scenario": scenario,
        "rain_flags": rain_flags,
        "rain_factor": rain_factor,
        "weather_metrics": weather_metrics,
        "route_len_m": route_len_m,
        "hotspot_start_m": hotspot_start_m,
        "hotspot_end_m": hotspot_end_m,
        "hotspot_len_m": hotspot_len_m,
        "rainwash_axis_score": rainwash_axis_score,
        "score_min": score_min,
        "score_mean": score_mean,
        "score_max": score_max,
        "outputs": {
            "segment_csv": str(seg_csv),
            "segment_md": str(seg_md),
            "summary_json": str(summary_json),
            "summary_md": str(summary_md),
        },
        "notes": [
            "Official CWA heavy-rain thresholds are used as red-line thresholds.",
            "Route-sensitive 20/50/72h thresholds are review triggers, not official weather alerts.",
            "This is a fusion scenario table; it does not overwrite IB2D or THCI source scores.",
        ],
    }

    summary_json.write_text(json.dumps(fusion_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"# {case_id} weather-terrain fusion scenario\n")
    lines.append(f"- scenario: `{scenario}`")
    lines.append(f"- as_of: `{weather_metrics['as_of']}`")
    lines.append(f"- p1h_mm: `{weather_metrics['p1h_mm']:.2f}`")
    lines.append(f"- p3h_mm: `{weather_metrics['p3h_mm']:.2f}`")
    lines.append(f"- p24h_mm: `{weather_metrics['p24h_mm']:.2f}`")
    lines.append(f"- p72h_mm: `{weather_metrics['p72h_mm']:.2f}`")
    lines.append(f"- rain_factor: `{rain_factor:.4f}`")
    lines.append(f"- rain_flags: `{ '|'.join(rain_flags) if rain_flags else 'none' }`")
    lines.append(f"- hotspot: `{hotspot_start_m}-{hotspot_end_m} m`, length `{hotspot_len_m}`")
    lines.append(f"- rainwash_axis_score: `{rainwash_axis_score}`")
    lines.append("\n## Segment table\n")
    lines.append(_df_to_markdown_simple(seg_df))
    lines.append("\n\n## Notes\n")
    lines.append("- 20/50/72h rainfall thresholds are route-sensitive review triggers.")
    lines.append("- CWA heavy-rain thresholds are used as official red-line references.")
    lines.append("- This script writes scenario evidence only; it does not alter IB2D source files.")
    summary_md.write_text("\n".join(lines), encoding="utf-8")

    return fusion_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build IB2D × weather terrain-fusion scenario table for route-segment rainfall-sensitive review."
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--weather-csv", required=True, help="Weather CSV, e.g. weather.history.csv")
    parser.add_argument("--as-of", default=None, help="Optional datetime cutoff. Default uses latest weather row.")
    args = parser.parse_args()

    result = build_fusion(
        case_id=args.case_id,
        weather_csv=Path(args.weather_csv),
        as_of=args.as_of,
    )

    print("DONE")
    print("case_id:", result["case_id"])
    print("scenario:", result["scenario"])
    print("as_of:", result["as_of"])
    print("rain_flags:", "|".join(result["rain_flags"]) if result["rain_flags"] else "none")
    print("rain_factor:", result["rain_factor"])
    for k, v in result["weather_metrics"].items():
        print(f"{k}: {v}")
    print("segment_csv:", result["outputs"]["segment_csv"])
    print("summary_md:", result["outputs"]["summary_md"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
