#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""IA1 v1.5.14 OSM schema contract regression.

This is intentionally independent of any real NLSC/OSM tile. It proves schema
capability and forward-compatible tag preservation using a deterministic OSM
fixture. Real-tile tag counts remain observational QA only.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FP = REPO_ROOT / "configs" / "osm_schema" / "osm_hiking_terrain_schema_contract_v1.csv"
FIXTURE_FP = REPO_ROOT / "tests" / "fixtures" / "osm" / "ia1_hiking_terrain_fixture_v1.osm"
DEFAULT_IA1 = REPO_ROOT / "scripts" / "ia_osm" / "ia1_osm_source_manager_v1_5_14.py"
IA1_FP = Path(os.environ.get("IA1_SCRIPT", str(DEFAULT_IA1))).resolve()


def load_ia1_module():
    if not IA1_FP.exists():
        raise FileNotFoundError(f"IA1 script not found: {IA1_FP}")
    spec = importlib.util.spec_from_file_location("ia1_under_test", IA1_FP)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import IA1 script: {IA1_FP}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_contract():
    with CONTRACT_FP.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_fixture_to_osmnx_like_gdf(fp: Path) -> gpd.GeoDataFrame:
    """Parse the tiny deterministic fixture without calling Overpass/osmium.

    Output resembles the source attribute shape IA1 receives before add_metadata:
    structural columns `element`, `id`, geometry, plus arbitrary OSM tag columns.
    """
    root = ET.parse(fp).getroot()
    nodes = {}
    for n in root.findall("node"):
        nodes[int(n.attrib["id"])] = (
            float(n.attrib["lon"]),
            float(n.attrib["lat"]),
        )

    rows = []
    for w in root.findall("way"):
        refs = [int(nd.attrib["ref"]) for nd in w.findall("nd")]
        coords = [nodes[r] for r in refs]
        if len(coords) >= 4 and coords[0] == coords[-1]:
            geom = Polygon(coords)
        else:
            geom = LineString(coords)
        row = {
            "element": "way",
            "id": int(w.attrib["id"]),
            "geometry": geom,
        }
        for tag in w.findall("tag"):
            row[tag.attrib["k"]] = tag.attrib["v"]
        rows.append(row)

    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


class IA1SchemaContractRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ia1 = load_ia1_module()
        cls.contract = load_contract()
        cls.source = parse_fixture_to_osmnx_like_gdf(FIXTURE_FP)
        cls.source_columns = list(cls.source.columns)
        cls.raw = cls.ia1.add_metadata(
            cls.source,
            case_id="synthetic_schema_contract_v1",
            fetched_at="2026-09-04T00:00:00Z",
            dataset_id="synthetic-osm-schema-contract-v1",
            source_kind="local_pbf",
            source_url=None,
            source_dataset_id="synthetic-fixture-v1",
            source_sha256="SYNTHETIC",
            osm_base_timestamp="2026-09-04T00:00:00Z",
            coverage_status="SYNTHETIC_FIXTURE",
        )
        cls.raw = cls.ia1.normalize_highway(cls.raw)
        cls.raw, cls.extra_cols = cls.ia1.attach_osm_extra_tags(
            cls.raw, cls.source_columns
        )
        cls.coverage = cls.ia1.build_osm_tag_coverage_qa(
            cls.raw, cls.source_columns
        )
        cls.selected = cls.ia1.select_columns(cls.raw)
        cls.masks = cls.ia1.layer_masks(cls.raw)

    def test_contract_explicit_keys_exist_in_protected_schema(self):
        missing = sorted({
            row["tag_key"]
            for row in self.contract
            if row["preservation_mode"] == "EXPLICIT_COLUMN"
            and row["tag_key"] not in self.ia1.PROTECT_COLS
        })
        self.assertEqual(missing, [], f"Explicit contract keys missing from PROTECT_COLS: {missing}")

    def test_canonical_identity_is_complete(self):
        self.assertIn("osm_type", self.selected.columns)
        self.assertIn("osm_id", self.selected.columns)
        self.assertEqual(int(self.selected["osm_type"].notna().sum()), len(self.selected))
        self.assertEqual(int(self.selected["osm_id"].notna().sum()), len(self.selected))
        self.assertTrue(self.selected["osm_type"].eq("way").all())
        self.assertEqual(self.selected["osm_id"].nunique(), len(self.selected))

    def test_sac_scale_seven_grade_mapping(self):
        expected = {
            "strolling": (0, "none", "very_easy"),
            "hiking": (1, "T1", "easy"),
            "mountain_hiking": (2, "T2", "moderate"),
            "demanding_mountain_hiking": (3, "T3", "hard"),
            "alpine_hiking": (4, "T4", "very_hard"),
            "demanding_alpine_hiking": (5, "T5", "extreme"),
            "difficult_alpine_hiking": (6, "T6", "extreme_plus"),
        }
        for value, (rank, grade, hint) in expected.items():
            with self.subTest(value=value):
                self.assertEqual(self.ia1.classify_sac_scale_rank(value), rank)
                self.assertEqual(self.ia1.classify_sac_scale_t_grade(value), grade)
                self.assertEqual(self.ia1.classify_trail_difficulty(value), hint)

    def test_fixture_core_route_attributes_survive(self):
        row = self.selected.loc[self.selected["osm_id"].astype(int) == 1001].iloc[0]
        self.assertEqual(row["highway"], "path")
        self.assertEqual(row["surface"], "ground")
        self.assertEqual(row["surface:material"], "stone")
        self.assertEqual(row["smoothness"], "bad")
        self.assertEqual(row["sac_scale"], "mountain_hiking")
        self.assertEqual(int(row["sac_scale_rank"]), 2)
        self.assertEqual(row["sac_scale_t_grade"], "T2")
        self.assertEqual(row["trail_difficulty_hint"], "moderate")
        self.assertEqual(row["incline"], "12%")

    def test_steps_and_technical_attributes_survive(self):
        steps = self.selected.loc[self.selected["osm_id"].astype(int) == 1002].iloc[0]
        self.assertEqual(steps["highway"], "steps")
        self.assertEqual(int(steps["is_steps"]), 1)
        self.assertEqual(str(steps["step_count"]), "120")
        self.assertEqual(steps["handrail"], "yes")
        self.assertEqual(steps["handrail:center"], "yes")

        ladder = self.selected.loc[self.selected["osm_id"].astype(int) == 1011].iloc[0]
        self.assertEqual(ladder["highway"], "ladder")
        self.assertEqual(ladder["route_role"], "technical_route")
        self.assertEqual(str(ladder["rungs"]), "12")

    def test_expected_semantic_layers_are_detected(self):
        expected_layers = [
            "highway", "cliff", "scree", "bare_rock", "wetland",
            "landslide", "safety_rope", "assisted_trail", "handrail",
            "rungs", "ladder", "waterway", "hazard", "obstacle",
            "overgrown", "barrier",
        ]
        failed = []
        for layer in expected_layers:
            mask = self.masks.get(layer)
            if mask is None or int(mask.sum()) < 1:
                failed.append(layer)
        self.assertEqual(failed, [], f"Synthetic fixture layers not detected: {failed}")

    def test_unknown_tag_is_losslessly_preserved_in_extra_json(self):
        self.assertNotIn("future:test_tag", self.ia1.PROTECT_COLS)
        row = self.selected.loc[self.selected["osm_id"].astype(int) == 1001].iloc[0]
        payload = json.loads(row["osm_tags_extra_json"])
        self.assertEqual(payload.get("future:test_tag"), "yes")
        self.assertNotIn("surface", payload)
        self.assertNotIn("sac_scale", payload)
        self.assertIn("future:test_tag", str(row["osm_extra_tag_keys"]))
        self.assertGreaterEqual(int(row["osm_extra_tag_count"]), 1)

    def test_coverage_qa_distinguishes_explicit_and_extra(self):
        by_key = self.coverage.set_index("tag_key")
        self.assertEqual(by_key.loc["surface", "schema_status"], "EXPLICIT_COLUMN")
        self.assertEqual(by_key.loc["sac_scale", "schema_status"], "EXPLICIT_COLUMN")
        self.assertEqual(by_key.loc["future:test_tag", "schema_status"], "EXTRA_JSON")
        self.assertTrue(bool(by_key.loc["future:test_tag", "preserved_in_extra_json"]))

    def test_required_fixture_contract_rows_are_represented(self):
        observed_source_keys = set(self.source_columns)
        generated_keys = set(self.selected.columns)
        missing = []
        for row in self.contract:
            if row["required_in_fixture"].upper() != "YES":
                continue
            key = row["tag_key"]
            mode = row["preservation_mode"]
            if mode == "CANONICAL_ID":
                ok = key in generated_keys
            else:
                ok = key in observed_source_keys or key in generated_keys
            if not ok:
                missing.append((row["category"], key, row["expected_value_or_pattern"]))
        self.assertEqual(missing, [], f"Required fixture contract rows not represented: {missing}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IA1SchemaContractRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("\nIA1 OSM SCHEMA CONTRACT REGRESSION: PASS")
        sys.exit(0)
    print("\nIA1 OSM SCHEMA CONTRACT REGRESSION: FAIL")
    sys.exit(1)
