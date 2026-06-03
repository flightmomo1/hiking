from __future__ import annotations

import argparse
import csv
import subprocess
from datetime import datetime
from pathlib import Path


"""
ib3_batch_run_juansi_activities.py

Purpose:
- Batch-run Juansi Waterfall activity analysis for multiple FIT CSV files.
- Reads activity_input/manifests/juansi_waterfall_activities.csv by default.
- Can also read another manifest via --manifest.
- Runs ib3a_mapmatch_highfreq_activity.py for each included activity.
- Runs ib3b_plot_mapmatched_activity_profile.py for each included activity.
- Writes a batch run status CSV.

Important:
- This runner assumes ib3a and ib3b support CLI arguments:
  ib3a:
    --case-id
    --activity-id
    --user-id
    --activity-fp
    --activity-type
    --out-dir

  ib3b:
    --case-id
    --activity-id
    --user-id
    --activity-core-csv
    --out-dir

If your ib3a / ib3b scripts do not yet support these arguments, update them first.
"""


CASE_ID = "juansi_waterfall_fitcsv_20260503"


def parse_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=None)
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def norm_include_flag(value) -> bool:
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "include"}


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def bool_series(s):
    return s.astype(str).str.lower().isin(["true", "1", "yes"])


def first_value(df, col, default=""):
    if col in df.columns and df[col].notna().any():
        return df[col].dropna().iloc[0]
    return default


def row_activity_relpath(row: dict) -> str:
    """
    Manifest 相容欄位：
    - activity_fp: 通用活動檔路徑，支援 .csv / .gpx
    - activity_csv: 舊欄位，保留給既有 FIT CSV manifest
    """
    return (
        row.get("activity_fp", "")
        or row.get("activity_csv", "")
        or row.get("activity_gpx", "")
    ).strip()


def row_activity_type(row: dict, activity_fp: Path) -> str:
    activity_type = row.get("activity_type", "").strip().lower()
    if activity_type:
        return activity_type

    suffix = activity_fp.suffix.lower()
    if suffix == ".gpx":
        return "gpx"
    if suffix == ".csv":
        return "csv"

    return "auto"


def build_ib3a_core_quality_summary(root: Path, manifest_rows: list[dict], out_dir: Path) -> Path:
    out_fp = out_dir / "juansi_waterfall_ib3a_core_quality_summary.csv"
    summary_rows = []

    for row in manifest_rows:
        activity_id = row["activity_id"].strip()
        user_id = row["user_id"].strip()
        case_id = row.get("case_id", CASE_ID).strip() or CASE_ID

        core_fp = (
            root
            / "outputs"
            / "ib3a_mapmatched_activity"
            / case_id
            / activity_id
            / f"{activity_id}_activity_mapmatched_core.csv"
        )

        full_fp = (
            root
            / "outputs"
            / "ib3a_mapmatched_activity"
            / case_id
            / activity_id
            / f"{activity_id}_activity_mapmatched.csv"
        )

        q = {
            "activity_id": activity_id,
            "user_id": user_id,
            "activity_fp": row_activity_relpath(row),
            "activity_csv": row.get("activity_csv", ""),
            "core_exists": core_fp.exists(),
            "full_exists": full_fp.exists(),
        }

        if not core_fp.exists():
            q["status"] = "missing_core"
            summary_rows.append(q)
            continue

        df = __import__("pandas").read_csv(core_fp, low_memory=False)
        q["status"] = "ok"
        q["core_rows"] = len(df)

        gatekeeper_cols = [
            "activity_quality_group",
            "route_coverage_group",
            "route_coverage_ratio",
            "speed_quality_group",
            "speed_capped_ratio",
            "hr_quality_group",
            "hr_valid_ratio",
        ]

        for col in gatekeeper_cols:
            q[col] = first_value(df, col, "")

        if len(df) > 0 and "route_dist_m" in df.columns:
            q["route_dist_min_m"] = df["route_dist_m"].min()
            q["route_dist_max_m"] = df["route_dist_m"].max()

            route_length_m = (
                df["route_length_m"].dropna().iloc[0]
                if "route_length_m" in df.columns and df["route_length_m"].notna().any()
                else 3964.4389
            )
            q["route_length_m"] = route_length_m
            q["computed_route_coverage_ratio"] = (
                q["route_dist_max_m"] - q["route_dist_min_m"]
            ) / route_length_m

        if len(df) > 0 and "offset_to_mainline_m" in df.columns:
            q["offset_mean_m"] = df["offset_to_mainline_m"].mean()
            q["offset_median_m"] = df["offset_to_mainline_m"].median()
            q["offset_p95_m"] = df["offset_to_mainline_m"].quantile(0.95)
            q["offset_max_m"] = df["offset_to_mainline_m"].max()

        if len(df) > 0 and "speed_capped" in df.columns:
            speed_capped = bool_series(df["speed_capped"])
            q["speed_capped_n"] = int(speed_capped.sum())
            q["computed_speed_capped_ratio"] = float(speed_capped.mean())

        if len(df) > 0 and "raw_speed_mps" in df.columns:
            q["raw_speed_mean_mps"] = df["raw_speed_mps"].mean()
            q["raw_speed_p95_mps"] = df["raw_speed_mps"].quantile(0.95)
            q["raw_speed_max_mps"] = df["raw_speed_mps"].max()

        if len(df) > 0 and "forward_speed_route_mps" in df.columns:
            q["route_speed_mean_mps"] = df["forward_speed_route_mps"].mean()
            q["route_speed_p95_mps"] = df["forward_speed_route_mps"].quantile(0.95)
            q["route_speed_max_mps"] = df["forward_speed_route_mps"].max()

        if len(df) > 0 and "raw_hr_bpm" in df.columns:
            q["hr_valid_n"] = int(df["raw_hr_bpm"].notna().sum())
            q["computed_hr_valid_ratio"] = float(df["raw_hr_bpm"].notna().mean())
            q["hr_mean_bpm"] = df["raw_hr_bpm"].mean()
            q["hr_p95_bpm"] = df["raw_hr_bpm"].quantile(0.95)
            q["hr_max_bpm"] = df["raw_hr_bpm"].max()

        if "match_quality" in df.columns:
            vc = df["match_quality"].value_counts(dropna=False)
            for k, v in vc.items():
                q[f"match_{k}"] = int(v)

        summary_rows.append(q)

    import pandas as pd

    qa = pd.DataFrame(summary_rows)

    preferred_cols = [
        "activity_id",
        "user_id",
        "status",
        "activity_fp",
        "activity_csv",
        "core_exists",
        "full_exists",
        "core_rows",
        "activity_quality_group",
        "route_coverage_group",
        "route_coverage_ratio",
        "computed_route_coverage_ratio",
        "speed_quality_group",
        "speed_capped_ratio",
        "computed_speed_capped_ratio",
        "hr_quality_group",
        "hr_valid_ratio",
        "computed_hr_valid_ratio",
        "route_dist_min_m",
        "route_dist_max_m",
        "route_length_m",
        "offset_mean_m",
        "offset_median_m",
        "offset_p95_m",
        "offset_max_m",
        "speed_capped_n",
        "raw_speed_mean_mps",
        "raw_speed_p95_mps",
        "raw_speed_max_mps",
        "route_speed_mean_mps",
        "route_speed_p95_mps",
        "route_speed_max_mps",
        "hr_valid_n",
        "hr_mean_bpm",
        "hr_p95_bpm",
        "hr_max_bpm",
    ]

    cols = [c for c in preferred_cols if c in qa.columns] + [
        c for c in qa.columns if c not in preferred_cols
    ]

    qa = qa[cols]
    qa.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print()
    print("ib3a core quality summary:", out_fp)
    print("summary rows:", len(qa))

    if {
        "activity_id",
        "activity_quality_group",
        "route_coverage_group",
        "speed_quality_group",
        "hr_quality_group",
    }.issubset(qa.columns):
        print(
            qa[
                [
                    "activity_id",
                    "core_rows",
                    "activity_quality_group",
                    "route_coverage_group",
                    "speed_quality_group",
                    "hr_quality_group",
                ]
            ].to_string(index=False)
        )

    return out_fp


def main() -> None:
    args = parse_cli_args()

    root = project_root()
    python_exe = root / ".venv" / "Scripts" / "python.exe"

    manifest_fp = (
        Path(args.manifest)
        if args.manifest
        else root / "activity_input" / "manifests" / "juansi_waterfall_activities.csv"
    )

    ib3a_script = (
        root
        / "scripts"
        / "ib3_activity_environment"
        / "ib3a_mapmatch_highfreq_activity.py"
    )

    ib3b_script = (
        root
        / "scripts"
        / "ib3_activity_environment"
        / "ib3b_plot_mapmatched_activity_profile.py"
    )

    batch_out_dir = (
        root
        / "outputs"
        / "ib3_batch_runs"
        / CASE_ID
    )
    batch_out_dir.mkdir(parents=True, exist_ok=True)

    run_status_fp = batch_out_dir / "juansi_waterfall_ib3_batch_status.csv"

    required_files = [
        python_exe,
        manifest_fp,
        ib3a_script,
        ib3b_script,
    ]

    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required files:\n" + "\n".join(missing))

    rows = []
    with manifest_fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if norm_include_flag(row.get("include_flag", "")):
                rows.append(row)

    if not rows:
        raise ValueError(f"No included activities in manifest: {manifest_fp}")

    status_rows = []

    print("case:", CASE_ID)
    print("manifest:", manifest_fp)
    print("included activities:", len(rows))
    print("ib3a:", ib3a_script)
    print("ib3b:", ib3b_script)
    print()

    for idx, row in enumerate(rows, start=1):
        activity_id = row["activity_id"].strip()
        user_id = row["user_id"].strip()
        case_id = row.get("case_id", CASE_ID).strip() or CASE_ID
        activity_rel = row_activity_relpath(row)
        if not activity_rel:
            raise ValueError(
                f"manifest row 缺少 activity_fp / activity_csv / activity_gpx: {row}"
            )

        activity_fp = root / activity_rel
        activity_type = row_activity_type(row, activity_fp)

        ib3a_out_dir = (
            root
            / "outputs"
            / "ib3a_mapmatched_activity"
            / case_id
            / activity_id
        )

        ib3b_out_dir = (
            root
            / "outputs"
            / "ib3b_mapmatched_activity_profile"
            / case_id
            / activity_id
        )

        activity_core_csv = ib3a_out_dir / f"{activity_id}_activity_mapmatched_core.csv"

        print("=" * 72)
        print(f"[{idx}/{len(rows)}] {activity_id} / {user_id}")
        print("activity:", activity_fp)

        started_at = datetime.now().isoformat(timespec="seconds")

        status = {
            "activity_id": activity_id,
            "user_id": user_id,
            "case_id": case_id,
            "activity_fp": activity_rel,
            "activity_csv": row.get("activity_csv", ""),
            "activity_type": activity_type,
            "started_at": started_at,
            "ib3a_status": "",
            "ib3b_status": "",
            "ib3a_returncode": "",
            "ib3b_returncode": "",
            "ib3a_out_dir": str(ib3a_out_dir.relative_to(root)).replace("\\", "/"),
            "ib3b_out_dir": str(ib3b_out_dir.relative_to(root)).replace("\\", "/"),
            "note": "",
        }

        if not activity_fp.exists():
            status["ib3a_status"] = "skipped"
            status["ib3b_status"] = "skipped"
            status["note"] = f"activity file not found: {activity_fp}"
            status_rows.append(status)
            print("SKIP:", status["note"])
            continue

        ib3a_cmd = [
            str(python_exe),
            str(ib3a_script),
            "--case-id", case_id,
            "--activity-id", activity_id,
            "--user-id", user_id,
            "--activity-fp", str(activity_fp),
            "--activity-type", activity_type,
            "--out-dir", str(ib3a_out_dir),
        ]

        rc_a, out_a, err_a = run_cmd(ib3a_cmd, cwd=root)
        status["ib3a_returncode"] = rc_a
        if rc_a == 0:
            status["ib3a_status"] = "ok"
            print("ib3a: OK")
        else:
            status["ib3a_status"] = "failed"
            status["ib3b_status"] = "skipped"
            status["note"] = "ib3a failed"
            print("ib3a: FAILED")
            print(out_a)
            print(err_a)
            status_rows.append(status)
            continue

        if not activity_core_csv.exists():
            status["ib3b_status"] = "skipped"
            status["note"] = f"core CSV not found after ib3a: {activity_core_csv}"
            print("ib3b: SKIP:", status["note"])
            status_rows.append(status)
            continue

        try:
            import pandas as pd

            core_check = pd.read_csv(activity_core_csv, nrows=1)
            if core_check.empty:
                status["ib3b_status"] = "skipped_no_route_core"
                status["note"] = f"core CSV is empty: {activity_core_csv}"
                print("ib3b: SKIP:", status["note"])
                status_rows.append(status)
                continue
        except Exception as e:
            status["ib3b_status"] = "skipped"
            status["note"] = f"failed to inspect core CSV: {e}"
            print("ib3b: SKIP:", status["note"])
            status_rows.append(status)
            continue

        ib3b_cmd = [
            str(python_exe),
            str(ib3b_script),
            "--case-id", case_id,
            "--activity-id", activity_id,
            "--user-id", user_id,
            "--activity-core-csv", str(activity_core_csv),
            "--out-dir", str(ib3b_out_dir),
        ]

        rc_b, out_b, err_b = run_cmd(ib3b_cmd, cwd=root)
        status["ib3b_returncode"] = rc_b
        if rc_b == 0:
            status["ib3b_status"] = "ok"
            print("ib3b: OK")
        else:
            status["ib3b_status"] = "failed"
            status["note"] = "ib3b failed"
            print("ib3b: FAILED")
            print(out_b)
            print(err_b)

        status_rows.append(status)

    with run_status_fp.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "activity_id",
            "user_id",
            "case_id",
            "activity_fp",
            "activity_csv",
            "activity_type",
            "started_at",
            "ib3a_status",
            "ib3b_status",
            "ib3a_returncode",
            "ib3b_returncode",
            "ib3a_out_dir",
            "ib3b_out_dir",
            "note",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(status_rows)

    print()
    print("Batch done.")
    print("status CSV:", run_status_fp)

    ok_a = sum(1 for r in status_rows if r["ib3a_status"] == "ok")
    ok_b = sum(1 for r in status_rows if r["ib3b_status"] == "ok")
    print("ib3a ok:", ok_a, "/", len(status_rows))
    print("ib3b ok:", ok_b, "/", len(status_rows))

    build_ib3a_core_quality_summary(root, rows, batch_out_dir)


if __name__ == "__main__":
    main()
