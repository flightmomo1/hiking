from __future__ import annotations

import csv
import html
from pathlib import Path
from collections import Counter

SCHEMA_VERSION = "ib3_baseline_hiking_performance_route_profile_ascent_features_v1"

BASE_COMPARISON_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_weather_numeric_reattach_v1/"
    "activity_route_normalized_comparison_weather_reattached.csv"
)
ELEVATION_QA_CSV = Path(
    "outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1/"
    "activity_elevation_gain_aggregation_qa.csv"
)

OUT_ROOT = Path("outputs/ib3_baseline_hiking_performance_route_profile_ascent_features_v1")
OUT_FEATURE_CSV = OUT_ROOT / "activity_route_profile_ascent_features.csv"
OUT_AUDIT_CSV = OUT_ROOT / "route_profile_ascent_feature_audit.csv"
OUT_REPORT_HTML = OUT_ROOT / "route_profile_ascent_feature_report.html"

AUTHORIZATION_NOTE = (
    "Route-profile ascent feature patch is descriptive / feature-contract evidence only. "
    "It does not compute or authorize ability scores, ability ranks, ability classes, "
    "THCI scores, radar scores, or final hiking risk scores."
)

BLOCKED_LEGACY_GAIN_FEATURES = (
    "calibrated_cumulative_gain_m|calibrated_cumulative_loss_m|agg_total_gain_m|"
    "agg_total_loss_m|candidate_gain_m_per_km|candidate_gain_rate_m_per_hour|"
    "candidate_duration_min_per_100m_gain"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: object) -> float | None:
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt(value: object, digits: int = 6) -> str:
    v = as_float(value)
    if v is None:
        return ""
    text = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def div(n: float | None, d: float | None) -> float | None:
    if n is None or d is None or d == 0:
        return None
    return n / d


def distribution(values: list[str]) -> str:
    counts = Counter(v if str(v).strip() else "BLANK" for v in values)
    return "|".join(f"{k}:{v}" for k, v in counts.most_common())


def esc(value: object) -> str:
    return html.escape(str(value))


def route_profile_status(qa: dict[str, str] | None) -> tuple[str, str]:
    if qa is None:
        return "BLOCKED_MISSING_ELEVATION_GAIN_QA", "missing elevation gain QA row"
    if qa.get("route_profile_ascent_candidate_m", "").strip() == "":
        return "BLOCKED_ROUTE_PROFILE_ASCENT_UNAVAILABLE", "route profile ascent candidate unavailable"
    if "ROUTE_PROFILE_ASCENT_CANDIDATE_AVAILABLE" not in qa.get("qa_flags", ""):
        return "REVIEW_ROUTE_PROFILE_ASCENT_CANDIDATE_FLAG_MISSING", "candidate value present but candidate flag missing"
    return (
        "ROUTE_PROFILE_ASCENT_FEATURE_READY_DESCRIPTIVE_CONTRACT_PATCH",
        "use route profile ascent/descent as corrected route-demand feature; legacy activity-point gain remains blocked",
    )


def make_row(base: dict[str, str], qa_by_activity: dict[str, dict[str, str]]) -> dict[str, object]:
    activity_id = base.get("activity_id_short", "").strip()
    qa = qa_by_activity.get(activity_id)

    out: dict[str, object] = dict(base)

    duration_min = as_float(base.get("duration_min", ""))
    route_km = as_float(base.get("route_dist_covered_km", ""))
    if route_km is None:
        dist_m = as_float(base.get("route_dist_covered_m", ""))
        route_km = div(dist_m, 1000.0)

    ascent = as_float(qa.get("route_profile_ascent_candidate_m", "")) if qa else None
    descent = as_float(qa.get("route_profile_descent_candidate_m", "")) if qa else None
    status, reason = route_profile_status(qa)

    out.update(
        {
            "legacy_gain_features_blocked": "True",
            "legacy_gain_features_blocked_reason": (
                "activity-point cumulative gain/loss underestimates ascent for 1Hz slow hiking; "
                "STEP_DISTANCE_LT_3M and related validity gates over-exclude normal uphill progression"
            ),
            "legacy_blocked_gain_features": BLOCKED_LEGACY_GAIN_FEATURES,
            "legacy_candidate_gain_m_per_km_original": base.get("candidate_gain_m_per_km", ""),
            "legacy_candidate_gain_rate_m_per_hour_original": base.get("candidate_gain_rate_m_per_hour", ""),
            "legacy_candidate_duration_min_per_100m_gain_original": base.get("candidate_duration_min_per_100m_gain", ""),
            "route_profile_ascent_m": fmt(ascent),
            "route_profile_descent_m": fmt(descent),
            "route_profile_ascent_m_per_km": fmt(div(ascent, route_km)),
            "route_profile_descent_m_per_km": fmt(div(descent, route_km)),
            "route_profile_ascent_rate_m_per_hour": fmt(div(ascent, div(duration_min, 60.0))),
            "duration_min_per_100m_route_profile_ascent": fmt(div(duration_min, div(ascent, 100.0))),
            "route_profile_descent_rate_m_per_hour": fmt(div(descent, div(duration_min, 60.0))),
            "duration_min_per_100m_route_profile_descent": fmt(div(duration_min, div(descent, 100.0))),
            "route_profile_candidate_points": qa.get("route_profile_candidate_points", "") if qa else "",
            "route_profile_candidate_source": qa.get("route_profile_candidate_source", "") if qa else "",
            "elevation_gain_qa_status": qa.get("qa_status", "") if qa else "",
            "elevation_gain_qa_flags": qa.get("qa_flags", "") if qa else "",
            "route_profile_gain_feature_status": status,
            "route_profile_gain_feature_status_reason": reason,
            "route_profile_gain_feature_model_ready": "False",
            "feature_contract_patch_required": "True",
            "ability_score_generated": "False",
            "ability_rank_generated": "False",
            "ability_class_generated": "False",
            "thci_scoring_authorized": "False",
            "radar_scoring_authorized": "False",
            "final_hiking_risk_scoring_authorized": "False",
            "authorization_note": AUTHORIZATION_NOTE,
        }
    )
    return out


def render_table(rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> str:
    head = "".join(f"<th>{esc(label)}</th>" for _, label in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{esc(row.get(key, ''))}</td>" for key, _ in columns)
        body.append(f"<tr>{cells}</tr>")
    return '<div class="table-wrap"><table><thead><tr>' + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"


def main() -> None:
    base_rows = read_csv(BASE_COMPARISON_CSV)
    qa_rows = read_csv(ELEVATION_QA_CSV)
    qa_by_activity = {row.get("activity_id_short", "").strip(): row for row in qa_rows}

    output_rows = [make_row(row, qa_by_activity) for row in base_rows]

    matched_qa_count = sum(1 for row in base_rows if row.get("activity_id_short", "").strip() in qa_by_activity)
    missing_qa_count = len(base_rows) - matched_qa_count
    ready_count = sum(
        1
        for row in output_rows
        if row.get("route_profile_gain_feature_status") == "ROUTE_PROFILE_ASCENT_FEATURE_READY_DESCRIPTIVE_CONTRACT_PATCH"
    )
    status_dist = distribution([str(row.get("route_profile_gain_feature_status", "")) for row in output_rows])

    audit = {
        "schema_version": SCHEMA_VERSION,
        "base_comparison_csv": str(BASE_COMPARISON_CSV),
        "elevation_gain_qa_csv": str(ELEVATION_QA_CSV),
        "base_row_count": len(base_rows),
        "elevation_qa_row_count": len(qa_rows),
        "output_row_count": len(output_rows),
        "matched_elevation_qa_count": matched_qa_count,
        "missing_elevation_qa_count": missing_qa_count,
        "legacy_gain_features_blocked_count": len(output_rows),
        "route_profile_ascent_feature_ready_count": ready_count,
        "route_profile_gain_feature_status_distribution": status_dist,
        "blocked_legacy_gain_features": BLOCKED_LEGACY_GAIN_FEATURES,
        "route_profile_gain_feature_model_ready": "False",
        "feature_contract_patch_required": "True",
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "ability_class_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": (
            "PASS_ROUTE_PROFILE_ASCENT_FEATURE_PATCH_DESCRIPTIVE_CONTRACT_REQUIRED"
            if missing_qa_count == 0 and ready_count == len(output_rows)
            else "REVIEW_ROUTE_PROFILE_ASCENT_FEATURE_PATCH"
        ),
    }

    write_csv(OUT_FEATURE_CSV, output_rows)
    write_csv(OUT_AUDIT_CSV, [audit])

    cards = [
        ("base rows", audit["base_row_count"]),
        ("matched QA", audit["matched_elevation_qa_count"]),
        ("legacy blocked", audit["legacy_gain_features_blocked_count"]),
        ("route-profile ready", audit["route_profile_ascent_feature_ready_count"]),
        ("audit", audit["audit_conclusion"]),
    ]
    card_html = "".join(f'<div class="card"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for k, v in cards)

    audit_columns = [(key, key) for key in audit.keys()]
    feature_columns = [
        ("activity_id_short", "activity"),
        ("route_dist_covered_km", "route km"),
        ("duration_min", "duration min"),
        ("legacy_candidate_gain_m_per_km_original", "legacy gain/km"),
        ("route_profile_ascent_m", "profile ascent"),
        ("route_profile_descent_m", "profile descent"),
        ("route_profile_ascent_m_per_km", "profile ascent/km"),
        ("route_profile_ascent_rate_m_per_hour", "profile ascent rate"),
        ("duration_min_per_100m_route_profile_ascent", "min/100m profile ascent"),
        ("route_profile_gain_feature_status", "status"),
    ]

    html_text = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>IB3 Route Profile Ascent Feature Patch</title>
<style>
body{{font-family:Arial,"Noto Sans TC",sans-serif;margin:24px;color:#1f2933}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:16px 0}}
.card{{border:1px solid #d8dee4;border-radius:8px;padding:12px;background:#f8fafc}}
.card strong{{display:block;font-size:20px}}.card span{{color:#52606d;font-size:12px}}
.note{{background:#fff8dc;border-left:4px solid #d4a72c;padding:12px;line-height:1.6}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:12px}}
th,td{{border:1px solid #d8dee4;padding:6px;text-align:right;vertical-align:top}}
th:first-child,td:first-child,th:last-child,td:last-child{{text-align:left}}
th{{background:#eef2f6;position:sticky;top:0}}
</style>
</head>
<body>
<h1>IB3 Route Profile Ascent Feature Patch</h1>
<p class="note"><strong>Boundary:</strong> {esc(AUTHORIZATION_NOTE)}<br>
This patch preserves legacy gain fields as blocked evidence and adds route-profile-based ascent/descent feature candidates for downstream contract review. Model use still requires a formal feature contract patch.</p>
<div class="cards">{card_html}</div>
<h2>Audit</h2>
{render_table([audit], audit_columns)}
<h2>Route-profile ascent feature table</h2>
{render_table(output_rows, feature_columns)}
</body>
</html>
"""
    OUT_REPORT_HTML.write_text(html_text, encoding="utf-8")

    print("IB3 route-profile ascent feature patch v1")
    for key in [
        "base_row_count",
        "elevation_qa_row_count",
        "output_row_count",
        "matched_elevation_qa_count",
        "missing_elevation_qa_count",
        "legacy_gain_features_blocked_count",
        "route_profile_ascent_feature_ready_count",
        "route_profile_gain_feature_status_distribution",
        "route_profile_gain_feature_model_ready",
        "feature_contract_patch_required",
        "audit_conclusion",
    ]:
        print(f"{key}={audit[key]}")
    print(f"wrote={OUT_FEATURE_CSV}")
    print(f"wrote={OUT_AUDIT_CSV}")
    print(f"wrote={OUT_REPORT_HTML}")


if __name__ == "__main__":
    main()
