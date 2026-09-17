#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def local_linear_smooth(x, y, window_m):
    out = np.empty(len(x), dtype=float)
    half = window_m / 2.0
    for i, q in enumerate(x):
        left = np.searchsorted(x, q - half, side="left")
        right = np.searchsorted(x, q + half, side="right")
        xx = x[left:right] - q
        yy = y[left:right]
        n = len(xx)
        if n < 2:
            out[i] = y[i]
            continue
        su = float(xx.sum()); sy = float(yy.sum())
        suu = float((xx * xx).sum()); suy = float((xx * yy).sum())
        den = n * suu - su * su
        out[i] = float(yy.mean()) if abs(den) < 1e-12 else float((sy * suu - su * suy) / den)
    return out


def metrics(x, ele):
    dd = np.diff(x); dz = np.diff(ele)
    gain = float(np.clip(dz, 0, None).sum())
    loss = float(np.clip(-dz, 0, None).sum())
    d20 = np.arange(0.0, float(x[-1]), 20.0)
    if len(d20) == 0 or d20[-1] < x[-1]:
        d20 = np.append(d20, x[-1])
    e20 = np.interp(d20, x, ele)
    grade20 = 100.0 * np.diff(e20) / np.diff(d20)
    return gain, loss, float(np.quantile(np.abs(grade20), 0.95))


def shrinkage_offset(route_dist, anchor_dist, anchor_bias, lam):
    med = float(np.median(anchor_bias))
    coef = np.polyfit(anchor_dist, anchor_bias, 1)
    linear = np.polyval(coef, route_dist)
    return med + lam * (linear - med), med, float(coef[0]) * 1000.0


def main():
    ap = argparse.ArgumentParser(description="Audit GPX smoothing scales and NLSC shrinkage calibration on a Route Axis profile.")
    ap.add_argument("--profile", required=True, help="CSV with dist_m and ele_gpx_m")
    ap.add_argument("--anchors", required=True, help="CSV from direct_contour_anchors.py")
    ap.add_argument("--windows", default="10,20,30,50,80,100")
    ap.add_argument("--lambda-values", default="0,0.25,0.5,0.75,1")
    ap.add_argument("--selected-window", type=float)
    ap.add_argument("--selected-lambda", type=float)
    ap.add_argument(
        "--absolute-vertical-reference",
        required=True,
        help="Explicit provenance label for the validated absolute vertical reference",
    )
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    p = pd.read_csv(args.profile).sort_values("dist_m").reset_index(drop=True)
    a = pd.read_csv(args.anchors).sort_values("route_dist_m").reset_index(drop=True)
    for c in ("dist_m", "ele_gpx_m"):
        if c not in p.columns:
            raise RuntimeError(f"Missing profile field: {c}")
    for c in ("route_dist_m", "contour_z_m"):
        if c not in a.columns:
            raise RuntimeError(f"Missing anchor field: {c}")

    x = p["dist_m"].to_numpy(float)
    raw = p["ele_gpx_m"].to_numpy(float)
    ax = a["route_dist_m"].to_numpy(float)
    az = a["contour_z_m"].to_numpy(float)
    windows = [float(v) for v in args.windows.split(",") if v.strip()]
    lambdas = [float(v) for v in args.lambda_values.split(",") if v.strip()]

    outdir = Path(args.output_dir); outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for w in windows:
        shape = local_linear_smooth(x, raw, w)
        shape_anchor = np.interp(ax, x, shape)
        anchor_bias = az - shape_anchor
        sgain, sloss, sp95 = metrics(x, shape)
        for lam in lambdas:
            off, med, drift = shrinkage_offset(x, ax, anchor_bias, lam)
            fused = shape + off
            fused_anchor = np.interp(ax, x, fused)
            resid = fused_anchor - az
            ae = np.abs(resid)
            fgain, floss, fp95 = metrics(x, fused)
            rows.append({
                "window_m": w,
                "lambda": lam,
                "shape_gain_m": sgain,
                "shape_loss_m": sloss,
                "shape_grade20_p95_pct": sp95,
                "anchor_global_median_bias_m": med,
                "anchor_full_linear_drift_m_per_km": drift,
                "fused_gain_m": fgain,
                "fused_loss_m": floss,
                "fused_grade20_p95_pct": fp95,
                "anchor_MAE_m": float(ae.mean()),
                "anchor_MedAE_m": float(np.median(ae)),
                "anchor_P90_AE_m": float(np.quantile(ae, 0.90)),
                "anchor_Max_AE_m": float(ae.max()),
            })
    summary = pd.DataFrame(rows)
    summary_fp = outdir / "elevation_fusion_grid.csv"
    summary.to_csv(summary_fp, index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))
    print("summary:", summary_fp)

    if args.selected_window is not None or args.selected_lambda is not None:
        if args.selected_window is None or args.selected_lambda is None:
            raise RuntimeError("Provide both --selected-window and --selected-lambda")
        shape = local_linear_smooth(x, raw, args.selected_window)
        anchor_bias = az - np.interp(ax, x, shape)
        off, med, drift = shrinkage_offset(x, ax, anchor_bias, args.selected_lambda)
        fused = shape + off
        out = p.copy()
        out["ele_gpx_shape_m"] = shape
        out["nlsc_vertical_offset_m"] = off
        out["ele_fused_m"] = fused
        out["elevation_sensor_origin"] = "UNKNOWN"
        out["shape_smoothing_method"] = "distance_local_linear"
        out["shape_smoothing_scale_m"] = args.selected_window
        out["absolute_vertical_reference"] = args.absolute_vertical_reference
        out["calibration_model"] = "shrinkage_linear"
        out["calibration_lambda"] = args.selected_lambda
        out["elevation_fusion_method"] = "nlsc_anchor_gpx_shape_v1"
        fused_fp = outdir / "elevation_fused_candidate.csv"
        out.to_csv(fused_fp, index=False, encoding="utf-8-sig")
        ae = np.abs(np.interp(ax, x, fused) - az)
        print("selected_window_m:", args.selected_window)
        print("selected_lambda:", args.selected_lambda)
        print("anchor_global_median_bias_m:", med)
        print("anchor_full_linear_drift_m_per_km:", drift)
        print("final_anchor_MAE_m:", float(ae.mean()))
        print("final_anchor_P90_AE_m:", float(np.quantile(ae, 0.90)))
        print("final_anchor_Max_AE_m:", float(ae.max()))
        print("fused_output:", fused_fp)


if __name__ == "__main__":
    main()
