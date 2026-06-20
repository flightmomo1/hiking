from __future__ import annotations

import html
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT_DATA_TABLE = (
    ROOT
    / "outputs"
    / "report_figures"
    / "ch6_5_5_route_following_data_table_patch_v1"
    / "personal_ability_radar_data_table_v1_1.csv"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs"
    / "report_figures"
    / "ch6_5_5_personal_ability_radar_plot_v1_1"
)
PLOT_ROOT = OUTPUT_ROOT / "plots"

READY_TABLE = OUTPUT_ROOT / "personal_ability_radar_plot_ready_table_v1_1.csv"
PLOT_INDEX = OUTPUT_ROOT / "personal_ability_radar_plot_index_v1_1.csv"
ANNOTATION_SUMMARY = OUTPUT_ROOT / "personal_ability_radar_annotation_summary_v1_1.csv"
AUDIT = OUTPUT_ROOT / "personal_ability_radar_plot_audit_v1_1.csv"
REPORT = OUTPUT_ROOT / "personal_ability_radar_plot_report_v1_1.html"

BASELINE_STATUS = "RADAR_BASELINE_ACTIVITY"
EXTRA_SOURCE_STATUS = "EXTRA_SOURCE_ACTIVITY_NOT_IN_RADAR_BASELINE"
LIMITED_PROXY_MODE = "LIMITED_PROXY_AXIS"
DESCRIPTIVE_MODE = "DESCRIPTIVE_ANNOTATION"
MISSING_MODE = "MISSING_EVIDENCE_ANNOTATION"
PASS_CONCLUSION = (
    "PASS_CH6_5_5_PERSONAL_ABILITY_RADAR_PLOT_V1_1_"
    "GOVERNED_LIMITED_PROXY_PREVIEW"
)

EXPECTED_LIMITED_AXES = [
    "terrain_movement_efficiency",
    "pacing_movement_stability",
    "route_following_stability",
]

SHORT_LABELS = {
    "terrain_movement_efficiency": "terrain",
    "pacing_movement_stability": "pacing",
    "route_following_stability": "route follow",
}

INTERPRETATION_BOUNDARY = (
    "CH6.5.5 personal ability radar plot v1_1 is a governed limited proxy "
    "preview only. It plots only admitted limited proxy axes from data table "
    "v1_1. It is not an ability score, ability rank, ability class, THCI "
    "score, final hiking risk score, route suitability score, go/no-go "
    "decision, medical diagnosis, or causality claim."
)


def truthy(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def nonblank(value: object) -> bool:
    return not pd.isna(value) and str(value).strip() != ""


def sort_activity_id(activity_id: object) -> tuple[int, int, str]:
    text = str(activity_id)
    head = text.split("_", 1)[0]
    try:
        return (0, int(head), text)
    except ValueError:
        return (1, 0, text)


def load_data() -> pd.DataFrame:
    if not INPUT_DATA_TABLE.exists():
        raise FileNotFoundError(f"Missing input data table: {INPUT_DATA_TABLE}")
    df = pd.read_csv(INPUT_DATA_TABLE)
    required_columns = {
        "participant_id",
        "activity_id_short",
        "study_population_status",
        "axis_id",
        "axis_label_zh",
        "axis_output_mode",
        "axis_value_allowed",
        "axis_value",
        "axis_annotation",
        "required_gate_status",
        "fallback_status",
        "missing_evidence_reason",
        "allowed_use",
        "disallowed_use",
        "interpretation_boundary",
    }
    missing = sorted(required_columns.difference(df.columns))
    if missing:
        raise ValueError(f"Input data table missing required columns: {missing}")
    return df


def build_ready_table(df: pd.DataFrame) -> pd.DataFrame:
    ready = df.copy()
    ready["axis_value_numeric"] = pd.to_numeric(ready["axis_value"], errors="coerce")
    ready["axis_value_allowed_bool"] = ready["axis_value_allowed"].map(truthy)
    ready["baseline_population_pass"] = (
        ready["study_population_status"].astype(str) == BASELINE_STATUS
    )
    ready["limited_proxy_axis"] = (
        ready["axis_output_mode"].astype(str) == LIMITED_PROXY_MODE
    )
    ready["plot_candidate"] = (
        ready["baseline_population_pass"]
        & ready["limited_proxy_axis"]
        & ready["axis_value_allowed_bool"]
        & ready["axis_value_numeric"].notna()
    )
    ready["plot_allowed"] = ready["plot_candidate"]
    ready["plot_value"] = ready["axis_value_numeric"].where(ready["plot_candidate"])
    ready["plot_scale"] = "ZERO_TO_100_LIMITED_PROXY"
    ready["plot_scale_note"] = (
        "Only governed limited proxy values already expressed on a 0-100 "
        "preview scale are plotted. Missing or blocked values are not filled."
    )
    ready["plot_label"] = ready.apply(
        lambda row: build_plot_label(row["axis_id"], row["axis_label_zh"]), axis=1
    )
    ready["plot_permission_note"] = ready.apply(plot_permission_note, axis=1)
    ready["plot_interpretation_boundary"] = INTERPRETATION_BOUNDARY
    return ready


def build_plot_label(axis_id: object, axis_label_zh: object) -> str:
    axis_id_text = str(axis_id)
    short = SHORT_LABELS.get(axis_id_text, axis_id_text.replace("_", " "))
    zh = "" if pd.isna(axis_label_zh) else str(axis_label_zh).strip()
    if zh:
        return f"{zh}\n({short})"
    return short


def plot_permission_note(row: pd.Series) -> str:
    if row["plot_candidate"]:
        return "PLOTTED_GOVERNED_LIMITED_PROXY_PREVIEW"
    if row["study_population_status"] != BASELINE_STATUS:
        return "NOT_PLOTTED_EXTRA_SOURCE_ACTIVITY"
    if row["axis_output_mode"] == LIMITED_PROXY_MODE:
        return "NOT_PLOTTED_LIMITED_PROXY_BLOCKED_OR_MISSING_VALUE"
    if row["axis_output_mode"] == DESCRIPTIVE_MODE:
        return "NOT_PLOTTED_DESCRIPTIVE_ANNOTATION_ONLY"
    if row["axis_output_mode"] == MISSING_MODE:
        return "NOT_PLOTTED_MISSING_EVIDENCE_ANNOTATION"
    return "NOT_PLOTTED_NOT_LIMITED_PROXY_AXIS"


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def make_radar_plot(activity_id: str, plot_rows: pd.DataFrame, plot_path: Path) -> None:
    rows = plot_rows.sort_values(
        "axis_id",
        key=lambda values: values.map(
            {axis: index for index, axis in enumerate(EXPECTED_LIMITED_AXES)}
        ),
    )
    labels = rows["plot_label"].tolist()
    values = rows["plot_value"].astype(float).clip(lower=0, upper=100).tolist()
    closed_values = values + values[:1]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    closed_angles = angles + angles[:1]

    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "Noto Sans CJK TC",
        "Noto Sans CJK JP",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(7.2, 7.2), dpi=150)
    ax = fig.add_subplot(111, polar=True)
    fig.patch.set_facecolor("#f7f8f4")
    ax.set_facecolor("#ffffff")

    ax.plot(closed_angles, closed_values, color="#246a73", linewidth=2.4)
    ax.fill(closed_angles, closed_values, color="#58a4b0", alpha=0.22)
    ax.scatter(angles, values, color="#164f58", s=34, zorder=5)

    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="#5b6467")
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=9, color="#1f2d2f")
    ax.grid(color="#d7ded9", linewidth=0.9)
    ax.spines["polar"].set_color("#b5c1bc")

    for angle, value in zip(angles, values):
        ax.text(
            angle,
            min(108, value + 8),
            f"{value:.1f}",
            ha="center",
            va="center",
            fontsize=8,
            color="#164f58",
        )

    ax.set_title(
        f"Activity {activity_id}\nGoverned limited proxy preview\n"
        "Not an ability score / rank / class",
        va="bottom",
        fontsize=12,
        color="#172326",
        pad=30,
    )
    fig.text(
        0.5,
        0.035,
        "Only admitted limited proxy axes are plotted. Missing or blocked axes are not filled with zero.",
        ha="center",
        va="bottom",
        fontsize=8,
        color="#455154",
    )
    fig.tight_layout(rect=[0.03, 0.08, 0.97, 0.94])
    fig.savefig(plot_path, bbox_inches="tight")
    plt.close(fig)


def build_plot_index_and_images(ready: pd.DataFrame) -> tuple[pd.DataFrame, list[Path]]:
    PLOT_ROOT.mkdir(parents=True, exist_ok=True)
    for old_plot in PLOT_ROOT.glob("personal_ability_radar_preview_*_v1_1.png"):
        old_plot.unlink()

    index_rows: list[dict[str, object]] = []
    generated: list[Path] = []
    grouped = ready.groupby("activity_id_short", sort=False)
    for activity_id in sorted(grouped.groups, key=sort_activity_id):
        activity_rows = grouped.get_group(activity_id)
        participant_id = activity_rows["participant_id"].iloc[0]
        status = activity_rows["study_population_status"].iloc[0]
        allowed_proxy_rows = activity_rows[activity_rows["plot_candidate"]].copy()
        allowed_proxy_axis_count = int(allowed_proxy_rows["axis_id"].nunique())
        descriptive_count = int(
            (activity_rows["axis_output_mode"] == DESCRIPTIVE_MODE).sum()
        )
        missing_count = int((activity_rows["axis_output_mode"] == MISSING_MODE).sum())
        blocked_limited_count = int(
            (
                (activity_rows["axis_output_mode"] == LIMITED_PROXY_MODE)
                & (~activity_rows["plot_candidate"])
            ).sum()
        )

        plot_created = False
        plot_path_text = ""
        if status != BASELINE_STATUS:
            plot_reason = "BLOCKED_EXTRA_SOURCE_ACTIVITY_NOT_IN_RADAR_BASELINE"
        elif allowed_proxy_axis_count < len(EXPECTED_LIMITED_AXES):
            plot_reason = "SKIPPED_FEWER_THAN_3_GOVERNED_LIMITED_PROXY_AXES"
        else:
            plot_path = (
                PLOT_ROOT
                / f"personal_ability_radar_preview_{activity_id}_v1_1.png"
            )
            make_radar_plot(str(activity_id), allowed_proxy_rows, plot_path)
            generated.append(plot_path)
            plot_created = True
            plot_path_text = relative_path(plot_path)
            plot_reason = "PLOTTED_GOVERNED_LIMITED_PROXY_PREVIEW"

        index_rows.append(
            {
                "participant_id": participant_id,
                "activity_id_short": activity_id,
                "study_population_status": status,
                "plot_created": plot_created,
                "plot_path": plot_path_text,
                "plot_reason": plot_reason,
                "plotted_axis_count": allowed_proxy_axis_count if plot_created else 0,
                "allowed_proxy_axis_count": allowed_proxy_axis_count,
                "blocked_limited_proxy_axis_count": blocked_limited_count,
                "descriptive_annotation_count": descriptive_count,
                "missing_evidence_annotation_count": missing_count,
                "interpretation_boundary": INTERPRETATION_BOUNDARY,
            }
        )
    return pd.DataFrame(index_rows), generated


def build_annotation_summary(ready: pd.DataFrame) -> pd.DataFrame:
    annotation = ready[
        (~ready["plot_candidate"])
        & (
            ready["axis_output_mode"].isin([DESCRIPTIVE_MODE, MISSING_MODE])
            | (ready["axis_output_mode"].eq(LIMITED_PROXY_MODE))
        )
    ].copy()
    columns = [
        "participant_id",
        "activity_id_short",
        "study_population_status",
        "axis_id",
        "axis_label_zh",
        "axis_output_mode",
        "radar_output_permission",
        "axis_annotation",
        "missing_evidence_reason",
        "required_gate_status",
        "fallback_status",
        "plot_permission_note",
        "allowed_use",
        "disallowed_use",
        "interpretation_boundary",
    ]
    return annotation[columns]


def forbidden_columns(frames: dict[str, pd.DataFrame]) -> list[str]:
    patterns = [
        "ability_score",
        "ability_rank",
        "ability_class",
        "thci_score",
        "final_hiking_risk_score",
        "route_suitability_score",
        "go_no_go",
        "medical_diagnosis",
        "causality_claim",
    ]
    found: list[str] = []
    for name, frame in frames.items():
        for column in frame.columns:
            lowered = str(column).lower()
            if any(pattern in lowered for pattern in patterns):
                found.append(f"{name}:{column}")
    return found


def build_audit(
    df: pd.DataFrame,
    ready: pd.DataFrame,
    plot_index: pd.DataFrame,
    annotation: pd.DataFrame,
    generated_plots: list[Path],
) -> pd.DataFrame:
    baseline_activities = ready[ready["study_population_status"] == BASELINE_STATUS][
        "activity_id_short"
    ].nunique()
    extra_source_activities = ready[
        ready["study_population_status"] != BASELINE_STATUS
    ]["activity_id_short"].nunique()
    plotted_baseline = plot_index[
        (plot_index["study_population_status"] == BASELINE_STATUS)
        & (plot_index["plot_created"])
    ]
    plotted_extra = plot_index[
        (plot_index["study_population_status"] != BASELINE_STATUS)
        & (plot_index["plot_created"])
    ]
    plotted_axis_counts = plotted_baseline["plotted_axis_count"]
    limited_axes = sorted(
        ready.loc[ready["axis_output_mode"] == LIMITED_PROXY_MODE, "axis_id"].unique()
    )
    limited_proxy_axis_count = len(limited_axes)
    descriptive_not_plotted = not ready.loc[
        ready["axis_output_mode"] == DESCRIPTIVE_MODE, "plot_candidate"
    ].any()
    missing_not_plotted = not ready.loc[
        ready["axis_output_mode"] == MISSING_MODE, "plot_candidate"
    ].any()
    zero_fill_used = bool(
        ready.loc[
            ready["plot_candidate"]
            & ready["axis_value"].fillna("").astype(str).str.strip().eq(""),
            "axis_id",
        ].any()
    )
    forbidden = forbidden_columns(
        {"ready": ready, "plot_index": plot_index, "annotation": annotation}
    )

    checks = {
        "input_data_table_row_count": int(len(df)),
        "activity_count": int(ready["activity_id_short"].nunique()),
        "baseline_activity_count": int(baseline_activities),
        "extra_source_activity_count": int(extra_source_activities),
        "plotted_baseline_activity_count": int(len(plotted_baseline)),
        "plotted_extra_source_activity_count": int(len(plotted_extra)),
        "limited_proxy_axis_count": int(limited_proxy_axis_count),
        "plotted_axis_count_per_baseline_activity_min": int(
            plotted_axis_counts.min() if not plotted_axis_counts.empty else 0
        ),
        "plotted_axis_count_per_baseline_activity_max": int(
            plotted_axis_counts.max() if not plotted_axis_counts.empty else 0
        ),
        "descriptive_annotation_not_plotted": bool(descriptive_not_plotted),
        "missing_evidence_annotation_not_plotted": bool(missing_not_plotted),
        "zero_fill_used": bool(zero_fill_used),
        "forbidden_fields_present": bool(forbidden),
        "forbidden_fields": "|".join(forbidden) if forbidden else "NONE",
        "generated_plot_count": int(len(generated_plots)),
        "annotation_summary_row_count": int(len(annotation)),
    }
    expected = {
        "input_data_table_row_count": 286,
        "activity_count": 26,
        "baseline_activity_count": 25,
        "extra_source_activity_count": 1,
        "plotted_baseline_activity_count": 25,
        "plotted_extra_source_activity_count": 0,
        "limited_proxy_axis_count": 3,
        "plotted_axis_count_per_baseline_activity_min": 3,
        "plotted_axis_count_per_baseline_activity_max": 3,
        "descriptive_annotation_not_plotted": True,
        "missing_evidence_annotation_not_plotted": True,
        "zero_fill_used": False,
        "forbidden_fields_present": False,
    }
    review_reasons = [
        f"{key}={checks[key]} expected {expected_value}"
        for key, expected_value in expected.items()
        if checks[key] != expected_value
    ]
    if sorted(limited_axes) != sorted(EXPECTED_LIMITED_AXES):
        review_reasons.append(
            "limited_proxy_axes="
            + "|".join(limited_axes)
            + " expected "
            + "|".join(EXPECTED_LIMITED_AXES)
        )
    if len(generated_plots) != checks["plotted_baseline_activity_count"]:
        review_reasons.append("generated_plot_count_mismatch")

    checks["limited_proxy_axes"] = "|".join(limited_axes)
    checks["audit_conclusion"] = (
        PASS_CONCLUSION if not review_reasons else "REVIEW_REQUIRED"
    )
    checks["review_reasons"] = "|".join(review_reasons) if review_reasons else "NONE"
    checks["interpretation_boundary"] = INTERPRETATION_BOUNDARY
    return pd.DataFrame([checks])


def write_report(
    ready: pd.DataFrame,
    plot_index: pd.DataFrame,
    annotation: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    audit_row = audit.iloc[0].to_dict()
    plotted = plot_index[plot_index["plot_created"]].copy()
    skipped = plot_index[~plot_index["plot_created"]].copy()
    limited_axes = (
        ready.loc[ready["axis_output_mode"] == LIMITED_PROXY_MODE, ["axis_id", "axis_label_zh"]]
        .drop_duplicates()
        .sort_values("axis_id")
    )

    def table_html(frame: pd.DataFrame, max_rows: int | None = None) -> str:
        data = frame if max_rows is None else frame.head(max_rows)
        return data.to_html(index=False, escape=True, border=0)

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CH6.5.5 personal ability radar plot v1_1</title>
  <style>
    body {{ font-family: Arial, "Microsoft JhengHei", sans-serif; margin: 32px; color: #172326; background: #f7f8f4; }}
    h1, h2 {{ margin-bottom: 0.35rem; }}
    .note {{ max-width: 980px; line-height: 1.5; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background: #dceee8; color: #143e3d; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 28px; background: white; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dfda; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #e8efeb; text-align: left; }}
    code {{ background: #eef2ef; padding: 2px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>CH6.5.5 Personal Ability Radar Plot v1_1</h1>
  <p><span class="badge">Governed limited proxy preview</span></p>
  <p class="note"><strong>Not an ability score / rank / class.</strong> This report plots only admitted limited proxy axes from data table v1_1. It does not create a formal ability radar score, final hiking risk score, route suitability score, go/no-go decision, medical diagnosis, or causal claim.</p>

  <h2>Audit</h2>
  <p><code>{html.escape(str(audit_row["audit_conclusion"]))}</code></p>
  {table_html(audit)}

  <h2>Limited Proxy Axes</h2>
  {table_html(limited_axes)}

  <h2>Plot Summary</h2>
  {table_html(plot_index[["activity_id_short", "study_population_status", "plot_created", "plot_reason", "plotted_axis_count", "plot_path"]])}

  <h2>Skipped Activities</h2>
  {table_html(skipped[["activity_id_short", "study_population_status", "plot_reason", "allowed_proxy_axis_count", "blocked_limited_proxy_axis_count"]])}

  <h2>Annotation Summary Sample</h2>
  <p class="note">Descriptive and missing-evidence axes are kept as annotations. Blocked limited proxy rows, including extra-source rows, are not zero-filled.</p>
  {table_html(annotation[["activity_id_short", "axis_id", "axis_label_zh", "axis_output_mode", "plot_permission_note"]], max_rows=40)}
</body>
</html>
"""
    REPORT.write_text(html_text, encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    df = load_data()
    ready = build_ready_table(df)
    plot_index, generated_plots = build_plot_index_and_images(ready)
    annotation = build_annotation_summary(ready)
    audit = build_audit(df, ready, plot_index, annotation, generated_plots)

    ready.to_csv(READY_TABLE, index=False, encoding="utf-8-sig")
    plot_index.to_csv(PLOT_INDEX, index=False, encoding="utf-8-sig")
    annotation.to_csv(ANNOTATION_SUMMARY, index=False, encoding="utf-8-sig")
    audit.to_csv(AUDIT, index=False, encoding="utf-8-sig")
    write_report(ready, plot_index, annotation, audit)

    result = {
        "script": str(Path(__file__).resolve()),
        "output_root": str(OUTPUT_ROOT),
        "audit_csv": str(AUDIT),
        "audit_conclusion": audit["audit_conclusion"].iloc[0],
        "plotted_baseline_activity_count": int(
            audit["plotted_baseline_activity_count"].iloc[0]
        ),
        "plotted_extra_source_activity_count": int(
            audit["plotted_extra_source_activity_count"].iloc[0]
        ),
        "limited_proxy_axis_count": int(audit["limited_proxy_axis_count"].iloc[0]),
        "plotted_axis_count_per_baseline_activity_min": int(
            audit["plotted_axis_count_per_baseline_activity_min"].iloc[0]
        ),
        "plotted_axis_count_per_baseline_activity_max": int(
            audit["plotted_axis_count_per_baseline_activity_max"].iloc[0]
        ),
        "generated_plot_count": int(audit["generated_plot_count"].iloc[0]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
