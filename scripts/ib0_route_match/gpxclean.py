import gpxpy

in_path = '/Users/iddmini/Documents/114_山力分析_山/七星山上山/七星山主東0423.gpx'
out_path = '/Users/iddmini/Documents/114_山力分析_山/七星山上山/七星山主東0423_clean.gpx'

with open(in_path, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

for trk in gpx.tracks:
    for seg in trk.segments:
        cleaned = []
        seen = set()
        for pt in seg.points:
            key = (pt.latitude, pt.longitude, pt.time)
            if key not in seen:
                cleaned.append(pt)
                seen.add(key)
        seg.points = cleaned

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(gpx.to_xml())

print(f"清理完成：{len(gpx.tracks)} 條軌跡已輸出到 {out_path}")