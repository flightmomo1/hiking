# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import argparse

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASES = [
    "qixing_lengshuikeng_main_peak_20260523_osmrefresh_v1_3b",
    "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b",
    "juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b",
    "zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b",
]

SEMANTICS_ROOT = PROJECT_ROOT / "outputs" / "ib1c_route_profile_semantics_v1_3b_contract_qa"
RISK_ROOT = PROJECT_ROOT / "outputs" / "ib1c_osm_semantic_risk_v1_3b_contract_qa"
MAPPING_CSV = PROJECT_ROOT / "configs" / "risk_semantics" / "osm_semantic_risk_mapping_v1_5_support_updated.csv"
OUT_ROOT = PROJECT_ROOT / "outputs" / "ib1c_semantic_risk_mapping_coverage_audit_v1_3b"

FIELD_TO_SOURCE_FIELD = {
    "osm_trail_visibility": "trail_visibility",
    "osm_surface": "surface",
    "osm_highway": "highway",
    "osm_bridge": "bridge",
    "osm_ford": "ford",
    "osm_tunnel": "tunnel",
    "osm_handrail": "handrail",
    "osm_safety_rope": "safety_rope",
    "osm_sac_scale": "sac_scale",
    "osm_lit": "lit",
    "osm_lit_status": "lit",
}

FLAG_FIELDS = {
    "technical_flags": "technical",
    "safety_flags": "safety",
    "hazard_flags": "hazard",
    "hydrology_flags": "hydrology",
    "landmark_flags": "landmark",
    "facility_flags": "facility",
    "rest_flags": "rest",
    "support_flags": "support",
}

FLAG_VALUE_TO_SOURCE_FIELD = {
    "handrail": "handrail",
    "safety_rope": "safety_rope",
    "rungs": "rungs",
    "ladder": "ladder",
    "via_ferrata": "via_ferrata",
    "assisted_trail": "assisted_trail",
    "cliff": "cliff",
    "scree": "scree",
    "bare_rock": "bare_rock",
    "landslide": "landslide",
    "waterway": "waterway",
    "wetland": "wetland",
    "water_area": "water_area",
    "guidepost": "guidepost",
    "trailhead": "trailhead",
    "peak": "peak",
    "shelter": "shelter",
    "alpine_hut": "alpine_hut",
    "wilderness_hut": "wilderness_hut",
    "bench": "bench",
    "picnic_table": "picnic_table",
    "picnic_site": "picnic_site",
    "drinking_water": "drinking_water",
    "toilets": "toilets",
    "visitor_centre": "visitor_centre",
    "information_office": "information_office",
    "street_lamp": "street_lamp",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit IB1C semantic risk mapping coverage for v1.3b cases without modifying mapping config."
    )
    parser.add_argument("--mapping-csv", default=str(MAPPING_CSV))
    parser.add_argument("--out-root", default=str(OUT_ROOT))
    return parser.parse_args()


def norm_value(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().strip('"').strip().lower()
    if text in {"", "nan", "none", "<na>", "na", "null", "nat"}:
        return ""
    return text


def split_flag_value(value: object) -> list[str]:
    text = norm_value(value)
    if text in {"", "normal", "none"}:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def make_key(source_field: str, source_value: str) -> str:
    return f"{source_field}::{source_value}"


def semantic_csv(case_id: str) -> Path:
    return SEMANTICS_ROOT / case_id / f"{case_id}_route_profile_semantic_enriched.csv"


def risk_summary_csv(case_id: str) -> Path:
    return RISK_ROOT / case_id / f"{case_id}_osm_semantic_risk_summary.csv"


def mapping_keys(mapping_df: pd.DataFrame) -> set[str]:
    keys: set[str] = set()
    for _, row in mapping_df.iterrows():
        source_field = norm_value(row.get("source_field", ""))
        source_value = norm_value(row.get("source_value", ""))
        if source_field and source_value:
            keys.add(make_key(source_field, source_value))
    return keys


def load_mapping_context(mapping_df: pd.DataFrame) -> dict[tuple[str, str], dict[str, str]]:
    context: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in mapping_df.iterrows():
        source_field = norm_value(row.get("source_field", ""))
        source_value = norm_value(row.get("source_value", ""))
        if not source_field or not source_value:
            continue
        context[(source_field, source_value)] = {
            "semantic_group": str(row.get("semantic_group", "")),
            "derived_class": str(row.get("derived_class", "")),
            "risk_domain": str(row.get("risk_domain", "")),
            "base_score": str(row.get("base_score", "")),
            "risk_direction": str(row.get("risk_direction", "")),
            "notes": str(row.get("notes", "")),
        }
    return context


def matching_key_for_flag(source_field: str, value: str, keys: set[str]) -> tuple[str, bool]:
    for candidate in ["near", "yes", value]:
        key = make_key(source_field, candidate)
        if key in keys:
            return key, True
    return make_key(source_field, value), False


def observed_values_for_case(case_id: str, keys: set[str]) -> pd.DataFrame:
    df = pd.read_csv(semantic_csv(case_id), low_memory=False)
    rows: list[dict[str, object]] = []

    for ib1c_field, source_field in FIELD_TO_SOURCE_FIELD.items():
        if ib1c_field not in df.columns:
            rows.append(
                {
                    "case_id": case_id,
                    "ib1c_field": ib1c_field,
                    "semantic_key": source_field,
                    "semantic_value": "",
                    "observed_count": 0,
                    "mapping_key": "",
                    "has_mapping": False,
                    "value_kind": "raw_tag",
                    "note": "field_missing_in_ib1c_output",
                }
            )
            continue
        vc = df[ib1c_field].map(norm_value).replace("", pd.NA).dropna().value_counts()
        for value, count in vc.items():
            key = make_key(source_field, value)
            rows.append(
                {
                    "case_id": case_id,
                    "ib1c_field": ib1c_field,
                    "semantic_key": source_field,
                    "semantic_value": value,
                    "observed_count": int(count),
                    "mapping_key": key,
                    "has_mapping": key in keys,
                    "value_kind": "raw_tag",
                    "note": "",
                }
            )

    for flag_col, semantic_group in FLAG_FIELDS.items():
        if flag_col not in df.columns:
            rows.append(
                {
                    "case_id": case_id,
                    "ib1c_field": flag_col,
                    "semantic_key": "",
                    "semantic_value": "",
                    "observed_count": 0,
                    "mapping_key": "",
                    "has_mapping": False,
                    "value_kind": "flag",
                    "note": "flag_field_missing_in_ib1c_output",
                }
            )
            continue
        exploded: list[str] = []
        for value in df[flag_col]:
            exploded.extend(split_flag_value(value))
        if not exploded:
            continue
        vc = pd.Series(exploded).value_counts()
        for value, count in vc.items():
            source_field = FLAG_VALUE_TO_SOURCE_FIELD.get(value, value)
            key, has_mapping = matching_key_for_flag(source_field, value, keys)
            rows.append(
                {
                    "case_id": case_id,
                    "ib1c_field": flag_col,
                    "semantic_key": source_field,
                    "semantic_value": value,
                    "observed_count": int(count),
                    "mapping_key": key,
                    "has_mapping": has_mapping,
                    "value_kind": "flag",
                    "note": f"flag_group={semantic_group}",
                }
            )
    return pd.DataFrame(rows)


def risk_summary_metrics(case_id: str) -> dict[str, object]:
    fp = risk_summary_csv(case_id)
    if not fp.exists():
        return {"risk_summary_present": False}
    summary = pd.read_csv(fp, encoding="utf-8-sig")
    metrics = dict(zip(summary["metric"].astype(str), summary["value"]))
    return {
        "risk_summary_present": True,
        "rows": metrics.get("rows", ""),
        "osm_semantic_risk_score_min": metrics.get("osm_semantic_risk_score_min", ""),
        "osm_semantic_risk_score_mean": metrics.get("osm_semantic_risk_score_mean", ""),
        "osm_semantic_risk_score_max": metrics.get("osm_semantic_risk_score_max", ""),
    }


def classify_value(semantic_key: str, semantic_value: str, observed_cases: set[str]) -> dict[str, object]:
    is_null_like = semantic_value in {"", "unknown"}
    is_binary_absence = semantic_value == "no"
    is_typo_like = False
    score = 0.10
    band = "low"
    reason = "Unmapped support/context value; add conservative baseline mapping if accepted."
    confidence = "medium"
    manual = True

    if semantic_key in {"guidepost", "trailhead", "peak", "bench", "toilets", "drinking_water", "information_office", "picnic_site"}:
        score = 0.00
        band = "low"
        reason = "Nearby facility/landmark support context; should usually reduce uncertainty or remain neutral."
        confidence = "medium"
    elif semantic_key in {"wetland", "water_area", "waterway"}:
        score = 0.45
        band = "moderate"
        reason = "Hydrology proximity can increase wet/slip/exposure context in baseline route risk."
        confidence = "medium"
    elif semantic_key in {"cliff", "scree", "bare_rock", "landslide"}:
        score = 0.65
        band = "high"
        reason = "Hazard proximity should contribute to baseline route risk."
        confidence = "medium"
    elif semantic_key in {"steps", "rungs", "ladder", "via_ferrata", "assisted_trail"}:
        score = 0.45
        band = "moderate"
        reason = "Technical/assisted trail feature can raise effort or technical risk."
        confidence = "medium"
    elif semantic_key in {"lit", "bridge", "ford", "tunnel", "handrail", "safety_rope"}:
        score = 0.20
        band = "moderate"
        reason = "Route structure/safety feature; requires manual interpretation for risk direction."
        confidence = "low"

    if is_binary_absence:
        score = 0.00
        band = "low"
        reason = "Binary absence value; add neutral global mapping only if coverage accounting should treat explicit no as mapped."
        confidence = "low"
        manual = True
    if semantic_value in {"unknown"}:
        reason = "Unknown value is valid uncertainty, not a typo; map only if the risk model should score missing OSM detail explicitly."
        confidence = "low"
        manual = True
    elif is_null_like:
        reason = "Null-like or binary value; verify semantics before global mapping."
        confidence = "low"
        manual = True

    return {
        "proposed_risk_score": score,
        "proposed_risk_band": band,
        "proposal_reason": reason,
        "confidence": confidence,
            "needs_manual_review": manual,
        "is_legacy_typo_null_unknown": is_null_like or is_typo_like,
        "is_binary_absence": is_binary_absence,
        "should_add_global_mapping": "yes" if observed_cases else "review",
    }


def write_outputs(mapping_csv: Path, out_root: Path) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    mapping_df = pd.read_csv(mapping_csv, low_memory=False)
    keys = mapping_keys(mapping_df)

    coverage_parts = [observed_values_for_case(case_id, keys) for case_id in CASES]
    coverage = pd.concat(coverage_parts, ignore_index=True)
    observed = coverage[coverage["observed_count"] > 0].copy()
    unmapped = observed[~observed["has_mapping"]].copy()

    case_rows: list[dict[str, object]] = []
    for case_id, case_df in observed.groupby("case_id"):
        mapped_n = int(case_df["has_mapping"].sum())
        total_n = int(len(case_df))
        case_unmapped = int(total_n - mapped_n)
        row = {
            "case_id": case_id,
            "observed_semantic_values_n": total_n,
            "mapped_semantic_values_n": mapped_n,
            "unmapped_semantic_values_n": case_unmapped,
            "mapping_coverage_rate": mapped_n / total_n if total_n else 0.0,
            "formal_semantics_input_root": str(SEMANTICS_ROOT),
            "formal_semantic_risk_output_root": str(RISK_ROOT),
            "mapping_config": str(mapping_csv),
        }
        row.update(risk_summary_metrics(case_id))
        case_rows.append(row)
    case_coverage = pd.DataFrame(case_rows).sort_values("case_id")

    unique_rows: list[dict[str, object]] = []
    for (semantic_key, semantic_value), group in unmapped.groupby(["semantic_key", "semantic_value"]):
        cases = sorted(group["case_id"].unique())
        observed_cases = set(cases)
        attrs = classify_value(semantic_key, semantic_value, observed_cases)
        unique_rows.append(
            {
                "semantic_key": semantic_key,
                "semantic_value": semantic_value,
                "observed_cases": "|".join(cases),
                "observed_case_count": len(cases),
                "observed_count": int(group["observed_count"].sum()),
                "ib1c_fields": "|".join(sorted(group["ib1c_field"].unique())),
                "value_kind": "|".join(sorted(group["value_kind"].unique())),
                "only_juansi": cases == ["juansi_waterfall_fitcsv_20260503_osmrefresh_v1_3b"],
                "only_zhonghua": cases == ["zhonghua_ust_jiuwufeng_roundtrip_biji_osmrefresh_v1_3b"],
                "also_xiaoyoukeng": "qixing_xiaoyoukeng_main_peak_20260315_osmrefresh_v1_3b" in observed_cases,
                **attrs,
            }
        )
    unique_columns = [
        "semantic_key",
        "semantic_value",
        "observed_cases",
        "observed_case_count",
        "observed_count",
        "ib1c_fields",
        "value_kind",
        "only_juansi",
        "only_zhonghua",
        "also_xiaoyoukeng",
        "proposed_risk_score",
        "proposed_risk_band",
        "proposal_reason",
        "confidence",
        "needs_manual_review",
        "is_legacy_typo_null_unknown",
        "is_binary_absence",
        "should_add_global_mapping",
    ]
    unique = pd.DataFrame(unique_rows, columns=unique_columns)
    if not unique.empty:
        unique = unique.sort_values(["observed_case_count", "observed_count"], ascending=[False, False])

    patch = unique[
        [
            "semantic_key",
            "semantic_value",
            "observed_cases",
            "observed_count",
            "proposed_risk_score",
            "proposed_risk_band",
            "proposal_reason",
            "confidence",
            "needs_manual_review",
        ]
    ].copy()

    case_coverage.to_csv(out_root / "ib1c_semantic_risk_mapping_case_coverage.csv", index=False, encoding="utf-8-sig")
    unmapped.to_csv(out_root / "ib1c_semantic_risk_unmapped_values_by_case.csv", index=False, encoding="utf-8-sig")
    unique.to_csv(out_root / "ib1c_semantic_risk_unmapped_values_unique.csv", index=False, encoding="utf-8-sig")
    patch.to_csv(out_root / "osm_semantic_risk_mapping_v1_patch_proposal.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# IB1C semantic risk mapping coverage audit v1.3b",
        "",
        f"- formal_semantics_input_root: `{SEMANTICS_ROOT}`",
        f"- formal_semantic_risk_output_root: `{RISK_ROOT}`",
        f"- mapping_config: `{mapping_csv}`",
        "- mapping_config_scope: shared global table for all routes in this branch",
        "- mapping_table_modified: False",
        "",
        "## Case Coverage",
        "",
        "| case_id | coverage | mapped | unmapped | observed_values |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in case_coverage.iterrows():
        lines.append(
            f"| {row['case_id']} | {float(row['mapping_coverage_rate']):.6f} | {int(row['mapped_semantic_values_n'])} | {int(row['unmapped_semantic_values_n'])} | {int(row['observed_semantic_values_n'])} |"
        )

    def bullet_values(title: str, df: pd.DataFrame) -> None:
        lines.extend(["", f"## {title}", ""])
        if df.empty:
            lines.append("- none")
            return
        for _, row in df.iterrows():
            lines.append(
                f"- `{row['semantic_key']}={row['semantic_value']}` count={int(row['observed_count'])} cases={row['observed_cases']}"
            )

    lines.extend(["", "## Unmapped Values By Case", ""])
    for case_id in CASES:
        case_unmapped = unmapped[unmapped["case_id"] == case_id].sort_values(["semantic_key", "semantic_value"])
        lines.append(f"### {case_id}")
        if case_unmapped.empty:
            lines.append("- none")
        else:
            for _, row in case_unmapped.iterrows():
                lines.append(
                    f"- field=`{row['ib1c_field']}` key=`{row['semantic_key']}` value=`{row['semantic_value']}` count={int(row['observed_count'])}"
                )
        lines.append("")

    bullet_values("Unique Unmapped Values", unique)
    bullet_values("Only In Juansi", unique[unique["only_juansi"] == True])
    bullet_values("Only In Zhonghua", unique[unique["only_zhonghua"] == True])
    bullet_values("Also In Xiaoyoukeng", unique[unique["also_xiaoyoukeng"] == True])

    lines.extend(["", "## Interpretation", ""])
    if unique.empty:
        lines.extend(
            [
                "- This mapping config covers all observed semantic key/value pairs for the four v1.3b cases.",
                "- No unmapped values remain under the current audit logic.",
                "- Patch proposal is intentionally empty because no additional mapping rows are needed for coverage.",
                "- The current mapping table was not modified by this audit.",
            ]
        )
    else:
        lines.extend(
            [
                "- The coverage WARN is caused by observed semantic key/value pairs that are not covered by the global mapping table.",
                "- The current unmapped values are not obvious legacy roots or typos. They are valid OSM-derived surface, facility/context, or route-structure values.",
                "- `handrail=no` is a binary absence value. It can be added as a neutral mapping for coverage accounting, or excluded by audit policy; it should not be treated as observed weather or as direct hazard by itself.",
                "- `unknown` is a valid uncertainty value, not a typo, but it needs manual policy before global scoring.",
                "- Mapping should be patched only after manual review of the proposal CSV.",
                "- The current mapping table was not modified.",
            ]
        )

    lines.extend(
        [
            "",
            "## Patch Proposal",
            "",
            f"- proposal_csv: `{out_root / 'osm_semantic_risk_mapping_v1_patch_proposal.csv'}`",
            "- recommended_action: no action needed when proposal CSV has only a header row; otherwise review proposal rows before changing the global mapping table.",
            "- ib2d_blocker: False",
        ]
    )
    (out_root / "ib1c_semantic_risk_mapping_coverage_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("mapping config:", mapping_csv)
    print("case coverage:", out_root / "ib1c_semantic_risk_mapping_case_coverage.csv")
    print("unmapped by case:", out_root / "ib1c_semantic_risk_unmapped_values_by_case.csv")
    print("unique unmapped:", out_root / "ib1c_semantic_risk_unmapped_values_unique.csv")
    print("patch proposal:", out_root / "osm_semantic_risk_mapping_v1_patch_proposal.csv")
    print("summary:", out_root / "ib1c_semantic_risk_mapping_coverage_summary.md")


if __name__ == "__main__":
    args = parse_args()
    write_outputs(Path(args.mapping_csv), Path(args.out_root))
