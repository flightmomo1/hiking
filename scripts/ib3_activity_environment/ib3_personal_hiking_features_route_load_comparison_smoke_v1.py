from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


SCHEMA_VERSION = "ib3_personal_hiking_features_route_load_comparison_smoke_v1"
PASS_CONCLUSION = "PASS_ROUTE_LOAD_BEHAVIOR_RESPONSE_FIXTURE_SMOKE_DESCRIPTIVE_ONLY"
FAIL_CONCLUSION = "FAIL_ROUTE_LOAD_BEHAVIOR_RESPONSE_FIXTURE_SMOKE"

DEFAULT_GATE_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/"
    "activity_v0_usability_gate_smoke.csv"
)
DEFAULT_ACTIVITY_CONTEXT_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1/"
    "activity_route_profile_ascent_features.csv"
)
DEFAULT_ENRICHED_ROOT = Path(
    "outputs/"
    "ib3a_rc_backend_activity_enriched_v1l2_osm_radar_evidence_"
    "qixing_lengshuikeng_full26"
)
DEFAULT_OUT_ROOT = Path(
    "outputs/ib3_personal_hiking_features_route_load_comparison_smoke_v1"
)
DEFAULT_FIXTURE_IDS = ("3_1", "8_1", "9_1")
SUPPORTED_USABLE_GATES = {"USABLE", "USABLE_FOR_V0_MODEL_SMOKE"}
ELIGIBLE_ROUTE_CLASSES = {
    "MAINLINE_CORE",
    "MAINLINE_SUMMIT_STAY",
    "CONNECTOR",
}
WINDOW_SIZE_M = 50.0
LOW_SPEED_THRESHOLD_MPS = 0.25

BLOCKED_LEGACY_GAIN_FIELDS = {
    "calibrated_cumulative_gain_m",
    "calibrated_cumulative_loss_m",
    "agg_total_gain_m",
    "agg_total_loss_m",
    "candidate_gain_m_per_km",
    "candidate_gain_rate_m_per_hour",
    "candidate_duration_min_per_100m_gain",
}

PROHIBITED_GENERATED_FIELDS = {
    "ability_score",
    "ability_rank",
    "ability_class",
    "thci_score",
    "radar_score",
    "final_hiking_risk_score",
}

WEATHER_FIELDS = (
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_gust_ms",
    "uv_index",
)

EXPOSURE_FIELDS = {
    "steps": ("near_steps_flag", "nearest_steps_dist_m"),
    "guidepost": ("near_guidepost_flag", "nearest_guidepost_dist_m"),
    "shelter": ("near_shelter_flag", "nearest_shelter_dist_m"),
    "waterway": ("near_waterway_flag", "nearest_waterway_dist_m"),
    "cliff": ("near_cliff_flag", "nearest_cliff_dist_m"),
    "road": ("near_road_flag", "nearest_road_dist_m"),
    "bridge": ("near_bridge_flag", "nearest_bridge_dist_m"),
    "trailhead": ("near_trailhead_flag", "nearest_trailhead_dist_m"),
    "peak": ("near_peak_flag", "nearest_peak_dist_m"),
}

WINDOW_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "fixture_activity",
    "route_distance_window_start_m",
    "route_distance_window_end_m",
    "route_phase",
    "point_count",
    "duration_observed_sec",
    "elapsed_time_span_sec",
    "speed_mps_median",
    "speed_mps_p25",
    "speed_mps_p75",
    "stopped_ratio",
    "low_speed_ratio",
    "heart_rate_bpm_median",
    "heart_rate_bpm_p75",
    "heart_rate_bpm_p90",
    "calibrated_slope_pct_median",
    "calibrated_slope_pct_p75_abs",
    "route_profile_elevation_min_m",
    "route_profile_elevation_max_m",
    "route_profile_elevation_range_m",
    "ib2_terrain_evidence_median",
    "ib2_effort_evidence_median",
    "ib2_exposure_evidence_median",
    "ib2_risk_band_evidence",
    "route_load_context_band",
    "osm_exposure_types",
    "near_steps_ratio",
    "near_guidepost_ratio",
    "near_shelter_ratio",
    "near_waterway_ratio",
    "near_cliff_ratio",
    "near_road_ratio",
    "nearest_environment_feature_distance_m_min",
    "temperature_c",
    "relative_humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_gust_ms",
    "uv_index",
    "weather_context_flags",
    "weather_context_available",
    "analytics_ready_ratio",
    "calibration_review_required_ratio",
    "movement_review_required_ratio",
    "slope_review_required_ratio",
    "window_qa_flags",
    "interpretation_boundary",
]

SUMMARY_FIELDS = [
    "schema_version",
    "activity_id_short",
    "activity_id_full",
    "fixture_activity",
    "window_count",
    "total_covered_route_window_count",
    "route_distance_min_m",
    "route_distance_max_m",
    "duration_observed_sec",
    "window_speed_mps_mean",
    "window_speed_mps_median",
    "stopped_ratio_mean",
    "low_speed_ratio_mean",
    "heart_rate_bpm_median",
    "high_load_window_count",
    "high_load_speed_mps_median",
    "high_load_stopped_ratio_mean",
    "high_load_low_speed_ratio_mean",
    "high_load_heart_rate_bpm_median",
    "weather_context_available",
    "weather_observed_numeric_count",
    "weather_missing_numeric_count",
    "weather_context_flags",
    "review_window_count",
    "review_flag_summary",
    "legacy_gain_fields_used_count",
    "prohibited_score_rank_class_generated_count",
    "interpretation_boundary",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a three-activity descriptive route-load and behavior "
            "response fixture smoke."
        )
    )
    parser.add_argument("--gate-csv", type=Path, default=DEFAULT_GATE_CSV)
    parser.add_argument(
        "--activity-context-csv",
        type=Path,
        default=DEFAULT_ACTIVITY_CONTEXT_CSV,
    )
    parser.add_argument(
        "--enriched-root", type=Path, default=DEFAULT_ENRICHED_ROOT
    )
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument(
        "--fixture-activity-ids",
        default=",".join(DEFAULT_FIXTURE_IDS),
        help="Comma-separated activity_id_short values.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(
    path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_fields = fields or list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=output_fields, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return None if math.isnan(number) else number


def as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def fmt(value: float | None, digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def percentile_inc(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def optional_median(values: list[float]) -> float | None:
    return median(values) if values else None


def optional_mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def dominant(values: list[str]) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    counts = Counter(filtered)
    return sorted(counts, key=lambda item: (-counts[item], item))[0]


def ratio_true(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def load_context_band(
    slope_p75_abs: float | None,
    effort_median: float | None,
    risk_band: str,
) -> str:
    risk = risk_band.strip().lower()
    if (
        (slope_p75_abs is not None and slope_p75_abs >= 15.0)
        or (effort_median is not None and effort_median >= 0.6)
        or risk in {"high", "very_high", "very high"}
    ):
        return "HIGH_ROUTE_LOAD_EVIDENCE"
    if (
        (slope_p75_abs is not None and slope_p75_abs >= 8.0)
        or (effort_median is not None and effort_median >= 0.35)
        or risk == "moderate"
    ):
        return "MODERATE_ROUTE_LOAD_EVIDENCE"
    return "LOWER_ROUTE_LOAD_EVIDENCE"


def new_bucket() -> dict[str, Any]:
    return {
        "point_count": 0,
        "duration_sec": 0.0,
        "elapsed": [],
        "speed": [],
        "hr": [],
        "slope": [],
        "elevation": [],
        "terrain": [],
        "effort": [],
        "exposure": [],
        "risk_band": [],
        "stopped": [],
        "low_speed": [],
        "analytics_ready": [],
        "calibration_review": [],
        "movement_review": [],
        "slope_review": [],
        "exposure_flags": defaultdict(list),
        "environment_distances": [],
    }


def enriched_path(root: Path, activity_id_full: str) -> Path:
    return root / (
        f"{activity_id_full}_backend_activity_enriched_"
        "v1l2_osm_radar_evidence.csv"
    )


def collect_activity_windows(
    path: Path,
    activity_short: str,
    activity_full: str,
    context: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    buckets: dict[tuple[float, str], dict[str, Any]] = {}
    counters = {
        "source_row_count": 0,
        "eligible_route_row_count": 0,
        "joined_route_row_count": 0,
        "missing_route_distance_count": 0,
        "missing_activity_id_count": 0,
    }

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        source_fields = set(reader.fieldnames or [])
        legacy_present = sorted(BLOCKED_LEGACY_GAIN_FIELDS & source_fields)
        if legacy_present:
            # Presence is expected for traceability. No legacy field is read.
            pass
        for row in reader:
            counters["source_row_count"] += 1
            if not str(row.get("activity_id", "")).strip():
                counters["missing_activity_id_count"] += 1
            if row.get("route_class", "") not in ELIGIBLE_ROUTE_CLASSES:
                continue
            counters["eligible_route_row_count"] += 1
            if row.get("v1l2_join_status", "") != "JOINED":
                continue
            counters["joined_route_row_count"] += 1
            route_distance = as_float(row.get("v1l2_ib2_dist_m"))
            if route_distance is None:
                counters["missing_route_distance_count"] += 1
                continue

            window_start = math.floor(route_distance / WINDOW_SIZE_M) * WINDOW_SIZE_M
            route_phase = str(row.get("route_phase", "")).strip() or "UNKNOWN"
            key = (window_start, route_phase)
            bucket = buckets.setdefault(key, new_bucket())
            bucket["point_count"] += 1

            dt_sec = as_float(row.get("dt_sec"))
            if dt_sec is not None and 0.0 < dt_sec <= 30.0:
                bucket["duration_sec"] += dt_sec
            elapsed = as_float(row.get("elapsed_sec"))
            if elapsed is not None:
                bucket["elapsed"].append(elapsed)

            speed = as_float(row.get("calibrated_speed_mps"))
            if speed is not None:
                bucket["speed"].append(speed)
            movement_state = str(row.get("movement_state", "")).strip()
            stopped = movement_state == "STOPPED"
            low_speed = (
                not stopped
                and (
                    movement_state == "SLOW_MOVING"
                    or (speed is not None and speed <= LOW_SPEED_THRESHOLD_MPS)
                )
            )
            bucket["stopped"].append(stopped)
            bucket["low_speed"].append(low_speed)

            for target, source in (
                ("hr", "heart_rate_bpm"),
                ("slope", "calibrated_slope_pct"),
                ("elevation", "elevation_profile_ele_smooth_m"),
                ("terrain", "ib2_terrain_score"),
                ("effort", "ib2_effort_score"),
                ("exposure", "ib2_exposure_score"),
            ):
                value = as_float(row.get(source))
                if value is not None:
                    bucket[target].append(value)

            risk_band = str(row.get("ib2_risk_band", "")).strip()
            if risk_band:
                bucket["risk_band"].append(risk_band)

            bucket["analytics_ready"].append(
                row.get("backend_use_policy", "") == "ANALYTICS_READY"
            )
            bucket["calibration_review"].append(
                as_bool(row.get("calibration_review_required"))
            )
            bucket["movement_review"].append(
                as_bool(row.get("movement_review_required_v1k2"))
                or as_bool(row.get("movement_review_required"))
            )
            bucket["slope_review"].append(
                as_bool(row.get("slope_review_required"))
            )

            for exposure_name, (flag_field, distance_field) in EXPOSURE_FIELDS.items():
                flag = as_bool(row.get(flag_field))
                bucket["exposure_flags"][exposure_name].append(flag)
                distance = as_float(row.get(distance_field))
                if distance is not None:
                    bucket["environment_distances"].append(distance)

    rows: list[dict[str, Any]] = []
    weather_values = {field: context.get(field, "") for field in WEATHER_FIELDS}
    weather_available = any(
        as_float(weather_values[field]) is not None for field in WEATHER_FIELDS
    )
    weather_flags = (
        context.get("candidate_weather_context_flags_reattached", "").strip()
        or context.get("candidate_weather_context_flags", "").strip()
    )

    for (window_start, route_phase), bucket in sorted(buckets.items()):
        slope_abs = [abs(value) for value in bucket["slope"]]
        slope_p75_abs = percentile_inc(slope_abs, 0.75)
        effort_median = optional_median(bucket["effort"])
        risk_band = dominant(bucket["risk_band"])
        load_band = load_context_band(slope_p75_abs, effort_median, risk_band)
        elevation_min = min(bucket["elevation"]) if bucket["elevation"] else None
        elevation_max = max(bucket["elevation"]) if bucket["elevation"] else None
        elapsed_span = (
            max(bucket["elapsed"]) - min(bucket["elapsed"])
            if bucket["elapsed"]
            else None
        )
        exposure_types = sorted(
            name
            for name, flags in bucket["exposure_flags"].items()
            if any(flags)
        )

        qa_flags: list[str] = []
        if not bucket["slope"] and not bucket["elevation"]:
            qa_flags.append("ROUTE_PROFILE_CONTEXT_MISSING")
        if not bucket["terrain"] and not bucket["effort"] and not bucket["exposure"]:
            qa_flags.append("IB2_ROUTE_LOAD_EVIDENCE_MISSING")
        if not bucket["speed"] or bucket["duration_sec"] <= 0:
            qa_flags.append("BEHAVIOR_EVIDENCE_MISSING")
        if ratio_true(bucket["calibration_review"]) not in {None, 0.0}:
            qa_flags.append("CALIBRATION_REVIEW_PRESENT")
        if ratio_true(bucket["movement_review"]) not in {None, 0.0}:
            qa_flags.append("MOVEMENT_REVIEW_PRESENT")
        if ratio_true(bucket["slope_review"]) not in {None, 0.0}:
            qa_flags.append("SLOPE_REVIEW_PRESENT")
        if route_phase == "UNKNOWN":
            qa_flags.append("ROUTE_PHASE_UNKNOWN")
        if not weather_available:
            qa_flags.append("WEATHER_CONTEXT_MISSING_NOT_ZERO_FILLED")

        row = {
            "schema_version": SCHEMA_VERSION,
            "activity_id_short": activity_short,
            "activity_id_full": activity_full,
            "fixture_activity": "True",
            "route_distance_window_start_m": fmt(window_start),
            "route_distance_window_end_m": fmt(window_start + WINDOW_SIZE_M),
            "route_phase": route_phase,
            "point_count": bucket["point_count"],
            "duration_observed_sec": fmt(bucket["duration_sec"]),
            "elapsed_time_span_sec": fmt(elapsed_span),
            "speed_mps_median": fmt(optional_median(bucket["speed"])),
            "speed_mps_p25": fmt(percentile_inc(bucket["speed"], 0.25)),
            "speed_mps_p75": fmt(percentile_inc(bucket["speed"], 0.75)),
            "stopped_ratio": fmt(ratio_true(bucket["stopped"])),
            "low_speed_ratio": fmt(ratio_true(bucket["low_speed"])),
            "heart_rate_bpm_median": fmt(optional_median(bucket["hr"])),
            "heart_rate_bpm_p75": fmt(percentile_inc(bucket["hr"], 0.75)),
            "heart_rate_bpm_p90": fmt(percentile_inc(bucket["hr"], 0.90)),
            "calibrated_slope_pct_median": fmt(optional_median(bucket["slope"])),
            "calibrated_slope_pct_p75_abs": fmt(slope_p75_abs),
            "route_profile_elevation_min_m": fmt(elevation_min),
            "route_profile_elevation_max_m": fmt(elevation_max),
            "route_profile_elevation_range_m": fmt(
                elevation_max - elevation_min
                if elevation_min is not None and elevation_max is not None
                else None
            ),
            "ib2_terrain_evidence_median": fmt(
                optional_median(bucket["terrain"])
            ),
            "ib2_effort_evidence_median": fmt(effort_median),
            "ib2_exposure_evidence_median": fmt(
                optional_median(bucket["exposure"])
            ),
            "ib2_risk_band_evidence": risk_band,
            "route_load_context_band": load_band,
            "osm_exposure_types": "|".join(exposure_types),
            "near_steps_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["steps"])
            ),
            "near_guidepost_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["guidepost"])
            ),
            "near_shelter_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["shelter"])
            ),
            "near_waterway_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["waterway"])
            ),
            "near_cliff_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["cliff"])
            ),
            "near_road_ratio": fmt(
                ratio_true(bucket["exposure_flags"]["road"])
            ),
            "nearest_environment_feature_distance_m_min": fmt(
                min(bucket["environment_distances"])
                if bucket["environment_distances"]
                else None
            ),
            **weather_values,
            "weather_context_flags": weather_flags,
            "weather_context_available": str(weather_available),
            "analytics_ready_ratio": fmt(ratio_true(bucket["analytics_ready"])),
            "calibration_review_required_ratio": fmt(
                ratio_true(bucket["calibration_review"])
            ),
            "movement_review_required_ratio": fmt(
                ratio_true(bucket["movement_review"])
            ),
            "slope_review_required_ratio": fmt(
                ratio_true(bucket["slope_review"])
            ),
            "window_qa_flags": "|".join(qa_flags),
            "interpretation_boundary": (
                "Descriptive route-load, behavior, proximity exposure, and "
                "weather evidence only; no ability or risk scoring."
            ),
        }
        rows.append(row)
    return rows, counters


def summarize_activity(
    activity_short: str,
    activity_full: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    def values(field: str) -> list[float]:
        parsed = [as_float(row.get(field)) for row in rows]
        return [value for value in parsed if value is not None]

    high_load = [
        row
        for row in rows
        if row["route_load_context_band"] == "HIGH_ROUTE_LOAD_EVIDENCE"
    ]

    def high_values(field: str) -> list[float]:
        parsed = [as_float(row.get(field)) for row in high_load]
        return [value for value in parsed if value is not None]

    weather_numeric_count = sum(
        as_float(rows[0].get(field)) is not None for field in WEATHER_FIELDS
    )
    qa_counter: Counter[str] = Counter()
    for row in rows:
        for flag in str(row.get("window_qa_flags", "")).split("|"):
            if flag:
                qa_counter[flag] += 1

    route_starts = values("route_distance_window_start_m")
    return {
        "schema_version": SCHEMA_VERSION,
        "activity_id_short": activity_short,
        "activity_id_full": activity_full,
        "fixture_activity": "True",
        "window_count": len(rows),
        "total_covered_route_window_count": len(
            {
                (
                    row["route_distance_window_start_m"],
                    row["route_distance_window_end_m"],
                )
                for row in rows
            }
        ),
        "route_distance_min_m": fmt(min(route_starts) if route_starts else None),
        "route_distance_max_m": fmt(
            max(values("route_distance_window_end_m"))
            if values("route_distance_window_end_m")
            else None
        ),
        "duration_observed_sec": fmt(sum(values("duration_observed_sec"))),
        "window_speed_mps_mean": fmt(optional_mean(values("speed_mps_median"))),
        "window_speed_mps_median": fmt(
            optional_median(values("speed_mps_median"))
        ),
        "stopped_ratio_mean": fmt(optional_mean(values("stopped_ratio"))),
        "low_speed_ratio_mean": fmt(optional_mean(values("low_speed_ratio"))),
        "heart_rate_bpm_median": fmt(
            optional_median(values("heart_rate_bpm_median"))
        ),
        "high_load_window_count": len(high_load),
        "high_load_speed_mps_median": fmt(
            optional_median(high_values("speed_mps_median"))
        ),
        "high_load_stopped_ratio_mean": fmt(
            optional_mean(high_values("stopped_ratio"))
        ),
        "high_load_low_speed_ratio_mean": fmt(
            optional_mean(high_values("low_speed_ratio"))
        ),
        "high_load_heart_rate_bpm_median": fmt(
            optional_median(high_values("heart_rate_bpm_median"))
        ),
        "weather_context_available": rows[0]["weather_context_available"],
        "weather_observed_numeric_count": weather_numeric_count,
        "weather_missing_numeric_count": len(WEATHER_FIELDS)
        - weather_numeric_count,
        "weather_context_flags": rows[0]["weather_context_flags"],
        "review_window_count": sum(
            bool(str(row.get("window_qa_flags", "")).strip()) for row in rows
        ),
        "review_flag_summary": "|".join(
            f"{key}:{qa_counter[key]}" for key in sorted(qa_counter)
        ),
        "legacy_gain_fields_used_count": 0,
        "prohibited_score_rank_class_generated_count": 0,
        "interpretation_boundary": (
            "Fixture summary only; high-load behavior is descriptive and "
            "must not be interpreted as ability, rank, class, or risk."
        ),
    }


def render_html(
    path: Path,
    fixture_ids: list[str],
    summaries: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    audit: dict[str, Any],
) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    def table(rows: list[dict[str, Any]], fields: list[str]) -> str:
        head = "".join(f"<th>{esc(field)}</th>" for field in fields)
        body = "".join(
            "<tr>"
            + "".join(f"<td>{esc(row.get(field, ''))}</td>" for field in fields)
            + "</tr>"
            for row in rows
        )
        return (
            '<div class="table-wrap"><table><thead><tr>'
            + head
            + "</tr></thead><tbody>"
            + body
            + "</tbody></table></div>"
        )

    summary_view = [
        "activity_id_short",
        "window_count",
        "total_covered_route_window_count",
        "window_speed_mps_median",
        "stopped_ratio_mean",
        "low_speed_ratio_mean",
        "heart_rate_bpm_median",
        "high_load_window_count",
        "weather_observed_numeric_count",
        "review_window_count",
    ]
    window_view = [
        "activity_id_short",
        "route_distance_window_start_m",
        "route_distance_window_end_m",
        "route_phase",
        "point_count",
        "speed_mps_median",
        "stopped_ratio",
        "low_speed_ratio",
        "heart_rate_bpm_median",
        "calibrated_slope_pct_p75_abs",
        "ib2_risk_band_evidence",
        "route_load_context_band",
        "osm_exposure_types",
        "window_qa_flags",
    ]
    audit_view = list(audit.keys())

    text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3 Route Load Behavior Response Fixture Smoke</title>
<style>
body{{font-family:Arial,"Noto Sans TC",sans-serif;margin:24px;color:#1f2933}}
.note{{background:#fff8dc;border-left:4px solid #b7791f;padding:12px;line-height:1.6}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:16px 0}}
.card{{border:1px solid #d8dee4;border-radius:8px;padding:12px;background:#f8fafc}}
.card strong{{display:block;font-size:20px}}.card span{{color:#52606d;font-size:12px}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0 24px}}
th,td{{border:1px solid #d8dee4;padding:6px;text-align:left;vertical-align:top}}
th{{background:#eef2f6}}
</style>
</head>
<body>
<h1>IB3 Route Load Behavior Response Fixture Smoke</h1>
<p class="note"><strong>Boundary:</strong> Descriptive fixture evidence only.
No ability score, rank, class, THCI score, radar score, or final hiking risk
score is generated. IB2 values remain route evidence. OSM proximity does not
prove facility use. Missing weather remains blank.</p>
<div class="cards">
<div class="card"><strong>{len(fixture_ids)}</strong><span>fixture activities</span></div>
<div class="card"><strong>{len(windows)}</strong><span>50m phase-window rows</span></div>
<div class="card"><strong>{esc(audit["legacy_gain_fields_used_count"])}</strong><span>legacy gain fields used</span></div>
<div class="card"><strong>{esc(audit["audit_conclusion"])}</strong><span>audit conclusion</span></div>
</div>
<h2>Fixture activity coverage</h2>
{table(summaries, summary_view)}
<h2>Window examples</h2>
<p>Rows are shown in route-distance order within each fixture activity. They are
not an activity or person ranking.</p>
{table(windows[:60], window_view)}
<h2>Audit</h2>
{table([audit], audit_view)}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    fixture_ids = [
        item.strip()
        for item in args.fixture_activity_ids.split(",")
        if item.strip()
    ]
    if not 2 <= len(fixture_ids) <= 3:
        raise ValueError("Fixture smoke requires two or three activity ids")

    gate_rows = read_csv(args.gate_csv)
    context_rows = read_csv(args.activity_context_csv)
    gate_by_short = {
        row.get("activity_id_short", "").strip(): row for row in gate_rows
    }
    context_by_short = {
        row.get("activity_id_short", "").strip(): row for row in context_rows
    }
    usable_rows = [
        row
        for row in gate_rows
        if row.get("v0_usability_gate", "").strip() in SUPPORTED_USABLE_GATES
    ]

    all_windows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    aggregate_counters: Counter[str] = Counter()
    fixture_failures: list[str] = []

    for activity_short in fixture_ids:
        gate = gate_by_short.get(activity_short)
        context = context_by_short.get(activity_short)
        if gate is None:
            fixture_failures.append(f"{activity_short}:MISSING_GATE_ROW")
            continue
        if gate.get("v0_usability_gate", "").strip() not in SUPPORTED_USABLE_GATES:
            fixture_failures.append(f"{activity_short}:NOT_USABLE")
            continue
        if context is None:
            fixture_failures.append(f"{activity_short}:MISSING_CONTEXT_ROW")
            continue
        if context.get("legacy_gain_features_blocked", "").strip() != "True":
            fixture_failures.append(f"{activity_short}:LEGACY_GAIN_NOT_BLOCKED")
            continue
        if (
            context.get("route_profile_gain_feature_status", "").strip()
            != "ROUTE_PROFILE_ASCENT_FEATURE_READY_DESCRIPTIVE_CONTRACT_PATCH"
        ):
            fixture_failures.append(
                f"{activity_short}:ROUTE_PROFILE_FEATURE_NOT_READY"
            )
            continue

        activity_full = gate.get("activity_id_full", "").strip()
        path = enriched_path(args.enriched_root, activity_full)
        if not path.exists():
            fixture_failures.append(f"{activity_short}:MISSING_ENRICHED_CSV")
            continue
        windows, counters = collect_activity_windows(
            path, activity_short, activity_full, context
        )
        aggregate_counters.update(counters)
        if not windows:
            fixture_failures.append(f"{activity_short}:NO_OUTPUT_WINDOWS")
            continue
        all_windows.extend(windows)
        summaries.append(
            summarize_activity(activity_short, activity_full, windows)
        )

    missing_route_load_count = sum(
        "ROUTE_PROFILE_CONTEXT_MISSING" in row["window_qa_flags"]
        and "IB2_ROUTE_LOAD_EVIDENCE_MISSING" in row["window_qa_flags"]
        for row in all_windows
    )
    missing_behavior_count = sum(
        "BEHAVIOR_EVIDENCE_MISSING" in row["window_qa_flags"]
        for row in all_windows
    )
    weather_missing_count = sum(
        int(row["weather_missing_numeric_count"]) for row in summaries
    )
    generated_output_fields = set(WINDOW_FIELDS) | set(SUMMARY_FIELDS)
    prohibited_generated = sorted(
        PROHIBITED_GENERATED_FIELDS & generated_output_fields
    )

    pass_checks = (
        len(summaries) == len(fixture_ids)
        and len(all_windows) > 0
        and aggregate_counters["missing_activity_id_count"] == 0
        and aggregate_counters["missing_route_distance_count"] == 0
        and missing_route_load_count == 0
        and missing_behavior_count == 0
        and not fixture_failures
        and not prohibited_generated
    )
    audit = {
        "schema_version": SCHEMA_VERSION,
        "input_activity_count": len(gate_rows),
        "usable_activity_count": len(usable_rows),
        "fixture_activity_count": len(fixture_ids),
        "fixture_activity_ids": "|".join(fixture_ids),
        "fixture_output_activity_count": len(summaries),
        "source_point_row_count": aggregate_counters["source_row_count"],
        "eligible_route_point_row_count": aggregate_counters[
            "eligible_route_row_count"
        ],
        "joined_route_point_row_count": aggregate_counters[
            "joined_route_row_count"
        ],
        "output_window_rows": len(all_windows),
        "output_activity_summary_rows": len(summaries),
        "missing_route_distance_count": aggregate_counters[
            "missing_route_distance_count"
        ],
        "missing_activity_id_count": aggregate_counters[
            "missing_activity_id_count"
        ],
        "missing_route_load_field_count": missing_route_load_count,
        "missing_behavior_field_count": missing_behavior_count,
        "weather_missing_count": weather_missing_count,
        "weather_missing_zero_filled_count": 0,
        "legacy_gain_fields_used_count": 0,
        "legacy_gain_fields_blocked": "|".join(
            sorted(BLOCKED_LEGACY_GAIN_FIELDS)
        ),
        "prohibited_score_rank_class_generated_count": len(
            prohibited_generated
        ),
        "prohibited_generated_fields": "|".join(prohibited_generated),
        "thci_score_generated_count": 0,
        "radar_score_generated_count": 0,
        "final_hiking_risk_score_generated_count": 0,
        "fixture_failure_count": len(fixture_failures),
        "fixture_failures": "|".join(fixture_failures),
        "window_size_m": fmt(WINDOW_SIZE_M),
        "audit_conclusion": PASS_CONCLUSION if pass_checks else FAIL_CONCLUSION,
        "authorization_note": (
            "Descriptive fixture smoke only. No ability score, rank, class, "
            "THCI score, radar score, or final hiking risk score is generated "
            "or authorized."
        ),
    }

    args.out_root.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.out_root / "activity_route_load_behavior_response_windows.csv",
        all_windows,
        WINDOW_FIELDS,
    )
    write_csv(
        args.out_root / "activity_route_load_behavior_response_summary.csv",
        summaries,
        SUMMARY_FIELDS,
    )
    write_csv(
        args.out_root / "activity_route_load_behavior_response_smoke_audit.csv",
        [audit],
        list(audit.keys()),
    )
    render_html(
        args.out_root / "activity_route_load_behavior_response_smoke_report.html",
        fixture_ids,
        summaries,
        all_windows,
        audit,
    )

    print(f"fixture_activity_ids={audit['fixture_activity_ids']}")
    print(f"output_window_rows={audit['output_window_rows']}")
    print(f"output_activity_summary_rows={audit['output_activity_summary_rows']}")
    print(f"legacy_gain_fields_used_count={audit['legacy_gain_fields_used_count']}")
    print(
        "prohibited_score_rank_class_generated_count="
        f"{audit['prohibited_score_rank_class_generated_count']}"
    )
    print(f"audit_conclusion={audit['audit_conclusion']}")
    if not pass_checks:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
