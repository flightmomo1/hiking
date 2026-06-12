# IB3W Station Elevation Map Tile Distribution v1 Notes

- Date: 2026-06-12
- Branch: codex/ib3w-station-elevation-map-tile-distribution-v1
- Scope: make the station elevation report tile summary dynamic

## Purpose

The station elevation 1D/2D report previously preserved only the
`tile_97233NW` and `tile_97233SW` counts in
`station_elevation_map_summary.csv`. The latest full-valid-tiles rerun contains
nine final NLSC tiles, so those two legacy fields are incomplete as a tile
distribution.

## Change

Updated:

    scripts/ib3_activity_environment/ib3w_plot_station_elevation_1d_2d_html_v1.py

The script now builds one tile distribution from the merged station plot
dataframe using `elevation_final_nlsc_tile`.

New output:

    station_elevation_tile_distribution.csv

Columns:

    case_id
    elevation_final_nlsc_tile
    station_rows
    weather_rows
    water_rows
    final_acceptable
    final_low_confidence_review_required
    final_review_required
    final_lookup_failed
    final_elevation_missing

New `station_elevation_map_summary.csv` fields:

    unique_final_tile_count
    final_tiles
    tile_distribution_json

The legacy `tile_97233NW` and `tile_97233SW` fields remain for backward
compatibility and are derived from the dynamic distribution.

The HTML report now includes a visible `Tile distribution` table with all
final NLSC tiles and the same counts written to the new CSV.

## Full Valid Tiles QA

Expected final tile station counts:

| elevation_final_nlsc_tile | station_rows |
| --- | ---: |
| 96231SE | 1 |
| 96232NE | 10 |
| 96232SE | 23 |
| 97224NW | 2 |
| 97233NE | 9 |
| 97233NW | 14 |
| 97233SE | 22 |
| 97233SW | 31 |
| 97234SW | 2 |

Expected totals:

    unique_final_tile_count = 9
    station_rows = 114
    tile_97233NW = 14
    tile_97233SW = 31

## Boundary

This change only updates station elevation report summarization and
visualization. It does not rerun station elevation lookup, perform
weather/hydro fusion, or adjust route risk, radar, THCI, or the time model.

Generated report outputs remain untracked and are not staged.
