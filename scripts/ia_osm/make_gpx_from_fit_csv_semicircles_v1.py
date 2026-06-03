import argparse
import csv
from pathlib import Path
from xml.sax.saxutils import escape


def fnum(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", required=True)
    ap.add_argument("--out-gpx", required=True)
    ap.add_argument("--name", default="fit csv routebuffer source")
    ap.add_argument("--max-points", type=int, default=3000)
    ap.add_argument("--drop-time", action="store_true")
    args = ap.parse_args()

    input_fp = Path(args.input_csv)
    out_fp = Path(args.out_gpx)

    rows = []
    with input_fp.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lat_semi = fnum(r.get("record.position_lat[semicircles]"))
            lon_semi = fnum(r.get("record.position_long[semicircles]"))

            if lat_semi is None or lon_semi is None:
                continue

            lat = lat_semi * 180.0 / (2 ** 31)
            lon = lon_semi * 180.0 / (2 ** 31)

            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue

            ele = fnum(r.get("record.enhanced_altitude[m]"))
            if ele is None:
                ele = fnum(r.get("record.altitude[m]"))

            t = r.get("record.timestamp[s]", "")

            rows.append({
                "lat": lat,
                "lon": lon,
                "ele": ele,
                "time": t,
            })

    if len(rows) < 2:
        raise RuntimeError("not enough valid GPS rows")

    # Downsample only for Overpass route-buffer polygon stability.
    if len(rows) > args.max_points:
        step = max(1, len(rows) // args.max_points)
        sampled = rows[::step]
        if sampled[-1] is not rows[-1]:
            sampled.append(rows[-1])
        rows = sampled

    out_fp.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<gpx version="1.1" creator="make_gpx_from_fit_csv_semicircles_v1" xmlns="http://www.topografix.com/GPX/1/1">')
    lines.append(f'  <trk><name>{escape(args.name)}</name><trkseg>')

    for r in rows:
        lines.append(f'    <trkpt lat="{r["lat"]:.8f}" lon="{r["lon"]:.8f}">')
        if r["ele"] is not None:
            lines.append(f'      <ele>{r["ele"]:.2f}</ele>')
        # For route-buffer source, default is no timestamp.
        if (not args.drop_time) and str(r["time"]).strip() != "":
            # FIT timestamp is not ISO time; keep it out unless explicitly needed.
            pass
        lines.append('    </trkpt>')

    lines.append('  </trkseg></trk>')
    lines.append('</gpx>')

    out_fp.write_text("\n".join(lines), encoding="utf-8")

    print("wrote:", out_fp)
    print("points:", len(rows))
    print("start:", rows[0]["lat"], rows[0]["lon"], rows[0]["ele"])
    print("end:", rows[-1]["lat"], rows[-1]["lon"], rows[-1]["ele"])
    print("lat range:", min(r["lat"] for r in rows), max(r["lat"] for r in rows))
    print("lon range:", min(r["lon"] for r in rows), max(r["lon"] for r in rows))


if __name__ == "__main__":
    main()
