# -*- coding: utf-8 -*-
from pathlib import Path
import subprocess


# =========================================================
# A. Paths
# =========================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

PYTHON_EXE = Path("/Users/iddmini/.pyenv/versions/mountain-310/bin/python")

IB3B = SCRIPT_DIR / "ib3b_extract_environment_window.py"
IB3B2 = SCRIPT_DIR / "ib3b2_analyze_weather_station_update_frequency.py"
IB3C2 = SCRIPT_DIR / "ib3c2_compare_weather_trend_adjustment.py"
IB3C = SCRIPT_DIR / "ib3c_apply_environment_risk_adjustment.py"
IB3E = SCRIPT_DIR / "ib3e_extract_route_microclimate_terrain_features.py"
IB3F = SCRIPT_DIR / "ib3f_apply_weather_terrain_microclimate_interaction.py"
IB3D = SCRIPT_DIR / "ib3d_plot_environment_adjusted_risk_profile.py"
IB4B = SCRIPT_DIR / "ib4b_activity_route_risk_overlay.py"
IB4C = SCRIPT_DIR / "ib4c_personal_capability_score.py"


# =========================================================
# B. Utility
# =========================================================
def ensure_exists(fp: Path):
    if not fp.exists():
        raise FileNotFoundError(f"找不到檔案：{fp.resolve()}")


def run_python_script(script_path: Path):
    ensure_exists(script_path)

    cmd = [str(PYTHON_EXE), str(script_path)]

    print("\n" + "=" * 80)
    print("執行：", " ".join(cmd))
    print("=" * 80)

    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
    )

    if result.stdout.strip():
        print(result.stdout)

    if result.stderr.strip():
        print("=== STDERR ===")
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"執行失敗：{script_path.name}")


# =========================================================
# C. Main
# =========================================================
def main():
    ensure_exists(PYTHON_EXE)

    scripts = [
        IB3B,
        IB3B2,
        IB3C2,
        IB3C,
        IB3E,
        IB3F,
        IB3D,
        IB4B,
        IB4C,
    ]

    for script in scripts:
        ensure_exists(script)

    print("=== Actual Environment Pipeline ===")
    print("base dir:", BASE_DIR.resolve())
    print("script dir:", SCRIPT_DIR.resolve())
    print("")
    print("流程：")
    print("ib3b → ib3b2 → ib3c2 → ib3c → ib3e → ib3f → ib3d → ib4b → ib4c")

    for script in scripts:
        run_python_script(script)

    print("\n完成 actual 真實版流程！")
    print("")
    print("主要輸出：")
    print(BASE_DIR / "ib3_environment_output" / "qixing_environment_adjusted_risk_profile.png")
    print(BASE_DIR / "ib4_activity_output" / "qixing_activity_risk_overlay_profile.png")
    print(BASE_DIR / "ib3_environment_output" / "qixing_weather_terrain_microclimate_interaction_summary.csv")
    print(BASE_DIR / "ib4_activity_output" / "qixing_personal_capability_score.csv")
    print("")
    print("下一步可執行：")
    print(
        f"{PYTHON_EXE} "
        f"{SCRIPT_DIR / 'ib3x_run_bad_weather_scenario_0430.py'}"
    )


if __name__ == "__main__":
    main()