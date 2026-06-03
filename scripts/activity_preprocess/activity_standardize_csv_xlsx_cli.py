from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


VALID_ACTIVITY_RE = re.compile(r"^(?P<subject_id>\d+)(?:-(?P<trial_id>\d+))?\.(?P<ext>csv|xlsx)$", re.IGNORECASE)
TAIWAN_LAT_MIN = 21.0
TAIWAN_LAT_MAX = 26.0
TAIWAN_LON_MIN = 119.0
TAIWAN_LON_MAX = 123.0
SEMICIRCLE_TO_DEG = 180.0 / (2**31)

OUTPUT_COLUMNS = [
    "route_folder",
    "subject_id",
    "trial_id",
    "activity_id",
    "timestamp_s",
    "elapsed_sec",
    "dt_sec",
    "duplicate_timestamp_flag",
    "irregular_interval_flag",
    "lat",
    "lon",
    "ele_m",
    "distance_m",
    "heart_rate_bpm",
    "source_file",
    "source_ext",
    "source_row_index",
]

MANIFEST_COLUMNS = [
    "route_folder",
    "subject_id",
    "trial_id",
    "activity_id",
    "source_file",
    "output_file",
    "rows_raw",
    "rows_valid",
    "has_time",
    "has_distance",
    "has_hr",
    "lat_min",
    "lat_max",
    "lon_min",
    "lon_max",
    "ele_min",
    "ele_max",
    "distance_max",
    "duration_sec",
    "dt_median_sec",
    "dt_mean_sec",
    "dt_min_sec",
    "dt_max_sec",
    "duplicate_timestamp_n",
    "duplicate_timestamp_ratio",
    "irregular_interval_ratio",
    "sampling_profile",
    "time_quality",
    "usable_for_time_model",
    "status",
    "error",
]

ERROR_COLUMNS = [
    "route_folder",
    "subject_id",
    "trial_id",
    "activity_id",
    "source_file",
    "source_ext",
    "stage",
    "error",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Standardize valid activity CSV/XLSX files into a common schema for "
            "map matching and feature engineering."
        )
    )
    parser.add_argument(
        "--inventory-csv",
        default="activity_input/activity_file_inventory_valid.csv",
        help="Path to activity_file_inventory_valid.csv.",
    )
    parser.add_argument(
        "--pairing-csv",
        default="activity_input/activity_subject_pairing_summary_v2.csv",
        help="Path to activity_subject_pairing_summary_v2.csv.",
    )
    parser.add_argument(
        "--input-root",
        default="activity_input/csv",
        help="Root folder containing route_folder activity files.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/activity_standardized",
        help="Output directory for standardized files and manifests.",
    )
    parser.add_argument(
        "--pair-status",
        default="paired_clean",
        help="Only process subjects with this pair_status. Other valid files are marked excluded.",
    )
    parser.add_argument(
        "--min-valid-points",
        type=int,
        default=10,
        help="Minimum valid lat/lon rows required for an output file to be marked valid.",
    )
    return parser.parse_args()


def project_path(path_like: str | Path) -> Path:
    return Path(path_like).expanduser()


def normalize_col(name: Any) -> str:
    return str(name).strip().lower()


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def first_existing_column(df: pd.DataFrame, exact: list[str], contains: list[str] | None = None) -> str | None:
    by_norm = {normalize_col(c): c for c in df.columns}
    for candidate in exact:
        col = by_norm.get(normalize_col(candidate))
        if col is not None:
            return col

    if not contains:
        return None

    for col in df.columns:
        norm = normalize_col(col)
        if any(token in norm for token in contains):
            return col
    return None


def read_activity_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, low_memory=False, encoding="cp950")
    if suffix == ".xlsx":
        try:
            return pd.read_excel(path)
        except ImportError as exc:
            try:
                return read_xlsx_first_sheet_basic(path)
            except Exception as fallback_exc:
                raise ImportError(
                    "Reading .xlsx requires openpyxl or another pandas Excel engine. "
                    f"The built-in fallback reader also failed: {fallback_exc}"
                ) from exc
    raise ValueError(f"Unsupported file extension: {suffix}")


def column_index_from_cell_ref(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return max(index - 1, 0)


def read_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for si in root.findall("x:si", ns):
        parts = [node.text or "" for node in si.findall(".//x:t", ns)]
        values.append("".join(parts))
    return values


def first_sheet_path(zf: zipfile.ZipFile) -> str:
    workbook_path = "xl/workbook.xml"
    rels_path = "xl/_rels/workbook.xml.rels"
    if workbook_path not in zf.namelist() or rels_path not in zf.namelist():
        return "xl/worksheets/sheet1.xml"

    workbook = ET.fromstring(zf.read(workbook_path))
    rels = ET.fromstring(zf.read(rels_path))
    main_ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    sheet = workbook.find("x:sheets/x:sheet", main_ns)
    if sheet is None:
        return "xl/worksheets/sheet1.xml"

    rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    for rel in rels.findall("r:Relationship", rel_ns):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    return "xl/worksheets/sheet1.xml"


def read_xlsx_first_sheet_basic(path: Path) -> pd.DataFrame:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared_strings = read_xlsx_shared_strings(zf)
        sheet_path = first_sheet_path(zf)
        if sheet_path not in zf.namelist():
            raise FileNotFoundError(f"{sheet_path} not found inside workbook")
        root = ET.fromstring(zf.read(sheet_path))

    rows: list[list[Any]] = []
    for row_node in root.findall(".//x:sheetData/x:row", ns):
        row_values: list[Any] = []
        for cell in row_node.findall("x:c", ns):
            cell_ref = cell.attrib.get("r", "")
            col_idx = column_index_from_cell_ref(cell_ref)
            while len(row_values) <= col_idx:
                row_values.append(pd.NA)

            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", ns)
            inline_node = cell.find("x:is/x:t", ns)
            value: Any = pd.NA
            if cell_type == "s" and value_node is not None:
                shared_idx = int(value_node.text or 0)
                value = shared_strings[shared_idx] if shared_idx < len(shared_strings) else pd.NA
            elif cell_type == "inlineStr" and inline_node is not None:
                value = inline_node.text or ""
            elif value_node is not None:
                value = value_node.text
            row_values[col_idx] = value
        rows.append(row_values)

    if not rows:
        return pd.DataFrame()

    width = max(len(row) for row in rows)
    normalized_rows = [row + [pd.NA] * (width - len(row)) for row in rows]
    header = [str(value).strip() if pd.notna(value) else f"Unnamed: {idx}" for idx, value in enumerate(normalized_rows[0])]
    return pd.DataFrame(normalized_rows[1:], columns=header)


def parse_valid_filename(path: Path) -> dict[str, Any] | None:
    match = VALID_ACTIVITY_RE.match(path.name)
    if not match:
        return None
    return {
        "subject_id": str(int(match.group("subject_id"))),
        "trial_id": int(match.group("trial_id") or 1),
        "source_ext": "." + match.group("ext").lower(),
    }


def make_activity_id(route_folder: str, subject_id: str, trial_id: int) -> str:
    return f"{route_folder}_{subject_id}_{trial_id}"


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["source_row_index"] = df.index

    time_col = first_existing_column(
        df,
        ["record.timestamp[s]"],
        ["timestamp", "time", "時間"],
    )
    out["timestamp_s"] = safe_numeric(df[time_col]) if time_col else pd.NA

    lat_col = first_existing_column(df, ["record.position_lat[semicircles]"])
    lon_col = first_existing_column(df, ["record.position_long[semicircles]"])
    if lat_col and lon_col:
        out["lat"] = safe_numeric(df[lat_col]) * SEMICIRCLE_TO_DEG
        out["lon"] = safe_numeric(df[lon_col]) * SEMICIRCLE_TO_DEG
    else:
        lat_col = first_existing_column(
            df,
            ["latitude", "lat"],
            ["latitude", "lat", "緯度"],
        )
        lon_col = first_existing_column(
            df,
            ["longitude", "lon", "lng"],
            ["longitude", "lon", "lng", "經度"],
        )
        out["lat"] = safe_numeric(df[lat_col]) if lat_col else pd.NA
        out["lon"] = safe_numeric(df[lon_col]) if lon_col else pd.NA

    ele_col = first_existing_column(
        df,
        ["record.altitude[m]", "record.enhanced_altitude[m]"],
        ["altitude", "elevation", "ele", "海拔", "高度"],
    )
    out["ele_m"] = safe_numeric(df[ele_col]) if ele_col else pd.NA

    distance_col = first_existing_column(
        df,
        ["record.distance[m]"],
        ["distance", "dist", "距離"],
    )
    out["distance_m"] = safe_numeric(df[distance_col]) if distance_col else pd.NA

    hr_col = first_existing_column(
        df,
        ["record.heart_rate[bpm]"],
        ["heart_rate", "hr", "心率", "心跳"],
    )
    out["heart_rate_bpm"] = safe_numeric(df[hr_col]) if hr_col else pd.NA
    return out


def clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.dropna(subset=["lat", "lon"]).copy()
    return out[
        out["lat"].between(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX)
        & out["lon"].between(TAIWAN_LON_MIN, TAIWAN_LON_MAX)
    ].copy()


def add_time_quality(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    out["timestamp_s"] = safe_numeric(out["timestamp_s"])
    has_time = bool(out["timestamp_s"].notna().any())

    metrics: dict[str, Any] = {
        "has_time": has_time,
        "duration_sec": np.nan,
        "dt_median_sec": np.nan,
        "dt_mean_sec": np.nan,
        "dt_min_sec": np.nan,
        "dt_max_sec": np.nan,
        "duplicate_timestamp_n": 0,
        "duplicate_timestamp_ratio": np.nan,
        "irregular_interval_ratio": np.nan,
        "sampling_profile": "no_timestamp",
        "time_quality": "no_timestamp",
        "usable_for_time_model": False,
    }

    out["elapsed_sec"] = pd.NA
    out["dt_sec"] = pd.NA
    out["duplicate_timestamp_flag"] = 0
    out["irregular_interval_flag"] = 0

    if not has_time:
        return out.reset_index(drop=True), metrics

    timed = out[out["timestamp_s"].notna()].copy()
    untimed = out[out["timestamp_s"].isna()].copy()
    timed = timed.sort_values(["timestamp_s", "source_row_index"], kind="mergesort")
    out = pd.concat([timed, untimed], ignore_index=True)

    timed_mask = out["timestamp_s"].notna()
    first_ts = out.loc[timed_mask, "timestamp_s"].iloc[0]
    out.loc[timed_mask, "elapsed_sec"] = out.loc[timed_mask, "timestamp_s"] - first_ts
    out.loc[timed_mask, "dt_sec"] = out.loc[timed_mask, "timestamp_s"].diff()

    duplicate_mask = out.loc[timed_mask, "timestamp_s"].duplicated(keep=False)
    out.loc[timed_mask, "duplicate_timestamp_flag"] = duplicate_mask.astype(int).to_numpy()

    dt = safe_numeric(out.loc[timed_mask, "dt_sec"])
    irregular_mask = dt.notna() & ((dt < 0.5) | (dt > 1.5))
    out.loc[timed_mask, "irregular_interval_flag"] = irregular_mask.astype(int).to_numpy()

    valid_dt = dt.dropna()
    duplicate_n = int(out.loc[timed_mask, "duplicate_timestamp_flag"].sum())
    irregular_ratio = float(out.loc[timed_mask, "irregular_interval_flag"].mean()) if int(timed_mask.sum()) else np.nan
    duplicate_ratio = duplicate_n / int(timed_mask.sum()) if int(timed_mask.sum()) else np.nan

    if not valid_dt.empty:
        metrics.update(
            {
                "duration_sec": float(out.loc[timed_mask, "elapsed_sec"].max()),
                "dt_median_sec": float(valid_dt.median()),
                "dt_mean_sec": float(valid_dt.mean()),
                "dt_min_sec": float(valid_dt.min()),
                "dt_max_sec": float(valid_dt.max()),
            }
        )

    metrics["duplicate_timestamp_n"] = duplicate_n
    metrics["duplicate_timestamp_ratio"] = duplicate_ratio
    metrics["irregular_interval_ratio"] = irregular_ratio

    median_dt = metrics["dt_median_sec"]

    if out.loc[timed_mask, "timestamp_s"].isna().any() or out.loc[timed_mask, "elapsed_sec"].isna().all():
        profile = "invalid_time"
        quality = "invalid_time"
        usable = False
    elif valid_dt.empty:
        profile = "invalid_time"
        quality = "invalid_time"
        usable = False
    elif pd.notna(median_dt) and (median_dt < 0.5 or duplicate_ratio > 0.10):
        profile = "high_frequency"
        quality = "irregular" if duplicate_n > 0 or irregular_ratio > 0.05 else "ok"
        usable = True
    elif pd.notna(median_dt) and median_dt > 1.5:
        profile = "low_frequency"
        quality = "irregular" if irregular_ratio > 0.05 else "ok"
        usable = True
    elif duplicate_n > 0 or irregular_ratio > 0.05:
        profile = "irregular"
        quality = "irregular"
        usable = True
    else:
        profile = "regular_1hz"
        quality = "ok"
        usable = True

    metrics["sampling_profile"] = profile
    metrics["time_quality"] = quality
    metrics["usable_for_time_model"] = usable
    return out.reset_index(drop=True), metrics


def base_manifest_row(route_folder: str, subject_id: str, trial_id: int, source_file: str) -> dict[str, Any]:
    activity_id = make_activity_id(route_folder, subject_id, trial_id)
    return {
        "route_folder": route_folder,
        "subject_id": subject_id,
        "trial_id": trial_id,
        "activity_id": activity_id,
        "source_file": source_file,
        "output_file": "",
        "rows_raw": 0,
        "rows_valid": 0,
        "has_time": False,
        "has_distance": False,
        "has_hr": False,
        "lat_min": np.nan,
        "lat_max": np.nan,
        "lon_min": np.nan,
        "lon_max": np.nan,
        "ele_min": np.nan,
        "ele_max": np.nan,
        "distance_max": np.nan,
        "duration_sec": np.nan,
        "dt_median_sec": np.nan,
        "dt_mean_sec": np.nan,
        "dt_min_sec": np.nan,
        "dt_max_sec": np.nan,
        "duplicate_timestamp_n": 0,
        "duplicate_timestamp_ratio": np.nan,
        "irregular_interval_ratio": np.nan,
        "sampling_profile": "invalid_time",
        "time_quality": "invalid_time",
        "usable_for_time_model": False,
        "status": "pending",
        "error": "",
    }


def summarize_manifest(row: dict[str, Any], cleaned: pd.DataFrame, time_metrics: dict[str, Any]) -> dict[str, Any]:
    row = row.copy()
    row.update(time_metrics)
    row["rows_valid"] = len(cleaned)
    row["has_distance"] = bool(cleaned["distance_m"].notna().any())
    row["has_hr"] = bool(cleaned["heart_rate_bpm"].notna().any())
    for src, dst in [
        ("lat", "lat_min"),
        ("lon", "lon_min"),
        ("ele_m", "ele_min"),
    ]:
        row[dst] = float(cleaned[src].min()) if cleaned[src].notna().any() else np.nan
    for src, dst in [
        ("lat", "lat_max"),
        ("lon", "lon_max"),
        ("ele_m", "ele_max"),
    ]:
        row[dst] = float(cleaned[src].max()) if cleaned[src].notna().any() else np.nan
    row["distance_max"] = float(cleaned["distance_m"].max()) if cleaned["distance_m"].notna().any() else np.nan
    return row


def process_file(
    source_path: Path,
    route_folder: str,
    subject_id: str,
    trial_id: int,
    out_dir: Path,
    min_valid_points: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    source_file = source_path.as_posix()
    activity_id = make_activity_id(route_folder, subject_id, trial_id)
    manifest = base_manifest_row(route_folder, subject_id, trial_id, source_file)
    source_ext = source_path.suffix.lower()

    try:
        raw = read_activity_file(source_path)
        manifest["rows_raw"] = len(raw)
        standardized = standardize_columns(raw)
        cleaned = clean_coordinates(standardized)
        cleaned, time_metrics = add_time_quality(cleaned)
        manifest = summarize_manifest(manifest, cleaned, time_metrics)

        if len(cleaned) < min_valid_points:
            manifest["status"] = "invalid_too_few_points"
            manifest["error"] = f"valid coordinate rows < {min_valid_points}"
            return manifest, {
                "route_folder": route_folder,
                "subject_id": subject_id,
                "trial_id": trial_id,
                "activity_id": activity_id,
                "source_file": source_file,
                "source_ext": source_ext,
                "stage": "validation",
                "error": manifest["error"],
            }

        output_folder = out_dir / route_folder
        output_folder.mkdir(parents=True, exist_ok=True)
        output_path = output_folder / f"{subject_id}_{trial_id}_standardized.csv"

        cleaned.insert(0, "activity_id", activity_id)
        cleaned.insert(0, "trial_id", trial_id)
        cleaned.insert(0, "subject_id", subject_id)
        cleaned.insert(0, "route_folder", route_folder)
        cleaned["source_file"] = source_file
        cleaned["source_ext"] = source_ext
        cleaned = cleaned[OUTPUT_COLUMNS]
        cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")

        manifest["output_file"] = output_path.as_posix()
        manifest["status"] = "standardized"
        return manifest, None
    except Exception as exc:
        manifest["status"] = "error"
        manifest["error"] = str(exc)
        return manifest, {
            "route_folder": route_folder,
            "subject_id": subject_id,
            "trial_id": trial_id,
            "activity_id": activity_id,
            "source_file": source_file,
            "source_ext": source_ext,
            "stage": "process_file",
            "error": str(exc),
        }


def load_inputs(inventory_csv: Path, pairing_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory = pd.read_csv(inventory_csv)
    pairing = pd.read_csv(pairing_csv)
    inventory["subject_id"] = inventory["subject_id"].astype(str)
    inventory["trial_id"] = inventory["trial_id"].fillna(1).astype(int)
    pairing["subject_id"] = pairing["subject_id"].astype(str)
    return inventory, pairing


def resolve_source_path(inv: dict[str, Any], input_root: Path) -> Path:
    source_path = project_path(inv["file"])
    if source_path.exists():
        return source_path
    route_folder = str(inv["route_folder"])
    return input_root / route_folder / Path(str(inv["file"])).name


def run(args: argparse.Namespace) -> int:
    inventory_csv = project_path(args.inventory_csv)
    pairing_csv = project_path(args.pairing_csv)
    input_root = project_path(args.input_root)
    out_dir = project_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory, pairing = load_inputs(inventory_csv, pairing_csv)
    status_by_subject = pairing.set_index("subject_id")["pair_status"].to_dict()

    manifest_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []

    for inv in inventory.to_dict("records"):
        source_path = resolve_source_path(inv, input_root)
        route_folder = str(inv["route_folder"])
        parsed = parse_valid_filename(source_path)
        if parsed is None:
            continue

        subject_id = str(inv.get("subject_id") or parsed["subject_id"])
        trial_id = int(inv.get("trial_id") or parsed["trial_id"])
        pair_status = status_by_subject.get(subject_id, "missing_pairing")

        if pair_status != args.pair_status:
            row = base_manifest_row(route_folder, subject_id, trial_id, source_path.as_posix())
            row["status"] = "excluded"
            row["error"] = f"pair_status={pair_status}"
            manifest_rows.append(row)
            continue

        manifest, error = process_file(
            source_path=source_path,
            route_folder=route_folder,
            subject_id=subject_id,
            trial_id=trial_id,
            out_dir=out_dir,
            min_valid_points=args.min_valid_points,
        )
        manifest_rows.append(manifest)
        if error is not None:
            error_rows.append(error)

    manifest_df = pd.DataFrame(manifest_rows, columns=MANIFEST_COLUMNS)
    error_df = pd.DataFrame(error_rows, columns=ERROR_COLUMNS)

    manifest_path = out_dir / "activity_standardized_manifest.csv"
    error_path = out_dir / "activity_standardized_error_log.csv"
    manifest_df.to_csv(manifest_path, index=False, encoding="utf-8-sig")
    error_df.to_csv(error_path, index=False, encoding="utf-8-sig")

    status_counts = manifest_df["status"].value_counts(dropna=False).to_dict() if not manifest_df.empty else {}
    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote error log: {error_path}")
    print(f"Status counts: {status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
