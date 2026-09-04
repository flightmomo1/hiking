# OSM Hiking / Terrain Schema Contract v1

## Purpose

This contract separates three different questions that must not be conflated:

1. **Schema capability** — what IA1 promises to preserve/normalize, independent of any real tile.
2. **Synthetic regression** — whether IA1 actually preserves and classifies those tags in a controlled fixture.
3. **Observed tile coverage** — which tags happen to exist in a specific OSM/NLSC tile or route subset.

A zero count in a real tile means only **NOT OBSERVED HERE**. It does not mean **NOT SUPPORTED**.

## Scope

The contract is for the IA1 v1.5.14 OSM evidence boundary. IA1 remains responsible for acquisition, canonical identity, preservation, normalization, route-subset clipping, semantic layers, and QA. Route matching and ordered traversal remain IB0/IB0B responsibilities.

This is a **project support contract**, not an exhaustive list of every possible OpenStreetMap key. OpenStreetMap is open-tagging. Any source key not modeled explicitly must be retained through `osm_tags_extra_json` rather than silently discarded.

## Preservation modes

- `CANONICAL_ID`: IA1-derived canonical identity (`osm_type`, `osm_id`).
- `EXPLICIT_COLUMN`: the source key is part of IA1's stable protected schema.
- `EXTRA_JSON_FALLBACK`: deliberately unknown/unsupported keys must survive in `osm_tags_extra_json`.

## Non-inference rule

IA1 must never convert absence into a claimed observation. For example, a missing `surface` must remain missing. If a later analysis layer infers a surface type, the inferred value must be stored separately from OSM evidence.

## Regression acceptance

The synthetic regression passes only when:

- canonical `osm_type` and `osm_id` are populated for every fixture feature;
- all contract rows marked `required_in_fixture=YES` are observed in the fixture or generated as canonical/derived fields;
- seven-grade `sac_scale` normalization matches the IA1 v1.5.14 mapping;
- expected terrain/technical layer masks are non-empty;
- `future:test_tag=yes` is absent from the explicit schema and present in `osm_tags_extra_json`;
- explicit source keys such as `surface` are not redundantly placed in extra JSON;
- tag-coverage QA marks explicit keys as `EXPLICIT_COLUMN` and the synthetic unknown key as `EXTRA_JSON`.

## Files

- `configs/osm_schema/osm_hiking_terrain_schema_contract_v1.csv`
- `tests/fixtures/osm/ia1_hiking_terrain_fixture_v1.osm`
- `tests/ia1/test_ia1_osm_schema_contract_v1.py`

## Run

From the repository root:

```powershell
python .\tests\ia1\test_ia1_osm_schema_contract_v1.py
```

To test another frozen IA1 script without editing the test:

```powershell
$env:IA1_SCRIPT = "D:\mountain_work\115_osm\scripts\ia_osm\ia1_osm_source_manager_v1_5_14.py"
python .\tests\ia1\test_ia1_osm_schema_contract_v1.py
```

Expected final line:

```text
IA1 OSM SCHEMA CONTRACT REGRESSION: PASS
```
