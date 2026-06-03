# -*- coding: utf-8 -*-
from pathlib import Path
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# =========================================================
# ib2e_compute_route_challenge_index.py
#
# Build a route-level THCI v0 summary from the ib1e point profile.
# This is a baseline route challenge index, not a live weather risk
# or personal suitability model.
# =========================================================


CASE_ID = os.environ.get("CASE_ID", "juansi_waterfall_fitcsv_20260503")

NEW_INPUT_DIR = Path("outputs") / "ib1e_route_profile_contour_window_terrain" / CASE_ID
NEW_INPUT_PROFILE_CSV = (
    NEW_INPUT_DIR / f"{CASE_ID}_route_profile_contour_window_terrain_enriched.csv"
)
LEGACY_INPUT_DIR = Path("outputs") / "ib1e_osm_nlsc_terrain_risk" / CASE_ID
LEGACY_INPUT_PROFILE_CSV = LEGACY_INPUT_DIR / f"{CASE_ID}_osm_nlsc_terrain_risk_profile.csv"

INPUT_DIR = NEW_INPUT_DIR if NEW_INPUT_PROFILE_CSV.exists() else LEGACY_INPUT_DIR
INPUT_PROFILE_CSV = (
    NEW_INPUT_PROFILE_CSV
    if NEW_INPUT_PROFILE_CSV.exists()
    else LEGACY_INPUT_PROFILE_CSV
)

OUT_DIR = Path("outputs") / "ib2e_route_challenge_index" / CASE_ID
OUT_PROFILE_CSV = OUT_DIR / f"{CASE_ID}_route_challenge_index_profile.csv"
OUT_SUMMARY_CSV = OUT_DIR / f"{CASE_ID}_route_challenge_index_summary.csv"
OUT_RADAR_PNG = OUT_DIR / f"{CASE_ID}_route_challenge_radar.png"

MODEL_VERSION = "thci_v0_from_ib1e_profile"

AXIS_WEIGHTS = {
    "physical_difficulty_score": 0.35,
    "technical_difficulty_score": 0.20,
    "baseline_hazard_score": 0.20,
    "navigation_risk_score": 0.10,
    "support_deficit_score": 0.10,
    "weather_sensitivity_score": 0.05,
}

CHALLENGE_BANDS = [
    (20.0, "easy"),
    (40.0, "moderate"),
    (60.0, "challenging"),
    (80.0, "hard"),
    (101.0, "extreme"),
]


mpl.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "Noto Sans CJK TC",
    "Microsoft JhengHei",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False


def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"missing required input: {fp.resolve()}")


def clamp(value, lo=0.0, hi=100.0):
    if pd.isna(value):
        return np.nan
    return max(lo, min(hi, float(value)))


def scale_0_1_to_100(series):
    return pd.to_numeric(series, errors="coerce").clip(0.0, 1.0) * 100.0


def linear_score(series, low_ref, high_ref):
    values = pd.to_numeric(series, errors="coerce")
    if high_ref == low_ref:
        return pd.Series(np.nan, index=values.index)
    return ((values - low_ref) / (high_ref - low_ref) * 100.0).clip(0.0, 100.0)


def bool_score(df, col):
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0).clip(0.0, 1.0) * 100.0


def numeric_col(df, col, default=0.0):
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def optional_score_0_1(df, col):
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return scale_0_1_to_100(df[col]).fillna(0.0)


def weighted_row_score(parts, weights):
    total = pd.Series(0.0, index=parts[0].index)
    total_weight = 0.0
    for part, weight in zip(parts, weights):
        total = total + part.fillna(0.0) * weight
        total_weight += weight
    if total_weight <= 0:
        return pd.Series(np.nan, index=parts[0].index)
    return (total / total_weight).clip(0.0, 100.0)


def weighted_mean(series, weights):
    values = pd.to_numeric(series, errors="coerce")
    w = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    mask = values.notna() & (w > 0)
    if mask.sum() == 0:
        return np.nan
    return float((values[mask] * w[mask]).sum() / w[mask].sum())


def linear_value_score(value, low_ref, high_ref):
    if pd.isna(value) or high_ref == low_ref:
        return np.nan
    return clamp((float(value) - low_ref) / (high_ref - low_ref) * 100.0)


def pct_true(df, col):
    if col not in df.columns or len(df) == 0:
        return np.nan
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).clip(0, 1).mean())


def challenge_band(score):
    if pd.isna(score):
        return "unknown"
    for upper, band in CHALLENGE_BANDS:
        if score < upper:
            return band
    return "extreme"


def compute_profile_scores(df):
    slope_abs = numeric_col(df, "slope_pct").abs()
    slope_score = linear_score(slope_abs, 0.0, 25.0)
    gain_score = linear_score(numeric_col(df, "gain_m"), 0.0, 0.25)
    terrain_score = optional_score_0_1(df, "terrain_window_risk_score")
    effort_score = optional_score_0_1(df, "route_effort_risk_score")

    physical = weighted_row_score(
        [terrain_score, slope_score, gain_score, effort_score],
        [0.45, 0.25, 0.20, 0.10],
    )

    technical = weighted_row_score(
        [
            optional_score_0_1(df, "technical_risk_score"),
            bool_score(df, "near_safety_rope"),
            bool_score(df, "near_handrail") * 0.45,
            bool_score(df, "near_ladder"),
            bool_score(df, "near_rungs"),
            bool_score(df, "near_via_ferrata"),
            bool_score(df, "osm_is_steps") * 0.65,
            slope_score * 0.35,
        ],
        [0.25, 0.15, 0.08, 0.12, 0.12, 0.12, 0.08, 0.08],
    )

    hydro_score = optional_score_0_1(df, "hydrology_risk_score")
    hydro_terrain_score = optional_score_0_1(df, "hydro_terrain_amplifier_score")
    exposure_score = optional_score_0_1(df, "exposure_risk_score")
    slip_score = optional_score_0_1(df, "surface_slip_risk_score")

    baseline_hazard = weighted_row_score(
        [
            exposure_score,
            hydro_score,
            hydro_terrain_score,
            slip_score,
            bool_score(df, "near_cliff"),
            bool_score(df, "near_scree"),
            bool_score(df, "near_bare_rock") * 0.70,
            bool_score(df, "near_landslide"),
            terrain_score * 0.45,
        ],
        [0.14, 0.18, 0.22, 0.12, 0.12, 0.08, 0.05, 0.06, 0.03],
    )

    navigation = weighted_row_score(
        [
            optional_score_0_1(df, "navigation_risk_score"),
            optional_score_0_1(df, "night_navigation_risk_score") * 0.55,
            optional_score_0_1(df, "route_continuity_context_score"),
            (100.0 - bool_score(df, "near_guidepost")) * 0.35,
        ],
        [0.45, 0.20, 0.20, 0.15],
    )

    support_presence = weighted_row_score(
        [
            bool_score(df, "near_trailhead"),
            bool_score(df, "near_shelter"),
            bool_score(df, "near_alpine_hut"),
            bool_score(df, "near_wilderness_hut"),
            bool_score(df, "near_bench") * 0.60,
            bool_score(df, "near_picnic_table") * 0.50,
            bool_score(df, "near_picnic_site") * 0.50,
            bool_score(df, "near_drinking_water"),
            bool_score(df, "near_toilets") * 0.85,
            bool_score(df, "near_information_office"),
        ],
        [0.10, 0.14, 0.14, 0.14, 0.07, 0.05, 0.05, 0.12, 0.10, 0.09],
    )
    support_deficit = (100.0 - support_presence).clip(0.0, 100.0)

    weather_sensitive_flags = (
        df.get("weather_sensitive_flags", pd.Series("", index=df.index))
        .astype(str)
        .str.strip()
    )
    has_weather_sensitive_flag = (~weather_sensitive_flags.isin(["", "normal", "none", "nan", "<NA>"])).astype(float) * 100.0

    weather_sensitivity = weighted_row_score(
        [
            has_weather_sensitive_flag,
            hydro_terrain_score,
            slip_score,
            bool_score(df, "near_waterway"),
            bool_score(df, "near_wetland"),
            bool_score(df, "near_water_area") * 0.70,
            terrain_score * 0.45,
        ],
        [0.22, 0.26, 0.18, 0.14, 0.08, 0.06, 0.06],
    )

    out = df.copy()
    out["physical_difficulty_score"] = physical
    out["technical_difficulty_score"] = technical
    out["baseline_hazard_score"] = baseline_hazard
    out["navigation_risk_score_thci"] = navigation
    out["support_deficit_score"] = support_deficit
    out["weather_sensitivity_score"] = weather_sensitivity
    out["route_challenge_point_score"] = (
        out["physical_difficulty_score"] * AXIS_WEIGHTS["physical_difficulty_score"]
        + out["technical_difficulty_score"] * AXIS_WEIGHTS["technical_difficulty_score"]
        + out["baseline_hazard_score"] * AXIS_WEIGHTS["baseline_hazard_score"]
        + out["navigation_risk_score_thci"] * AXIS_WEIGHTS["navigation_risk_score"]
        + out["support_deficit_score"] * AXIS_WEIGHTS["support_deficit_score"]
        + out["weather_sensitivity_score"] * AXIS_WEIGHTS["weather_sensitivity_score"]
    )
    out["route_challenge_point_band"] = out["route_challenge_point_score"].apply(challenge_band)
    return out


def build_summary(profile):
    weights = numeric_col(profile, "delta_dist_m", default=1.0).abs()
    weights = weights.mask(weights <= 0, 1.0)

    distance_m = float(numeric_col(profile, "dist_m").max())
    elevation_gain_m = float(numeric_col(profile, "gain_m").sum())
    elevation_loss_m = float(numeric_col(profile, "loss_m").sum())

    point_support_deficit_mean = weighted_mean(profile["support_deficit_score"], weights)
    near_support_facility_ratio = float(
        profile[
            [
                c
                for c in [
                    "near_shelter",
                    "near_alpine_hut",
                    "near_wilderness_hut",
                    "near_bench",
                    "near_picnic_table",
                    "near_picnic_site",
                    "near_drinking_water",
                    "near_toilets",
                    "near_information_office",
                ]
                if c in profile.columns
            ]
        ]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .clip(0.0, 1.0)
        .max(axis=1)
        .mean()
    )
    near_drinking_water_ratio = pct_true(profile, "near_drinking_water")
    near_shelter_like_ratio = float(
        profile[
            [
                c
                for c in [
                    "near_shelter",
                    "near_alpine_hut",
                    "near_wilderness_hut",
                ]
                if c in profile.columns
            ]
        ]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .clip(0.0, 1.0)
        .max(axis=1)
        .mean()
    )
    distance_deficit = linear_value_score(distance_m / 1000.0, 2.0, 15.0)
    distance_factor = linear_value_score(distance_m / 1000.0, 2.0, 15.0) / 100.0
    facility_gap_deficit = 100.0 - near_support_facility_ratio * 100.0
    water_gap_deficit = 100.0 - near_drinking_water_ratio * 100.0
    shelter_gap_deficit = 100.0 - near_shelter_like_ratio * 100.0
    route_support_deficit = clamp(
        facility_gap_deficit * 0.35
        + distance_deficit * 0.30
        + water_gap_deficit * 0.15
        + shelter_gap_deficit * distance_factor * 0.20
    )

    axis_scores = {
        "physical_difficulty_score": weighted_mean(profile["physical_difficulty_score"], weights),
        "technical_difficulty_score": weighted_mean(profile["technical_difficulty_score"], weights),
        "baseline_hazard_score": weighted_mean(profile["baseline_hazard_score"], weights),
        "navigation_risk_score": weighted_mean(profile["navigation_risk_score_thci"], weights),
        "support_deficit_score": route_support_deficit,
        "weather_sensitivity_score": weighted_mean(profile["weather_sensitivity_score"], weights),
    }

    route_challenge_index = sum(axis_scores[k] * AXIS_WEIGHTS[k] for k in AXIS_WEIGHTS)

    summary = {
        "case_id": CASE_ID,
        "model_version": MODEL_VERSION,
        "route_challenge_index": clamp(route_challenge_index),
        "route_challenge_band": challenge_band(route_challenge_index),
        **axis_scores,
        "distance_km": distance_m / 1000.0,
        "elevation_gain_m": elevation_gain_m,
        "elevation_loss_m": elevation_loss_m,
        "avg_abs_slope_pct": float(numeric_col(profile, "slope_pct").abs().mean()),
        "max_abs_slope_pct": float(numeric_col(profile, "slope_pct").abs().max()),
        "near_waterway_ratio": pct_true(profile, "near_waterway"),
        "near_wetland_ratio": pct_true(profile, "near_wetland"),
        "near_cliff_ratio": pct_true(profile, "near_cliff"),
        "near_scree_ratio": pct_true(profile, "near_scree"),
        "near_bare_rock_ratio": pct_true(profile, "near_bare_rock"),
        "near_guidepost_ratio": pct_true(profile, "near_guidepost"),
        "near_support_facility_ratio": near_support_facility_ratio,
        "near_drinking_water_ratio": near_drinking_water_ratio,
        "near_shelter_like_ratio": near_shelter_like_ratio,
        "point_support_deficit_score_mean": point_support_deficit_mean,
        "route_length_support_deficit_component": distance_deficit,
        "osm_terrain_combined_risk_score_mean": float(
            numeric_col(profile, "osm_terrain_combined_risk_score").mean()
        ),
        "terrain_window_risk_score_mean": float(numeric_col(profile, "terrain_window_risk_score").mean()),
        "hydro_terrain_amplifier_score_mean": float(
            numeric_col(profile, "hydro_terrain_amplifier_score").mean()
        ),
        "thci_weight_physical": AXIS_WEIGHTS["physical_difficulty_score"],
        "thci_weight_technical": AXIS_WEIGHTS["technical_difficulty_score"],
        "thci_weight_baseline_hazard": AXIS_WEIGHTS["baseline_hazard_score"],
        "thci_weight_navigation": AXIS_WEIGHTS["navigation_risk_score"],
        "thci_weight_support_deficit": AXIS_WEIGHTS["support_deficit_score"],
        "thci_weight_weather_sensitivity": AXIS_WEIGHTS["weather_sensitivity_score"],
        "note": "THCI is a baseline route challenge score under good hiking conditions; live weather and personal suitability are separate layers.",
    }
    return summary


def plot_radar(summary):
    labels = [
        ("體力難度", "Physical"),
        ("技術難度", "Technical"),
        ("基礎危害", "Hazard"),
        ("導航風險", "Navigation"),
        ("支援不足", "Support deficit"),
        ("天候敏感度", "Weather sensitivity"),
    ]
    values = [
        summary["physical_difficulty_score"],
        summary["technical_difficulty_score"],
        summary["baseline_hazard_score"],
        summary["navigation_risk_score"],
        summary["support_deficit_score"],
        summary["weather_sensitivity_score"],
    ]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    # Start at the top and move clockwise.
    angles = np.pi / 2 - angles

    fig, ax = plt.subplots(figsize=(8.5, 8.5), dpi=180)
    ax.set_aspect("equal")
    ax.axis("off")

    grid_color = "#B8C3C7"
    axis_color = "#8FA2A8"
    main_color = "#2F6F73"

    # Hexagonal grid rings.
    for ring in [20, 40, 60, 80, 100]:
        radius = ring / 100.0
        xs = np.cos(angles) * radius
        ys = np.sin(angles) * radius
        xs = np.r_[xs, xs[0]]
        ys = np.r_[ys, ys[0]]
        ax.plot(xs, ys, color=grid_color, linewidth=0.8)
        ax.text(
            0.03,
            radius,
            str(ring),
            fontsize=8,
            color="#54666B",
            ha="left",
            va="bottom",
        )

    # Axis spokes and labels.
    for angle, (zh_label, en_label), value in zip(angles, labels, values):
        ax.plot([0, np.cos(angle)], [0, np.sin(angle)], color=axis_color, linewidth=0.8)
        lx = np.cos(angle) * 1.16
        ly = np.sin(angle) * 1.16
        ha = "center"
        if lx > 0.2:
            ha = "left"
        elif lx < -0.2:
            ha = "right"
        ax.text(
            lx,
            ly,
            f"{zh_label}\n{en_label}\n{value:.1f}",
            fontsize=10,
            color="#1F2D31",
            ha=ha,
            va="center",
            linespacing=1.25,
        )

    radii = np.array(values, dtype=float) / 100.0
    xs = np.cos(angles) * radii
    ys = np.sin(angles) * radii
    xs = np.r_[xs, xs[0]]
    ys = np.r_[ys, ys[0]]
    ax.fill(xs, ys, color=main_color, alpha=0.23)
    ax.plot(xs, ys, color=main_color, linewidth=2.8)
    ax.scatter(xs[:-1], ys[:-1], s=22, color=main_color, zorder=3)

    title = (
        f"{CASE_ID}\n"
        f"全台登山挑戰指數 THCI: {summary['route_challenge_index']:.1f} / 100 "
        f"({summary['route_challenge_band']})"
    )
    ax.text(0, 1.38, title, ha="center", va="center", fontsize=13, linespacing=1.35)
    ax.text(
        0,
        -1.34,
        "六軸分數為 0-100 標準化子指標；THCI 表示良好登山條件下的路線基準挑戰度，"
        "不等同今日天候風險或個人適配度。",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#46585D",
        wrap=True,
    )

    ax.set_xlim(-1.42, 1.42)
    ax.set_ylim(-1.42, 1.48)
    fig.tight_layout()
    fig.savefig(OUT_RADAR_PNG, bbox_inches="tight")
    plt.close(fig)


def main():
    ensure_exists(INPUT_PROFILE_CSV)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_PROFILE_CSV)
    profile = compute_profile_scores(df)
    summary = build_summary(profile)

    keep_cols = [
        c
        for c in [
            "sample_idx",
            "dist_m",
            "lat",
            "lon",
            "ele_gpx_m",
            "delta_dist_m",
            "delta_ele_m",
            "slope_pct",
            "slope_band",
            "gain_m",
            "loss_m",
            "cum_gain_m",
            "cum_loss_m",
            "terrain_slope_band_window",
            "terrain_window_risk_score",
            "hydro_terrain_amplifier_score",
            "osm_semantic_risk_score",
            "osm_terrain_combined_risk_score",
            "osm_terrain_combined_risk_band",
            "physical_difficulty_score",
            "technical_difficulty_score",
            "baseline_hazard_score",
            "navigation_risk_score_thci",
            "support_deficit_score",
            "weather_sensitivity_score",
            "route_challenge_point_score",
            "route_challenge_point_band",
        ]
        if c in profile.columns
    ]

    profile[keep_cols].to_csv(OUT_PROFILE_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    plot_radar(summary)

    print(f"case_id: {CASE_ID}")
    print(f"model_version: {MODEL_VERSION}")
    print(f"route_challenge_index: {summary['route_challenge_index']:.2f}")
    print(f"route_challenge_band: {summary['route_challenge_band']}")
    print(f"wrote: {OUT_PROFILE_CSV}")
    print(f"wrote: {OUT_SUMMARY_CSV}")
    print(f"wrote: {OUT_RADAR_PNG}")


if __name__ == "__main__":
    main()
