from __future__ import annotations

import csv, html, math
from pathlib import Path
from statistics import median
from collections import Counter, defaultdict

SCHEMA_VERSION = "ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1"
PERFORMANCE_SUMMARY_CSV = Path("outputs/ib3a_rc_full26_performance_summary_v1/activity_performance_summary.csv")
USABILITY_GATE_CSV = Path("outputs/ib3_baseline_hiking_performance_v0_usability_gate_smoke_v1/activity_v0_usability_gate_smoke.csv")
OUT_ROOT = Path("outputs/ib3_baseline_hiking_performance_elevation_gain_aggregation_qa_v1")
OUT_QA_CSV = OUT_ROOT / "activity_elevation_gain_aggregation_qa.csv"
OUT_AUDIT_CSV = OUT_ROOT / "elevation_gain_aggregation_qa_audit.csv"
OUT_REPORT_HTML = OUT_ROOT / "elevation_gain_aggregation_qa_report.html"
AUTHORIZATION_NOTE = "Elevation gain aggregation QA is descriptive evidence only. It does not compute or authorize ability scores, ability ranks, ability classes, THCI scores, radar scores, or final hiking risk scores."
BLOCKED_GAIN_FEATURES = "calibrated_cumulative_gain_m|calibrated_cumulative_loss_m|candidate_gain_m_per_km|candidate_gain_rate_m_per_hour|candidate_duration_min_per_100m_gain"

def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]

def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def as_float(v):
    s = str(v).strip()
    if not s:
        return None
    try:
        x = float(s)
        return None if math.isnan(x) else x
    except ValueError:
        return None

def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}

def fmt(v, digits=6):
    x = as_float(v)
    if x is None:
        return ""
    s = f"{x:.{digits}f}".rstrip("0").rstrip(".")
    return s if s else "0"

def pct(n, d):
    return "" if d <= 0 else fmt(100.0 * n / d, 3)

def vals(rows, field):
    out = []
    for r in rows:
        x = as_float(r.get(field, ""))
        if x is not None:
            out.append(x)
    return out

def compact(values, max_items=12):
    c = Counter(v if str(v).strip() else "BLANK" for v in values)
    return "|".join(f"{k}:{v}" for k, v in c.most_common(max_items))

def reason_has(row, token):
    return token in str(row.get("gain_loss_excluded_reason", ""))

def profile_candidate(rows):
    for dist_field, ele_field, source in [
        ("elevation_profile_dist_m", "elevation_profile_ele_smooth_m", "PROFILE_SMOOTH"),
        ("route_dist_m", "calibrated_elevation_m", "ROUTE_DIST_CALIBRATED_ELEVATION"),
    ]:
        groups = defaultdict(list)
        for r in rows:
            d, e = as_float(r.get(dist_field, "")), as_float(r.get(ele_field, ""))
            if d is not None and e is not None:
                groups[int(round(d))].append(e)
        if len(groups) < 2:
            continue
        series = [(k, float(median(v))) for k, v in sorted(groups.items())]
        asc = desc = 0.0
        prev = series[0][1]
        for _, e in series[1:]:
            delta = e - prev
            if delta > 0:
                asc += delta
            elif delta < 0:
                desc += -delta
            prev = e
        return asc, desc, len(series), source
    return None, None, 0, "UNAVAILABLE"

def analyze(perf, gate_by_id):
    sid = perf.get("activity_id_short", "").strip()
    input_csv = Path(perf.get("input_csv", "").strip())
    gate = gate_by_id.get(sid, {})
    base = {
        "schema_version": SCHEMA_VERSION,
        "activity_id_short": sid,
        "activity_id_full": perf.get("activity_id_full", ""),
        "v0_usability_gate": gate.get("v0_usability_gate", ""),
        "included_in_v0_usable_set": str(gate.get("v0_usability_gate", "") in {"USABLE", "USABLE_FOR_V0_MODEL_SMOKE"}),
        "input_csv": str(input_csv),
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "ability_class_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "authorization_note": AUTHORIZATION_NOTE,
    }
    if not input_csv.exists():
        base["qa_status"] = "INPUT_CSV_MISSING"
        return base

    rows = read_csv(input_csv)
    ele = vals(rows, "calibrated_elevation_m")
    cgain, closs = vals(rows, "calibrated_cumulative_gain_m"), vals(rows, "calibrated_cumulative_loss_m")
    agg_gain, agg_loss = vals(rows, "agg_total_gain_m"), vals(rows, "agg_total_loss_m")
    supp_gain, supp_loss = vals(rows, "agg_supplemental_gain_m"), vals(rows, "agg_supplemental_loss_m")

    ele_min = min(ele) if ele else None
    ele_max = max(ele) if ele else None
    ele_range = (ele_max - ele_min) if ele_min is not None and ele_max is not None else None
    cal_gain_max = max(cgain) if cgain else None
    cal_loss_max = max(closs) if closs else None
    agg_gain_max = max(agg_gain) if agg_gain else None
    agg_loss_max = max(agg_loss) if agg_loss else None
    supp_gain_max = max(supp_gain) if supp_gain else None
    supp_loss_max = max(supp_loss) if supp_loss else None
    prof_asc, prof_desc, prof_n, prof_src = profile_candidate(rows)

    valid = invalid = pos = pos_valid = pos_invalid = 0
    valid_pos_sum = invalid_pos_sum = 0.0
    for r in rows:
        step_valid = as_bool(r.get("elevation_step_valid", ""))
        valid += int(step_valid)
        invalid += int(not step_valid)
        d = as_float(r.get("calibrated_delta_elevation_m", ""))
        if d is not None and d > 0:
            pos += 1
            if step_valid:
                pos_valid += 1
                valid_pos_sum += d
            else:
                pos_invalid += 1
                invalid_pos_sum += d

    step_lt3 = sum(1 for r in rows if reason_has(r, "STEP_DISTANCE_LT_3M"))
    profile_soft = sum(1 for r in rows if reason_has(r, "PROFILE_DISTANCE_JUMP_GT_100M_WITH_SMALL_STEP_SOFT"))
    profile_hard = sum(1 for r in rows if reason_has(r, "PROFILE_DISTANCE_JUMP_HARD_EXCLUDED"))
    join_gt10 = sum(1 for r in rows if reason_has(r, "ELEVATION_JOIN_DIST_GT_10M_HARD_EXCLUDED"))
    dup = sum(1 for r in rows if reason_has(r, "DUPLICATE_TIMESTAMP_NON_REPRESENTATIVE"))
    time_bad = sum(1 for r in rows if reason_has(r, "TIME_INTERVAL_INVALID"))

    flags = []
    if ele_range is None or ele_range <= 0:
        flags.append("ELEVATION_RANGE_UNAVAILABLE")
    if agg_gain_max is None:
        flags.append("AGG_TOTAL_GAIN_UNAVAILABLE")
    if ele_range and agg_gain_max is not None and agg_gain_max < 0.5 * ele_range:
        flags.append("AGG_TOTAL_GAIN_BELOW_50PCT_ELEVATION_RANGE")
    if ele_range and cal_gain_max is not None and cal_gain_max < 0.5 * ele_range:
        flags.append("CALIBRATED_GAIN_BELOW_50PCT_ELEVATION_RANGE")
    if pos > 0 and pos_valid / pos < 0.25:
        flags.append("POSITIVE_ELEVATION_DELTAS_MOSTLY_INVALID")
    if rows and step_lt3 / len(rows) > 0.5:
        flags.append("STEP_DISTANCE_LT_3M_DOMINANT")
    if prof_asc is not None and ele_range and prof_asc >= 0.8 * ele_range:
        flags.append("ROUTE_PROFILE_ASCENT_CANDIDATE_AVAILABLE")

    status = "GAIN_FEATURES_BLOCKED_ELEVATION_GAIN_AGGREGATION_QA_REQUIRED"
    if "ROUTE_PROFILE_ASCENT_CANDIDATE_AVAILABLE" in flags:
        status = "GAIN_FEATURES_BLOCKED_ROUTE_PROFILE_CANDIDATE_AVAILABLE_QA_REQUIRED"

    base.update({
        "point_rows": len(rows),
        "duration_min": perf.get("duration_min", ""),
        "route_dist_covered_m": perf.get("route_dist_covered_m", ""),
        "ele_min_m": fmt(ele_min),
        "ele_max_m": fmt(ele_max),
        "ele_range_m": fmt(ele_range),
        "calibrated_cumulative_gain_max_m": fmt(cal_gain_max),
        "calibrated_cumulative_loss_max_m": fmt(cal_loss_max),
        "agg_supplemental_gain_max_m": fmt(supp_gain_max),
        "agg_supplemental_loss_max_m": fmt(supp_loss_max),
        "agg_total_gain_max_m": fmt(agg_gain_max),
        "agg_total_loss_max_m": fmt(agg_loss_max),
        "route_profile_ascent_candidate_m": fmt(prof_asc),
        "route_profile_descent_candidate_m": fmt(prof_desc),
        "route_profile_candidate_points": prof_n,
        "route_profile_candidate_source": prof_src,
        "agg_gain_to_elevation_range_ratio": fmt((agg_gain_max / ele_range) if agg_gain_max is not None and ele_range else None),
        "calibrated_gain_to_elevation_range_ratio": fmt((cal_gain_max / ele_range) if cal_gain_max is not None and ele_range else None),
        "route_profile_ascent_to_elevation_range_ratio": fmt((prof_asc / ele_range) if prof_asc is not None and ele_range else None),
        "elevation_step_valid_true_count": valid,
        "elevation_step_valid_false_count": invalid,
        "elevation_step_valid_true_pct": pct(valid, len(rows)),
        "positive_delta_rows": pos,
        "positive_delta_valid_rows": pos_valid,
        "positive_delta_invalid_rows": pos_invalid,
        "positive_delta_valid_pct": pct(pos_valid, pos),
        "valid_positive_delta_sum_m": fmt(valid_pos_sum),
        "invalid_positive_delta_sum_m": fmt(invalid_pos_sum),
        "step_distance_lt_3m_rows": step_lt3,
        "step_distance_lt_3m_pct": pct(step_lt3, len(rows)),
        "profile_jump_soft_rows": profile_soft,
        "profile_jump_hard_rows": profile_hard,
        "elevation_join_dist_gt_10m_rows": join_gt10,
        "duplicate_timestamp_nonrepresentative_rows": dup,
        "time_interval_invalid_rows": time_bad,
        "gain_loss_excluded_reason_distribution": compact([r.get("gain_loss_excluded_reason", "") for r in rows]),
        "qa_flags": "|".join(flags),
        "qa_status": status,
        "blocked_gain_features": BLOCKED_GAIN_FEATURES,
        "qa_note": "Existing activity-point cumulative gain/loss is not model-ready. 1Hz slow hiking can be over-excluded by STEP_DISTANCE_LT_3M and related step-validity rules. Route-profile ascent/descent candidate is QA evidence only until a revised contract is approved.",
    })
    return base

def esc(v):
    return html.escape(str(v))

def table(rows, cols):
    head = "".join(f"<th>{esc(label)}</th>" for _, label in cols)
    body = "".join("<tr>" + "".join(f"<td>{esc(r.get(key,''))}</td>" for key, _ in cols) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

def main():
    perf = read_csv(PERFORMANCE_SUMMARY_CSV)
    gates = read_csv(USABILITY_GATE_CSV)
    gate_by_id = {r.get("activity_id_short","").strip(): r for r in gates}
    qa = [analyze(r, gate_by_id) for r in perf]

    usable = sum(1 for r in qa if r.get("included_in_v0_usable_set") == "True")
    low_agg = sum(1 for r in qa if "AGG_TOTAL_GAIN_BELOW_50PCT_ELEVATION_RANGE" in str(r.get("qa_flags","")))
    step_dom = sum(1 for r in qa if "STEP_DISTANCE_LT_3M_DOMINANT" in str(r.get("qa_flags","")))
    prof_ok = sum(1 for r in qa if "ROUTE_PROFILE_ASCENT_CANDIDATE_AVAILABLE" in str(r.get("qa_flags","")))
    audit = {
        "schema_version": SCHEMA_VERSION,
        "input_performance_summary_csv": str(PERFORMANCE_SUMMARY_CSV),
        "input_usability_gate_csv": str(USABILITY_GATE_CSV),
        "input_row_count": len(perf),
        "usable_input_row_count": usable,
        "review_only_input_row_count": len(perf) - usable,
        "output_qa_row_count": len(qa),
        "agg_total_gain_below_50pct_elevation_range_count": low_agg,
        "step_distance_lt_3m_dominant_count": step_dom,
        "route_profile_ascent_candidate_available_count": prof_ok,
        "qa_status_distribution": compact([r.get("qa_status","") for r in qa], 20),
        "qa_flag_distribution": compact([f for r in qa for f in str(r.get("qa_flags","")).split("|") if f], 20),
        "blocked_gain_features": BLOCKED_GAIN_FEATURES,
        "gain_features_model_ready": "False",
        "route_profile_candidate_model_ready": "False",
        "ability_score_generated": "False",
        "ability_rank_generated": "False",
        "ability_class_generated": "False",
        "thci_scoring_authorized": "False",
        "radar_scoring_authorized": "False",
        "final_hiking_risk_scoring_authorized": "False",
        "zero_fallback_used": "False",
        "audit_conclusion": "PASS_ELEVATION_GAIN_AGGREGATION_QA_DESCRIPTIVE_ONLY",
    }

    write_csv(OUT_QA_CSV, qa)
    write_csv(OUT_AUDIT_CSV, [audit])

    cards = [
        ("input activities", len(perf)),
        ("usable activities", usable),
        ("low aggregate gain", low_agg),
        ("step <3m dominant", step_dom),
        ("profile candidates", prof_ok),
        ("audit", audit["audit_conclusion"]),
    ]
    card_html = "".join(f'<div class="card"><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for k, v in cards)
    cols = [
        ("activity_id_short","activity"),
        ("included_in_v0_usable_set","usable"),
        ("ele_range_m","elev range"),
        ("calibrated_cumulative_gain_max_m","cal gain"),
        ("agg_total_gain_max_m","agg gain"),
        ("route_profile_ascent_candidate_m","profile ascent cand."),
        ("positive_delta_valid_pct","positive delta valid %"),
        ("step_distance_lt_3m_pct","step <3m %"),
        ("qa_flags","QA flags"),
        ("qa_status","QA status"),
    ]
    audit_cols = [(k, k) for k in audit]
    html_text = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>IB3 Elevation Gain Aggregation QA</title>
<style>
body{{font-family:Arial,"Noto Sans TC",sans-serif;margin:24px;color:#1f2933}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:16px 0}}
.card{{border:1px solid #d8dee4;border-radius:8px;padding:12px;background:#f8fafc}}
.card strong{{display:block;font-size:20px}}.card span{{color:#52606d;font-size:12px}}
.note{{background:#fff8dc;border-left:4px solid #d4a72c;padding:12px;line-height:1.6}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:12px}}
th,td{{border:1px solid #d8dee4;padding:6px;text-align:right;vertical-align:top}}
th:first-child,td:first-child,th:nth-last-child(-n+2),td:nth-last-child(-n+2){{text-align:left}}
th{{background:#eef2f6;position:sticky;top:0}}
</style></head><body>
<h1>IB3 Elevation Gain Aggregation QA</h1>
<p class="note"><strong>Boundary:</strong> {esc(AUTHORIZATION_NOTE)}<br>
This QA explains why activity-point gain/loss fields are blocked for future ability estimation. It does not score ability, rank people, or produce THCI, radar, or final-risk scores.<br>
Main known issue: 1Hz slow hiking can be over-excluded by STEP_DISTANCE_LT_3M and related step-validity rules.</p>
<div class="cards">{card_html}</div>
<h2>Audit</h2>{table([audit], audit_cols)}
<h2>Activity QA table</h2>{table(qa, cols)}
</body></html>"""
    OUT_REPORT_HTML.write_text(html_text, encoding="utf-8")

    print("IB3 elevation gain aggregation QA v1")
    for k in ["input_row_count","usable_input_row_count","review_only_input_row_count","output_qa_row_count","agg_total_gain_below_50pct_elevation_range_count","step_distance_lt_3m_dominant_count","route_profile_ascent_candidate_available_count","qa_status_distribution","qa_flag_distribution","gain_features_model_ready","audit_conclusion"]:
        print(f"{k}={audit[k]}")
    print(f"wrote={OUT_QA_CSV}")
    print(f"wrote={OUT_AUDIT_CSV}")
    print(f"wrote={OUT_REPORT_HTML}")

if __name__ == "__main__":
    main()
