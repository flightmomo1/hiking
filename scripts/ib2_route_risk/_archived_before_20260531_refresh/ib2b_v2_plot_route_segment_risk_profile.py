# -*- coding: utf-8 -*-
from pathlib import Path
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = os.environ.get("CASE_ID", "qixing_xiaoyoukeng_main_peak_20260315")
CASE_NAME = os.environ.get("CASE_NAME", CASE_ID)
SEGMENT_SIZE_M = int(float(os.environ.get("SEGMENT_SIZE_M", "100")))

mpl.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False

INPUT_CSV = (
    PROJECT_ROOT
    / "outputs"
    / "ib2_v3_route_segment_risk"
    / CASE_ID
    / f"{CASE_ID}_route_segment_risk_{SEGMENT_SIZE_M}m.csv"
)
OUT_DIR = PROJECT_ROOT / "outputs" / "ib2b_v2_segment_risk_profile" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PNG = OUT_DIR / f"{CASE_ID}_route_segment_risk_profile_report.png"
OUT_CSV = OUT_DIR / f"{CASE_ID}_route_segment_risk_profile_report_data.csv"

RISK_COLOR = {
    "low": "#4CAF50",
    "moderate": "#F2C037",
    "high": "#F57C00",
    "very_high": "#D93A3A",
    "unknown": "#9E9E9E",
}


def find_band_runs(df, target):
    runs = []
    start = None
    for i, value in enumerate(df["segment_risk_band"].astype(str)):
        if value == target and start is None:
            start = i
        if value != target and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(df) - 1))
    return runs


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(INPUT_CSV)
    df = pd.read_csv(INPUT_CSV, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        raise ValueError(f"Empty input: {INPUT_CSV}")
    for col in [
        "segment_start_m",
        "segment_end_m",
        "segment_mid_m",
        "segment_risk_score",
        "segment_risk_band",
    ]:
        if col not in df.columns:
            raise KeyError(f"missing required column: {col}")

    df = df.sort_values("segment_start_m").reset_index(drop=True)
    df = df[df.get("segment_valid", True).astype(bool)].copy()
    if df.empty:
        raise ValueError("No valid segments to plot")

    for col in ["segment_risk_score_mean", "effort_score_mean", "exposure_score_mean"]:
        if col not in df.columns:
            df[col] = df["segment_risk_score"] if col == "segment_risk_score_mean" else 0.0

    bar_width = (df["segment_end_m"] - df["segment_start_m"]).median() * 0.86
    colors = [RISK_COLOR.get(str(v), RISK_COLOR["unknown"]) for v in df["segment_risk_band"]]

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(15, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3.2, 1.2]},
    )

    ax1.bar(
        df["segment_mid_m"],
        df["segment_risk_score"],
        width=bar_width,
        color=colors,
        alpha=0.58,
        label="segment risk max",
    )
    ax1.plot(df["segment_mid_m"], df["segment_risk_score_mean"], color="black", lw=2, label="risk mean")
    ax1.plot(df["segment_mid_m"], df["effort_score_mean"], ls="--", lw=1.5, label="effort mean")
    ax1.plot(df["segment_mid_m"], df["exposure_score_mean"], ls=":", lw=1.5, label="exposure mean")
    ax1.set_ylabel("Score (0-1)")
    ax1.set_ylim(0, max(1.0, float(df["segment_risk_score"].max()) * 1.18))
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper right", ncol=4, fontsize=9)

    for start_i, end_i in find_band_runs(df, "very_high"):
        start_m = df.iloc[start_i]["segment_start_m"]
        end_m = df.iloc[end_i]["segment_end_m"]
        ax1.axvspan(start_m, end_m, color=RISK_COLOR["very_high"], alpha=0.10)
        ax1.text(
            (start_m + end_m) / 2,
            ax1.get_ylim()[1] * 0.95,
            f"{int(start_m)}-{int(end_m)} m\nvery_high",
            ha="center",
            va="top",
            fontsize=8,
            color="#8B0000",
        )

    if "route_data_bad_ratio" not in df.columns:
        df["route_data_bad_ratio"] = 0.0
    if "low_confidence_ratio" not in df.columns:
        df["low_confidence_ratio"] = 0.0

    ax2.bar(
        df["segment_mid_m"],
        df["route_data_bad_ratio"],
        width=bar_width,
        color="#78909C",
        alpha=0.65,
        label="route_data_bad_ratio",
    )
    ax2.plot(
        df["segment_mid_m"],
        df["low_confidence_ratio"],
        color="#5D4037",
        lw=1.6,
        label="low_confidence_ratio",
    )
    ax2.set_ylabel("Data quality")
    ax2.set_xlabel("Distance (m)")
    ax2.set_ylim(0, 1)
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper right", fontsize=9)

    fig.suptitle(f"{CASE_NAME}\n{SEGMENT_SIZE_M}m segment risk profile", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT_PNG, dpi=180)
    plt.close(fig)

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print("case:", CASE_ID)
    print("PNG:", OUT_PNG)
    print("CSV:", OUT_CSV)
    print(df["segment_risk_band"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
