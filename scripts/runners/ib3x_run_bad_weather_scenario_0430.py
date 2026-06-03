# -*- coding: utf-8 -*-
from pathlib import Path
import os
import shutil
import subprocess
import importlib.util
import pandas as pd


# =========================================================
# A. Scenario config
# =========================================================
SCENARIO_NAME = "bad_weather_0430"

# 假情境：2026/04/30 較差天候
SCENARIO_WEATHER_START_TIME = "2026-04-30T00:00:00+00:00"
SCENARIO_WEATHER_END_TIME = "2026-04-30T23:59:59+00:00"

SCENARIO_WATER_START_TIME = "2026-04-30T00:00:00+08:00"
SCENARIO_WATER_END_TIME = "2026-04-30T23:59:59+08:00"


# =========================================================
# B. Paths
# =========================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

PYTHON_EXE = Path("/Users/iddmini/.pyenv/versions/mountain-310/bin/python")

IB3B = SCRIPT_DIR / "ib3b_extract_environment_window.py"
IB3B2 = SCRIPT_DIR / "ib3b2_analyze_weather_station_update_frequency.py"
IB3C = SCRIPT_DIR / "ib3c_apply_environment_risk_adjustment.py"
IB3C2 = SCRIPT_DIR / "ib3c2_compare_weather_trend_adjustment.py"
IB3D = SCRIPT_DIR / "ib3d_plot_environment_adjusted_risk_profile.py"
IB3E = SCRIPT_DIR / "ib3e_extract_route_microclimate_terrain_features.py"
IB3F = SCRIPT_DIR / "ib3f_apply_weather_terrain_microclimate_interaction.py"
IB4B = SCRIPT_DIR / "ib4b_activity_route_risk_overlay.py"
IB4C = SCRIPT_DIR / "ib4c_personal_capability_score.py"

ENV_DIR = BASE_DIR / "ib3_environment_output"
ACT_DIR = BASE_DIR / "ib4_activity_output"

SCENARIO_DIR = BASE_DIR / "ib_scenario_output" / SCENARIO_NAME
BACKUP_DIR = BASE_DIR / "ib_scenario_output" / "_backup_before_scenario"


# =========================================================
# C. Files
# =========================================================
# 這些是會被重跑覆蓋的核心檔案。
# 若執行情境前原本存在，會備份並還原；
# 若原本不存在但情境流程產生，還原時會刪除，避免污染真實環境版。
FILES_TO_BACKUP_AND_RESTORE = [
    # ib3b outputs
    ENV_DIR / "qixing_weather_window.csv",
    ENV_DIR / "qixing_weather_summary_by_station.csv",
    ENV_DIR / "qixing_water_window.csv",
    ENV_DIR / "qixing_water_summary_by_station.csv",
    ENV_DIR / "qixing_environment_window_metadata.csv",

    # ib3b2 outputs
    ENV_DIR / "qixing_weather_station_update_profile.csv",
    ENV_DIR / "qixing_weather_trend_features.csv",
    ENV_DIR / "qixing_weather_data_quality_summary.csv",

    # ib3c outputs
    ENV_DIR / "qixing_environment_adjusted_risk.csv",
    ENV_DIR / "qixing_environment_adjusted_risk_summary.csv",

    # ib3c2 outputs
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend.csv",
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv",

    # ib3e outputs
    ENV_DIR / "qixing_route_microclimate_terrain_features.csv",
    ENV_DIR / "qixing_route_microclimate_terrain_features_summary.csv",

    # ib3f outputs
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction.csv",
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction_summary.csv",

    # ib3d outputs
    ENV_DIR / "qixing_environment_adjusted_risk_profile.png",
    ENV_DIR / "qixing_environment_adjusted_risk_plot_data.csv",

    # ib4b outputs
    ACT_DIR / "qixing_activity_risk_overlay_points.csv",
    ACT_DIR / "qixing_activity_risk_overlay_summary.csv",
    ACT_DIR / "qixing_activity_risk_overlay_profile.png",

    # ib4c outputs
    ACT_DIR / "qixing_personal_capability_score.csv",
]


# 情境結果要另外保存的檔案
FILES_TO_COPY_TO_SCENARIO = [
    # ib3b outputs
    ENV_DIR / "qixing_weather_window.csv",
    ENV_DIR / "qixing_weather_summary_by_station.csv",
    ENV_DIR / "qixing_water_window.csv",
    ENV_DIR / "qixing_water_summary_by_station.csv",
    ENV_DIR / "qixing_environment_window_metadata.csv",

    # ib3b2 outputs
    ENV_DIR / "qixing_weather_station_update_profile.csv",
    ENV_DIR / "qixing_weather_trend_features.csv",
    ENV_DIR / "qixing_weather_data_quality_summary.csv",

    # ib3c outputs
    ENV_DIR / "qixing_environment_adjusted_risk.csv",
    ENV_DIR / "qixing_environment_adjusted_risk_summary.csv",

    # ib3c2 outputs
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend.csv",
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv",

    # ib3d outputs
    ENV_DIR / "qixing_environment_adjusted_risk_profile.png",
    ENV_DIR / "qixing_environment_adjusted_risk_plot_data.csv",

    # ib3e outputs
    ENV_DIR / "qixing_route_microclimate_terrain_features.csv",
    ENV_DIR / "qixing_route_microclimate_terrain_features_summary.csv",

    # ib3f outputs
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction.csv",
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction_summary.csv",


    # ib4b outputs
    ACT_DIR / "qixing_activity_risk_overlay_points.csv",
    ACT_DIR / "qixing_activity_risk_overlay_summary.csv",
    ACT_DIR / "qixing_activity_risk_overlay_profile.png",

    # ib4c outputs
    ACT_DIR / "qixing_personal_capability_score.csv",
]


# 比較用 PNG
PNG_FILES_FOR_COMPARE = [
    ENV_DIR / "qixing_environment_adjusted_risk_profile.png",
    ACT_DIR / "qixing_activity_risk_overlay_profile.png",
]


# 比較用方法對照 CSV
METHOD_COMPARE_FILES = [
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend.csv",
    ENV_DIR / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv",
]

MICROCLIMATE_INTERACTION_FILES = [
    ENV_DIR / "qixing_route_microclimate_terrain_features.csv",
    ENV_DIR / "qixing_route_microclimate_terrain_features_summary.csv",
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction.csv",
    ENV_DIR / "qixing_weather_terrain_microclimate_interaction_summary.csv",
]

# =========================================================
# D. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def backup_current_outputs():
    """
    備份目前「真實環境版」輸出，避免被 scenario 覆蓋。
    """
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for fp in FILES_TO_BACKUP_AND_RESTORE:
        if fp.exists():
            rel = fp.relative_to(BASE_DIR)
            dst = BACKUP_DIR / rel
            copy_if_exists(fp, dst)

    print("已備份目前輸出到：", BACKUP_DIR.resolve())


def restore_current_outputs():
    """
    將 scenario 執行前的真實環境版輸出還原回去。
    若某檔案原本不存在但 scenario 產生了，還原時會刪除。
    """
    if not BACKUP_DIR.exists():
        print("警告：找不到備份資料夾，略過還原")
        return

    for fp in FILES_TO_BACKUP_AND_RESTORE:
        rel = fp.relative_to(BASE_DIR)
        backup_fp = BACKUP_DIR / rel

        if backup_fp.exists():
            copy_if_exists(backup_fp, fp)
        else:
            if fp.exists():
                fp.unlink()

    print("已還原原本輸出")


def load_module_from_path(module_name: str, path: Path):
    ensure_exists(path)

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)

    if spec.loader is None:
        raise RuntimeError(f"無法載入模組：{path}")

    spec.loader.exec_module(module)
    return module


def run_python_script(script_path: Path):
    ensure_exists(script_path)

    cmd = [str(PYTHON_EXE), str(script_path)]

    print("\n執行：", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
    )

    print(result.stdout)

    if result.stderr.strip():
        print("=== STDERR ===")
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"執行失敗：{script_path.name}")


def run_ib3b_with_bad_weather_scenario():
    """
    用 import 方式載入 ib3b，覆寫時間設定，再呼叫 main()。
    不需要手動修改原本 ib3b。
    """
    print("\n執行 ib3b 假情境：", SCENARIO_NAME)

    ib3b = load_module_from_path("ib3b_scenario_module", IB3B)

    # 覆寫 ib3b 的全域設定
    ib3b.USE_ACTIVITY_GPX_TIME = False

    ib3b.MANUAL_WEATHER_START_TIME = SCENARIO_WEATHER_START_TIME
    ib3b.MANUAL_WEATHER_END_TIME = SCENARIO_WEATHER_END_TIME

    ib3b.MANUAL_WATER_START_TIME = SCENARIO_WATER_START_TIME
    ib3b.MANUAL_WATER_END_TIME = SCENARIO_WATER_END_TIME

    # 讓 ib3b 內部相對路徑與原本一致
    old_cwd = Path.cwd()
    os.chdir(BASE_DIR)

    try:
        ib3b.main()
    finally:
        os.chdir(old_cwd)


def copy_scenario_outputs():
    """
    將 scenario 跑完後的輸出另存到獨立資料夾。
    """
    if SCENARIO_DIR.exists():
        shutil.rmtree(SCENARIO_DIR)

    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)

    for fp in FILES_TO_COPY_TO_SCENARIO:
        if fp.exists():
            rel = fp.relative_to(BASE_DIR)
            dst = SCENARIO_DIR / rel
            copy_if_exists(fp, dst)

    print("\n已保存假情境結果到：", SCENARIO_DIR.resolve())


def export_actual_and_scenario_pngs():
    """
    將 backup 中的真實環境版 PNG，以及目前 scenario 跑出的 PNG，
    一起整理到 SCENARIO_DIR / compare_pngs
    """
    compare_dir = SCENARIO_DIR / "compare_pngs"
    compare_dir.mkdir(parents=True, exist_ok=True)

    name_mapping = {
        "qixing_environment_adjusted_risk_profile.png": {
            "actual": "actual_qixing_environment_adjusted_risk_profile.png",
            "scenario": "scenario_qixing_environment_adjusted_risk_profile.png",
        },
        "qixing_activity_risk_overlay_profile.png": {
            "actual": "actual_qixing_activity_risk_overlay_profile.png",
            "scenario": "scenario_qixing_activity_risk_overlay_profile.png",
        },
    }

    for fp in PNG_FILES_FOR_COMPARE:
        rel = fp.relative_to(BASE_DIR)

        # backup 內的真實環境版
        actual_src = BACKUP_DIR / rel
        if actual_src.exists():
            actual_dst = compare_dir / name_mapping[fp.name]["actual"]
            shutil.copy2(actual_src, actual_dst)

        # 目前情境版
        scenario_src = fp
        if scenario_src.exists():
            scenario_dst = compare_dir / name_mapping[fp.name]["scenario"]
            shutil.copy2(scenario_src, scenario_dst)

    print("已整理比較用 PNG 到：", compare_dir.resolve())


def export_actual_and_scenario_method_compare_csvs():
    """
    將真實環境版與壞天氣情境版的 ib3c2 方法對照 CSV
    一起整理到 SCENARIO_DIR / compare_method_csvs
    """
    compare_dir = SCENARIO_DIR / "compare_method_csvs"
    compare_dir.mkdir(parents=True, exist_ok=True)

    for fp in METHOD_COMPARE_FILES:
        rel = fp.relative_to(BASE_DIR)

        # backup 內的真實環境版
        actual_src = BACKUP_DIR / rel
        if actual_src.exists():
            actual_dst = compare_dir / f"actual_{fp.name}"
            shutil.copy2(actual_src, actual_dst)

        # 目前情境版
        scenario_src = fp
        if scenario_src.exists():
            scenario_dst = compare_dir / f"scenario_{fp.name}"
            shutil.copy2(scenario_src, scenario_dst)

    print("已整理方法對照 CSV 到：", compare_dir.resolve())

def export_actual_and_scenario_microclimate_csvs():
    """
    將真實環境版與壞天氣情境版的 ib3e / ib3f 微氣候交互作用 CSV
    一起整理到 SCENARIO_DIR / compare_microclimate_csvs
    """
    compare_dir = SCENARIO_DIR / "compare_microclimate_csvs"
    compare_dir.mkdir(parents=True, exist_ok=True)

    for fp in MICROCLIMATE_INTERACTION_FILES:
        rel = fp.relative_to(BASE_DIR)

        # backup 內的真實環境版
        actual_src = BACKUP_DIR / rel
        if actual_src.exists():
            actual_dst = compare_dir / f"actual_{fp.name}"
            shutil.copy2(actual_src, actual_dst)

        # 目前情境版
        scenario_src = fp
        if scenario_src.exists():
            scenario_dst = compare_dir / f"scenario_{fp.name}"
            shutil.copy2(scenario_src, scenario_dst)

    print("已整理微氣候交互作用 CSV 到：", compare_dir.resolve())


def build_capability_comparison():
    """
    若 backup 中有實際天候版 capability，且 scenario 中有假情境 capability，
    自動產生一份前後比較表。
    """
    actual_fp = BACKUP_DIR / "ib4_activity_output" / "qixing_personal_capability_score.csv"
    scenario_fp = SCENARIO_DIR / "ib4_activity_output" / "qixing_personal_capability_score.csv"

    if not actual_fp.exists() or not scenario_fp.exists():
        print("警告：缺少 capability CSV，略過能力比較表")
        return

    actual_df = pd.read_csv(actual_fp)
    scenario_df = pd.read_csv(scenario_fp)

    if actual_df.empty or scenario_df.empty:
        print("警告：capability CSV 為空，略過能力比較表")
        return

    actual = actual_df.iloc[0].to_dict()
    scenario = scenario_df.iloc[0].to_dict()

    compare_keys = [
        "total_duration_min",
        "moving_duration_min",
        "total_distance_km",
        "total_gain_m",
        "moving_avg_speed_km_h",

        "max_300s_gain_m",
        "max_300s_vertical_speed_m_h",
        "max_300s_horizontal_distance_m",
        "max_300s_horizontal_speed_km_h",

        "stationary_count",
        "micro_rest_count",
        "micro_rest_duration_min",

        "duration_min_in_adjusted_high_or_above",
        "duration_min_in_adjusted_very_high",
        "duration_ratio_in_adjusted_high_or_above",
        "duration_ratio_in_adjusted_very_high",

        "environment_modifier_mean",
        "environment_modifier_max",

        "vertical_capability_score",
        "horizontal_capability_score",
        "pacing_stability_score",
        "rest_response_score",

        "scenario_passing_score",
        "environment_challenge_score",
        "environment_adaptation_score",
        "personal_capability_index",

        "overall_capability_class",
        "scenario_passing_class",
        "environment_challenge_class",
        "environment_adaptation_class",
    ]

    rows = []

    for key in compare_keys:
        actual_value = actual.get(key, "")
        scenario_value = scenario.get(key, "")

        row = {
            "metric": key,
            "actual_gpx_time": actual_value,
            SCENARIO_NAME: scenario_value,
        }

        try:
            av = float(actual_value)
            sv = float(scenario_value)
            row["delta_scenario_minus_actual"] = sv - av
        except Exception:
            row["delta_scenario_minus_actual"] = ""

        rows.append(row)

    compare_df = pd.DataFrame(rows)

    out_fp = SCENARIO_DIR / f"compare_actual_vs_{SCENARIO_NAME}.csv"
    compare_df.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print("能力比較表 CSV:", out_fp.resolve())

    print("\n=== key capability comparison ===")
    key_show = compare_df[
        compare_df["metric"].isin(
            [
                "duration_min_in_adjusted_high_or_above",
                "duration_min_in_adjusted_very_high",
                "environment_modifier_mean",
                "scenario_passing_score",
                "environment_challenge_score",
                "environment_adaptation_score",
                "personal_capability_index",
            ]
        )
    ]
    print(key_show.to_string(index=False))


def build_method_summary_comparison():
    """
    若真實環境版與情境版都有 ib3c2 summary，
    額外產生一份 method summary 對照表。
    """
    actual_fp = (
        BACKUP_DIR
        / "ib3_environment_output"
        / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv"
    )
    scenario_fp = (
        SCENARIO_DIR
        / "ib3_environment_output"
        / "qixing_environment_adjusted_risk_compare_weather_trend_summary.csv"
    )

    if not actual_fp.exists() or not scenario_fp.exists():
        print("警告：缺少 ib3c2 summary，略過方法摘要比較表")
        return

    actual_df = pd.read_csv(actual_fp)
    scenario_df = pd.read_csv(scenario_fp)

    if actual_df.empty or scenario_df.empty:
        print("警告：ib3c2 summary 為空，略過方法摘要比較表")
        return

    actual_map = dict(zip(actual_df["metric"], actual_df["value"]))
    scenario_map = dict(zip(scenario_df["metric"], scenario_df["value"]))

    compare_metrics = [
        "original_weather_rain_sum_mm",
        "original_weather_rain_factor",
        "trend_weather_observed_rain_factor",
        "trend_weather_pre_wetness_rain_mm",
        "trend_weather_pre_wetness_factor",
        "trend_weather_post_lag_rain_mm",
        "trend_weather_post_lag_rain_factor",
        "trend_weather_wetness_status_factor",
        "trend_weather_effective_wetness_factor",
        "original_weather_modifier_base",
        "trend_weather_modifier_base",

        "risk_score_delta_trend_minus_original_mean",
        "risk_score_delta_trend_minus_original_max",
        "modifier_delta_trend_minus_original_mean",
        "modifier_delta_trend_minus_original_max",
        "risk_band_changed_count",
        "risk_band_changed_ratio",

        "original_adjusted_band_count_low",
        "original_adjusted_band_count_moderate",
        "original_adjusted_band_count_high",
        "original_adjusted_band_count_very_high",

        "trend_adjusted_band_count_low",
        "trend_adjusted_band_count_moderate",
        "trend_adjusted_band_count_high",
        "trend_adjusted_band_count_very_high",
    ]

    rows = []

    for metric in compare_metrics:
        actual_value = actual_map.get(metric, "")
        scenario_value = scenario_map.get(metric, "")

        row = {
            "metric": metric,
            "actual_gpx_time": actual_value,
            SCENARIO_NAME: scenario_value,
        }

        try:
            av = float(actual_value)
            sv = float(scenario_value)
            row["delta_scenario_minus_actual"] = sv - av
        except Exception:
            row["delta_scenario_minus_actual"] = ""

        rows.append(row)

    compare_df = pd.DataFrame(rows)

    out_fp = SCENARIO_DIR / f"compare_method_summary_actual_vs_{SCENARIO_NAME}.csv"
    compare_df.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print("方法摘要比較表 CSV:", out_fp.resolve())

    print("\n=== key method comparison ===")
    key_show = compare_df[
        compare_df["metric"].isin(
            [
                "trend_weather_effective_wetness_factor",
                "original_weather_modifier_base",
                "trend_weather_modifier_base",
                "risk_score_delta_trend_minus_original_mean",
                "risk_band_changed_count",
                "risk_band_changed_ratio",
            ]
        )
    ]
    print(key_show.to_string(index=False))


def build_microclimate_summary_comparison():
    """
    若真實環境版與情境版都有 ib3f summary，
    額外產生一份 microclimate summary 對照表。
    """
    actual_fp = (
        BACKUP_DIR
        / "ib3_environment_output"
        / "qixing_weather_terrain_microclimate_interaction_summary.csv"
    )
    scenario_fp = (
        SCENARIO_DIR
        / "ib3_environment_output"
        / "qixing_weather_terrain_microclimate_interaction_summary.csv"
    )

    if not actual_fp.exists() or not scenario_fp.exists():
        print("警告：缺少 ib3f summary，略過微氣候摘要比較表")
        return

    actual_df = pd.read_csv(actual_fp)
    scenario_df = pd.read_csv(scenario_fp)

    if actual_df.empty or scenario_df.empty:
        print("警告：ib3f summary 為空，略過微氣候摘要比較表")
        return

    # ib3f summary 有 metric / value / class / count / ratio 欄位
    actual_map = {}
    for _, row in actual_df.iterrows():
        metric = str(row.get("metric", ""))
        cls = str(row.get("class", ""))
        key = metric if cls in ["", "nan", "None"] else f"{metric}:{cls}"
        value = row.get("value", "")
        if pd.isna(value) or value == "":
            value = row.get("ratio", "")
        actual_map[key] = value

    scenario_map = {}
    for _, row in scenario_df.iterrows():
        metric = str(row.get("metric", ""))
        cls = str(row.get("class", ""))
        key = metric if cls in ["", "nan", "None"] else f"{metric}:{cls}"
        value = row.get("value", "")
        if pd.isna(value) or value == "":
            value = row.get("ratio", "")
        scenario_map[key] = value

    compare_keys = [
        "thermal_humidity_regime",
        "rainfall_level",
        "wind_level",
        "visibility_level",
        "pressure_trend_condition",

        "thermal_stress_factor_mean",
        "wetness_slip_factor_mean",
        "wind_exposure_factor_mean",
        "visibility_navigation_factor_mean",
        "weather_deterioration_factor_mean",
        "terrain_microclimate_factor_mean",
        "combined_microclimate_weather_factor_mean",

        "thermal_stress_factor_max",
        "wetness_slip_factor_max",
        "wind_exposure_factor_max",
        "visibility_navigation_factor_max",
        "weather_deterioration_factor_max",
        "combined_microclimate_weather_factor_max",
    ]

    rows = []

    for key in compare_keys:
        actual_value = actual_map.get(key, "")
        scenario_value = scenario_map.get(key, "")

        row = {
            "metric": key,
            "actual_gpx_time": actual_value,
            SCENARIO_NAME: scenario_value,
        }

        try:
            av = float(actual_value)
            sv = float(scenario_value)
            row["delta_scenario_minus_actual"] = sv - av
        except Exception:
            row["delta_scenario_minus_actual"] = ""

        rows.append(row)

    compare_df = pd.DataFrame(rows)

    out_fp = SCENARIO_DIR / f"compare_microclimate_summary_actual_vs_{SCENARIO_NAME}.csv"
    compare_df.to_csv(out_fp, index=False, encoding="utf-8-sig")

    print("微氣候摘要比較表 CSV:", out_fp.resolve())

    print("\n=== key microclimate comparison ===")
    key_show = compare_df[
        compare_df["metric"].isin(
            [
                "thermal_humidity_regime",
                "rainfall_level",
                "wind_level",
                "visibility_level",
                "pressure_trend_condition",

                "thermal_stress_factor_mean",
                "wetness_slip_factor_mean",
                "wind_exposure_factor_mean",
                "visibility_navigation_factor_mean",
                "weather_deterioration_factor_mean",
                "combined_microclimate_weather_factor_mean",

                "thermal_stress_factor_max",
                "wetness_slip_factor_max",
                "wind_exposure_factor_max",
                "visibility_navigation_factor_max",
                "weather_deterioration_factor_max",
                "combined_microclimate_weather_factor_max",
            ]
        )
    ]
    print(key_show.to_string(index=False))

# =========================================================
# E. Main
# =========================================================
def main():
    ensure_exists(PYTHON_EXE)
    ensure_exists(IB3B)
    ensure_exists(IB3B2)
    ensure_exists(IB3C)
    ensure_exists(IB3C2)
    ensure_exists(IB3D)
    ensure_exists(IB3E)
    ensure_exists(IB3F)
    ensure_exists(IB4B)
    ensure_exists(IB4C)

    print("=== Scenario Runner ===")
    print("scenario:", SCENARIO_NAME)
    print("base dir:", BASE_DIR.resolve())

    backup_current_outputs()

    try:
        # 1. 產生 4/30 假情境天氣 / 水文 window
        run_ib3b_with_bad_weather_scenario()

        # 2. 分析 4/30 情境下的測站更新頻率與天氣趨勢
        run_python_script(IB3B2)

        # 3. 產生 4/30 情境下「舊方法 vs 新方法」方法對照
        run_python_script(IB3C2)

        # 4. 根據假情境重新修正路線風險
        #    若你的 ib3c 已改成趨勢補償版，這裡會使用 ib3b2 趨勢資料。
        #    若你的 ib3c 保持舊版，則仍會產生舊版正式風險。
        run_python_script(IB3C)

        # 5. 產生路線地形微氣候特徵
        #    這一步讀 qixing_environment_adjusted_risk.csv
        run_python_script(IB3E)

        # 6. 產生 4/30 情境下的「氣候 × 地形」交互作用結果
        #    這一步讀 ib3b2 的天氣趨勢 + ib3e 的地形微氣候特徵
        run_python_script(IB3F)

        # 7. 產生假情境風險剖面圖
        run_python_script(IB3D)

        # 8. 疊合同一筆 GPX 活動
        run_python_script(IB4B)

        # 9. 重新計算個人能力與情境適應分數
        run_python_script(IB4C)

        # 10. 保存假情境結果
        copy_scenario_outputs()

        # 11. 整理真實環境版與情境版 PNG
        export_actual_and_scenario_pngs()

        # 12. 整理真實環境版與情境版的 ib3c2 方法對照 CSV
        export_actual_and_scenario_method_compare_csvs()

        # 13. 整理真實環境版與情境版的 ib3e / ib3f 微氣候交互作用 CSV
        export_actual_and_scenario_microclimate_csvs()

        # 14. 產生 actual vs scenario 能力比較表
        build_capability_comparison()

        # 15. 產生 actual vs scenario 方法摘要比較表
        build_method_summary_comparison()

        # 16. 產生 actual vs scenario 微氣候摘要比較表
        build_microclimate_summary_comparison()

    finally:
        # 無論成功失敗，都還原原本真實環境版輸出
        restore_current_outputs()

    print("\n完成假情境流程！")
    print("假情境結果資料夾：", SCENARIO_DIR.resolve())
    print("原本真實環境版輸出已還原。")


if __name__ == "__main__":
    main()