# =========================================================
# ib1h_generate_candidate_waypoints_from_risk_zones.py
#
# 目的：
# - 讀取 Prototype A risk zones
# - 根據連續風險區間產生候選中繼點
# - 先輸出 distance-axis waypoint，不處理 lat/lon
#
# 中繼點角色：
# - decision：進入高風險區前的推進/撤退判斷點
# - recovery：通過高風險區後的心率恢復點
# - rest_candidate：低風險或較平緩區間的休息候選點
# - conditional_check：橋梁、水文、天候敏感等條件式檢查點
# - final_push：最後推進前的狀態確認點
# =========================================================

from pathlib import Path
import pandas as pd


# =========================================================
# 0. Case 設定
# =========================================================
CASE_ID = "juansi_waterfall_fitcsv_20260503"
CASE_NAME = "絹絲瀑布 FIT CSV 20260503"
MODEL_VERSION = "prototype_A_terrain_dominant_v1"

IN_ZONE_CSV = (
    Path("outputs")
    / "prototype_A_terrain_dominant"
    / CASE_ID
    / f"{CASE_ID}_prototype_A_risk_zones.csv"
)

OUT_DIR = Path("outputs") / "prototype_A_terrain_dominant" / CASE_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_WAYPOINT_CSV = OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_by_distance.csv"
OUT_SUMMARY_TXT = OUT_DIR / f"{CASE_ID}_prototype_A_candidate_waypoints_summary.txt"


# =========================================================
# 1. 參數
# =========================================================
# 高風險區入口前，往前多少公尺設 decision point
PRE_HIGH_DECISION_OFFSET_M = 50.0

# 高風險區出口後，往後多少公尺設 recovery point
POST_HIGH_RECOVERY_OFFSET_M = 50.0

# risk zone 太短時，避免 decision / recovery 超出 zone 太多
MIN_DISTANCE_M = 0.0

# 在 low zone 中間產生 rest candidate
GENERATE_LOW_ZONE_REST = True

# moderate zone 長於此值時，產生中段 rest / pacing candidate
MODERATE_REST_MIN_LENGTH_M = 300.0

# 最後一段前的 final push point
GENERATE_FINAL_PUSH = True

HIGH_GROUPS = {"high", "very_high"}


# =========================================================
# 2. 工具函式
# =========================================================
def norm_text(v):
    if pd.isna(v):
        return ""
    text = str(v).strip().lower()
    if text in {"", "nan", "none", "<na>", "na", "null"}:
        return ""
    return text


def clamp_dist(d, route_min, route_max):
    return max(route_min, min(route_max, float(d)))


def has_reason(row, keyword):
    return keyword in str(row.get("zone_main_reason", "")).lower()


def make_waypoint(
    waypoint_id,
    name,
    target_dist_m,
    waypoint_type,
    primary_role,
    secondary_roles,
    source_zone,
    recommendation_reason,
    priority,
):
    return {
        "case_id": CASE_ID,
        "case_name": CASE_NAME,
        "model_version": MODEL_VERSION,
        "waypoint_id": waypoint_id,
        "name": name,
        "target_dist_m": round(float(target_dist_m), 2),
        "waypoint_type": waypoint_type,
        "primary_role": primary_role,
        "secondary_roles": secondary_roles,
        "candidate_source": "prototype_A_risk_zone",
        "source_zone_id": int(source_zone.get("zone_id", -1)),
        "source_zone_risk_group": source_zone.get("zone_risk_group", ""),
        "source_zone_start_m": round(float(source_zone.get("start_dist_m", 0)), 2),
        "source_zone_end_m": round(float(source_zone.get("end_dist_m", 0)), 2),
        "source_zone_length_m": round(float(source_zone.get("length_m", 0)), 2),
        "source_zone_mean_risk": round(float(source_zone.get("mean_combined_risk", 0)), 6),
        "source_zone_max_risk": round(float(source_zone.get("max_combined_risk", 0)), 6),
        "dominant_slope_band": source_zone.get("dominant_slope_band", ""),
        "hydrology_present_ratio": round(float(source_zone.get("hydrology_present_ratio", 0)), 6),
        "zone_main_reason": source_zone.get("zone_main_reason", ""),
        "recommendation_reason": recommendation_reason,
        "priority": int(priority),
    }


def merge_role_text(a, b):
    """
    合併 role 字串，例如：
    rest|hydration + decision|next_high_zone_check
    """
    items = []

    for text in [a, b]:
        if pd.isna(text):
            continue

        for item in str(text).split("|"):
            item = item.strip()
            if item and item not in items:
                items.append(item)

    return "|".join(items)


def merge_waypoint_rows(base, other):
    """
    兩個 waypoint 太接近時，保留 priority 較高者作為主體，
    但把另一個 waypoint 的角色與原因合併進來。
    """
    merged = dict(base)

    # 合併 waypoint_type
    t1 = str(base.get("waypoint_type", "")).strip()
    t2 = str(other.get("waypoint_type", "")).strip()

    if t1 and t2 and t1 != t2:
        if {"recovery", "decision"} == {t1, t2}:
            merged["waypoint_type"] = "recovery_decision"
        else:
            merged["waypoint_type"] = merge_role_text(t1, t2)

    # 合併 primary / secondary roles
    merged["secondary_roles"] = merge_role_text(
        base.get("secondary_roles", ""),
        other.get("primary_role", "") + "|" + str(other.get("secondary_roles", "")),
    )

    # 合併 reason
    r1 = str(base.get("recommendation_reason", "")).strip()
    r2 = str(other.get("recommendation_reason", "")).strip()

    if r2 and r2 not in r1:
        merged["recommendation_reason"] = r1 + " 同時，" + r2
    else:
        merged["recommendation_reason"] = r1

    # 合併來源 zone id
    z1 = str(base.get("source_zone_id", "")).strip()
    z2 = str(other.get("source_zone_id", "")).strip()

    if z2 and z2 != z1:
        merged["related_zone_ids"] = merge_role_text(z1, z2)
    else:
        merged["related_zone_ids"] = z1

    # priority 取較高優先，也就是數字較小者
    merged["priority"] = min(int(base.get("priority", 99)), int(other.get("priority", 99)))

    return merged


def deduplicate_waypoints(wp_df, min_sep_m=30.0):
    """
    若 waypoint 太接近，不直接刪除，而是合併角色。
    priority 數字越小越重要。
    """
    if wp_df.empty:
        return wp_df

    df = wp_df.sort_values(["target_dist_m", "priority"]).reset_index(drop=True)

    kept = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        d = float(row_dict["target_dist_m"])

        merge_idx = None

        for i, kept_row in enumerate(kept):
            if abs(float(kept_row["target_dist_m"]) - d) < min_sep_m:
                merge_idx = i
                break

        if merge_idx is None:
            kept.append(row_dict)
        else:
            existing = kept[merge_idx]

            # priority 較高者當 base
            if int(row_dict.get("priority", 99)) < int(existing.get("priority", 99)):
                kept[merge_idx] = merge_waypoint_rows(row_dict, existing)
            else:
                kept[merge_idx] = merge_waypoint_rows(existing, row_dict)

    out = pd.DataFrame(kept)
    out = out.sort_values("target_dist_m").reset_index(drop=True)
    return out


# =========================================================
# 3. 讀資料
# =========================================================
if not IN_ZONE_CSV.exists():
    raise FileNotFoundError(f"找不到 risk zone CSV：{IN_ZONE_CSV.resolve()}")

zone_df = pd.read_csv(IN_ZONE_CSV, low_memory=False)
zone_df = zone_df.sort_values("start_dist_m").reset_index(drop=True)

required = [
    "zone_id",
    "zone_risk_group",
    "start_dist_m",
    "end_dist_m",
    "length_m",
    "mean_combined_risk",
    "max_combined_risk",
    "dominant_slope_band",
    "hydrology_present_ratio",
    "zone_main_reason",
]

missing = [c for c in required if c not in zone_df.columns]
if missing:
    raise ValueError(f"risk zone CSV 缺少必要欄位：{missing}")

route_min = float(zone_df["start_dist_m"].min())
route_max = float(zone_df["end_dist_m"].max())

print("case:", CASE_ID)
print("zones:", len(zone_df))
print("route range:", route_min, route_max)


# =========================================================
# 4. 產生候選中繼點
# =========================================================
waypoints = []
wp_counter = 1

for idx, zone in zone_df.iterrows():
    zone_id = int(zone["zone_id"])
    group = norm_text(zone["zone_risk_group"])
    start_m = float(zone["start_dist_m"])
    end_m = float(zone["end_dist_m"])
    length_m = float(zone["length_m"])

    # -----------------------------------------------------
    # A. high zone 入口前 decision point
    # -----------------------------------------------------
    if group in HIGH_GROUPS:
        target = clamp_dist(start_m - PRE_HIGH_DECISION_OFFSET_M, route_min, route_max)

        # 若高風險從起點開始，decision point 就是起點整備點
        if start_m <= route_min + 1:
            name = f"WP{wp_counter:02d}_高風險主段起點整備點"
            wp_type = "start_precheck"
            primary_role = "decision"
            secondary_roles = "precheck|pacing"
            reason = (
                f"zone {zone_id} 從起點附近進入高風險區，"
                f"建議於出發前完成裝備、體力、天候與配速確認。"
            )
            priority = 1
        else:
            name = f"WP{wp_counter:02d}_高風險區入口決策點"
            wp_type = "decision"
            primary_role = "decision"
            secondary_roles = "retreat_check|pacing"
            reason = (
                f"位於 zone {zone_id} 高風險區入口前約 {PRE_HIGH_DECISION_OFFSET_M:.0f} m，"
                f"適合判斷是否繼續進入高風險路段。"
            )
            priority = 2

        waypoints.append(
            make_waypoint(
                f"WP{wp_counter:02d}",
                name,
                target,
                wp_type,
                primary_role,
                secondary_roles,
                zone,
                reason,
                priority,
            )
        )
        wp_counter += 1

        # -------------------------------------------------
        # B. high zone 出口後 recovery point
        # -------------------------------------------------
        target = clamp_dist(end_m + POST_HIGH_RECOVERY_OFFSET_M, route_min, route_max)

        name = f"WP{wp_counter:02d}_高風險區出口恢復點"
        reason_parts = [
            f"zone {zone_id} 高風險區結束後約 {POST_HIGH_RECOVERY_OFFSET_M:.0f} m，適合恢復心率、補水與重新評估推進狀態。"
        ]

        if has_reason(zone, "hydrology_present"):
            reason_parts.append("該高風險區具有水文鄰近特徵，雨後應特別注意濕滑。")

        if has_reason(zone, "slope_very_steep") or has_reason(zone, "slope_steep"):
            reason_parts.append("該高風險區地形坡度較大，通過後適合安排恢復。")

        waypoints.append(
            make_waypoint(
                f"WP{wp_counter:02d}",
                name,
                target,
                "recovery",
                "recovery",
                "rest|hydration|heart_rate_check",
                zone,
                "".join(reason_parts),
                1,
            )
        )
        wp_counter += 1

    # -----------------------------------------------------
    # C. low zone 中段 rest candidate
    # -----------------------------------------------------
    if group == "low" and GENERATE_LOW_ZONE_REST:
        target = clamp_dist((start_m + end_m) / 2.0, route_min, route_max)

        waypoints.append(
            make_waypoint(
                f"WP{wp_counter:02d}",
                f"WP{wp_counter:02d}_低風險區休息候選點",
                target,
                "rest_candidate",
                "rest",
                "recovery|pacing",
                zone,
                f"zone {zone_id} 為低風險區，可作為短暫休息或節奏調整候選點。",
                4,
            )
        )
        wp_counter += 1

    # -----------------------------------------------------
    # D. 長 moderate zone 中段 pacing / rest candidate
    # -----------------------------------------------------
    if group == "moderate" and length_m >= MODERATE_REST_MIN_LENGTH_M:
        target = clamp_dist((start_m + end_m) / 2.0, route_min, route_max)

        waypoints.append(
            make_waypoint(
                f"WP{wp_counter:02d}",
                f"WP{wp_counter:02d}_中風險長區間節奏調整點",
                target,
                "pacing",
                "pacing",
                "rest_candidate|heart_rate_check",
                zone,
                f"zone {zone_id} 為長距離中風險區間，建議於中段檢查心率、補水並調整配速。",
                3,
            )
        )
        wp_counter += 1

    # -----------------------------------------------------
    # E. bridge conditional check
    # -----------------------------------------------------
    if has_reason(zone, "bridge_conditional") or float(zone.get("bridge_ratio", 0)) > 0:
        target = clamp_dist((start_m + end_m) / 2.0, route_min, route_max)

        waypoints.append(
            make_waypoint(
                f"WP{wp_counter:02d}",
                f"WP{wp_counter:02d}_橋梁條件式檢查點",
                target,
                "conditional_check",
                "condition_check",
                "bridge|hydrology|slip_check",
                zone,
                f"zone {zone_id} 含橋梁條件式因子，雨後或水文狀況不佳時應檢查濕滑、橋面與通行安全。",
                2,
            )
        )
        wp_counter += 1


# ---------------------------------------------------------
# F. final push point：最後一段前
# ---------------------------------------------------------
if GENERATE_FINAL_PUSH and len(zone_df) >= 2:
    last_zone = zone_df.iloc[-1]
    target = clamp_dist(float(last_zone["start_dist_m"]), route_min, route_max)

    waypoints.append(
        make_waypoint(
            f"WP{wp_counter:02d}",
            f"WP{wp_counter:02d}_最後推進決策點",
            target,
            "final_push",
            "decision",
            "final_push|time_check|fatigue_check",
            last_zone,
            "進入最後一段前，建議確認剩餘體力、時間、天候與隊伍狀態。",
            3,
        )
    )
    wp_counter += 1


# =========================================================
# 5. 去除過近候選點
# =========================================================
wp_df = pd.DataFrame(waypoints)

before_n = len(wp_df)
wp_df = deduplicate_waypoints(wp_df, min_sep_m=30.0)
after_n = len(wp_df)

# 重新依距離編號，保留原本 waypoint_id 作為 generated_id
wp_df = wp_df.reset_index(drop=True)
wp_df["generated_order"] = range(1, len(wp_df) + 1)


# =========================================================
# 6. 輸出
# =========================================================
wp_df.to_csv(OUT_WAYPOINT_CSV, index=False, encoding="utf-8-sig")

summary_lines = [
    "Prototype A Candidate Waypoints Summary",
    f"case_id: {CASE_ID}",
    f"case_name: {CASE_NAME}",
    f"model_version: {MODEL_VERSION}",
    "",
    f"input zone CSV: {IN_ZONE_CSV}",
    f"route_range_m: {route_min:.1f} - {route_max:.1f}",
    f"generated_waypoints_before_dedup: {before_n}",
    f"generated_waypoints_after_dedup: {after_n}",
    "",
    "waypoint_type counts:",
    str(wp_df["waypoint_type"].value_counts()),
    "",
    f"waypoint CSV: {OUT_WAYPOINT_CSV}",
]

OUT_SUMMARY_TXT.write_text("\n".join(summary_lines), encoding="utf-8")


print("\n完成！")
print("waypoint CSV:", OUT_WAYPOINT_CSV.resolve())
print("summary TXT:", OUT_SUMMARY_TXT.resolve())

print("\n--- waypoint type ---")
print(wp_df["waypoint_type"].value_counts())

print("\n--- candidate waypoints ---")
print(
    wp_df[
        [
            "generated_order",
            "waypoint_id",
            "target_dist_m",
            "waypoint_type",
            "primary_role",
            "secondary_roles",
            "source_zone_id",
            "related_zone_ids",
            "source_zone_risk_group",
            "source_zone_start_m",
            "source_zone_end_m",
            "recommendation_reason",
        ]
    ]
)