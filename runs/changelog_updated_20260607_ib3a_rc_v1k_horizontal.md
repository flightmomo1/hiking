# Changelog - 2026-06-07 IB3A-RC v1k Minimal Horizontal

## Completed Engineering Nodes

### v1d3-v1i Evidence and Classification

Commit:

- `581f511 Add IB3A-RC full-batch candidate labeling and wrong-route QA`

This node includes candidate projection and context, summit stabilization, transition evidence, off-target detection, zone consolidation, mainline membership, and route-level wrong-route rules.

### v1j Display Trajectory

Commit:

- `0b04c81 Add IB3A-RC display trajectory refit layer`

The qixing_lengshuikeng full26 run passed with 345,979 rows. v1j adds display coordinates and raw-vs-display QA only. It does not create calibrated fields.

### v1k Minimal Horizontal Dataset

Commit:

- `70e8ffe Add IB3A-RC calibrated activity dataset horizontal layer`

The qixing_lengshuikeng full26 run passed:

- PASS / FAIL / SKIPPED = 26 / 0 / 0
- total rows = 345,979
- calibrated CSV / summary / provenance = 26 / 26 / 26
- row count and order preserved
- protected fields changed = 0
- v1i/v1j hashes unchanged
- raw alias mismatch = 0
- unresolved rows = 0
- forbidden columns = 0
- semantic mismatch checks = 0

## v1k Distribution

Horizontal sources:

- mainline candidate projection = 228,338
- raw GPS fallback = 96,361
- reviewed summit anchor = 16,714
- connector projection = 3,131
- wrong-route candidate projection = 1,435

Backend policies:

- analytics ready = 248,183
- behavior analytics only, off-target = 96,361
- behavior analytics only, wrong-route = 1,435

## Boundaries Preserved

- No raw activity data was overwritten.
- No v1d3-v1i or v1j output was modified.
- Wrong-route was preserved outside canonical mainline.
- Connector remained distinct from mainline core.
- No calibrated speed, distance, elevation, movement state, NLSC, facility/radar, or THCI fields were produced.
- Legacy automatic usable recovery remains excluded.

## Next Stage

Plan v1k2 for calibrated horizontal distance, speed, movement state, GPS drift suspicion, and low-speed uncertainty. NLSC elevation and facility/radar evidence remain separate later stages.

