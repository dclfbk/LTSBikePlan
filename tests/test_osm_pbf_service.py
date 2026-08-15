import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.services.osm_pbf_service import (
    apply_route_name_fallback,
    extract_bicycle_route_names,
    normalize_edge_columns,
    normalize_node_columns,
)


class TestNormalizeEdgeColumns(unittest.TestCase):
    def test_fills_missing_required_columns_with_nan(self):
        edges = pd.DataFrame({"highway": ["residential"], "geometry": [None]})
        normalized = normalize_edge_columns(edges)
        for column in ["access", "oneway", "lanes", "maxspeed", "length", "osmid", "service"]:
            self.assertIn(column, normalized.columns)
            self.assertTrue(pd.isna(normalized[column].iloc[0]))

    def test_preserves_existing_columns_untouched(self):
        edges = pd.DataFrame({"highway": ["residential"], "access": ["yes"], "geometry": [None]})
        normalized = normalize_edge_columns(edges)
        self.assertEqual(normalized["access"].iloc[0], "yes")

    def test_does_not_mutate_input(self):
        edges = pd.DataFrame({"highway": ["residential"], "geometry": [None]})
        normalize_edge_columns(edges)
        self.assertNotIn("access", edges.columns)

    def test_accepts_custom_column_list(self):
        edges = pd.DataFrame({"highway": ["residential"]})
        normalized = normalize_edge_columns(edges, required_columns=["custom_tag"])
        self.assertIn("custom_tag", normalized.columns)
        self.assertNotIn("access", normalized.columns)


class TestNormalizeNodeColumns(unittest.TestCase):
    def test_extracts_highway_from_tags_dict(self):
        # Reproduces the pyrosm shape verified against a live osmit-estratti
        # extract: nodes have no top-level `highway` column, only a `tags`
        # dict that may contain one.
        nodes = pd.DataFrame(
            {
                "tags": [
                    {"highway": "traffic_signals"},
                    {"barrier": "gate"},
                    np.nan,
                ]
            }
        )
        normalized = normalize_node_columns(nodes)
        self.assertEqual(normalized["highway"].tolist()[0], "traffic_signals")
        self.assertTrue(pd.isna(normalized["highway"].iloc[1]))
        self.assertTrue(pd.isna(normalized["highway"].iloc[2]))

    def test_leaves_existing_highway_column_untouched(self):
        # osmnx-sourced nodes already have a real `highway` column.
        nodes = pd.DataFrame({"highway": ["stop"], "tags": [{"unused": "value"}]})
        normalized = normalize_node_columns(nodes)
        self.assertEqual(normalized["highway"].iloc[0], "stop")

    def test_no_tags_column_falls_back_to_nan(self):
        nodes = pd.DataFrame({"x": [1.0], "y": [2.0]})
        normalized = normalize_node_columns(nodes)
        self.assertIn("highway", normalized.columns)
        self.assertTrue(pd.isna(normalized["highway"].iloc[0]))


class TestExtractBicycleRouteNames(unittest.TestCase):
    def _mock_relations(self, relations_df):
        patcher = mock.patch("pyrosm.OSM")
        mock_osm_cls = patcher.start()
        self.addCleanup(patcher.stop)
        mock_osm_cls.return_value.get_data_by_custom_criteria.return_value = relations_df
        return mock_osm_cls

    def test_named_relation_fills_way_ids(self):
        tags = json.dumps(
            {
                "name": "Ciclovia Test",
                "members": [
                    {"member_id": 111, "member_type": "way", "member_role": ""},
                    {"member_id": 222, "member_type": "way", "member_role": ""},
                    {"member_id": 333, "member_type": "node", "member_role": ""},
                ],
            }
        )
        self._mock_relations(pd.DataFrame({"tags": [tags]}))
        result = extract_bicycle_route_names("fake.osm.pbf")
        self.assertEqual(result, {111: "Ciclovia Test", 222: "Ciclovia Test"})

    def test_unnamed_relation_falls_back_to_ref(self):
        # Reproduces Trento's "Bicipolitana" tagging: cycle_network + ref +
        # colour, no name at all on the relation.
        tags = json.dumps(
            {
                "ref": "7",
                "colour": "purple",
                "cycle_network": "it:tn:tn:bicipolitana_trento",
                "members": [{"member_id": 999, "member_type": "way", "member_role": ""}],
            }
        )
        self._mock_relations(pd.DataFrame({"tags": [tags]}))
        result = extract_bicycle_route_names("fake.osm.pbf")
        self.assertEqual(result, {999: "Linea 7"})

    def test_relation_without_name_or_ref_is_skipped(self):
        tags = json.dumps({"members": [{"member_id": 1, "member_type": "way", "member_role": ""}]})
        self._mock_relations(pd.DataFrame({"tags": [tags]}))
        result = extract_bicycle_route_names("fake.osm.pbf")
        self.assertEqual(result, {})

    def test_way_in_multiple_relations_joins_names(self):
        tags1 = json.dumps({"name": "EuroVelo 7", "members": [{"member_id": 42, "member_type": "way", "member_role": ""}]})
        tags2 = json.dumps({"ref": "3", "members": [{"member_id": 42, "member_type": "way", "member_role": ""}]})
        self._mock_relations(pd.DataFrame({"tags": [tags1, tags2]}))
        result = extract_bicycle_route_names("fake.osm.pbf")
        self.assertEqual(result, {42: "EuroVelo 7 / Linea 3"})

    def test_empty_relations_returns_empty_dict(self):
        self._mock_relations(pd.DataFrame())
        self.assertEqual(extract_bicycle_route_names("fake.osm.pbf"), {})

    def test_none_relations_returns_empty_dict(self):
        self._mock_relations(None)
        self.assertEqual(extract_bicycle_route_names("fake.osm.pbf"), {})


class TestApplyRouteNameFallback(unittest.TestCase):
    def test_fills_missing_name_only(self):
        edges = pd.DataFrame({"osmid": [1, 2, 3], "name": [np.nan, "Existing", ""]})
        result = apply_route_name_fallback(edges, {1: "Linea 7", 3: "Linea 8"})
        self.assertEqual(result["name"].tolist(), ["Linea 7", "Existing", "Linea 8"])

    def test_no_match_leaves_name_missing(self):
        edges = pd.DataFrame({"osmid": [1], "name": [np.nan]})
        result = apply_route_name_fallback(edges, {999: "Linea 7"})
        self.assertTrue(pd.isna(result["name"].iloc[0]))

    def test_empty_route_names_is_noop(self):
        edges = pd.DataFrame({"osmid": [1], "name": [np.nan]})
        result = apply_route_name_fallback(edges, {})
        self.assertTrue(pd.isna(result["name"].iloc[0]))

    def test_missing_osmid_column_is_noop(self):
        edges = pd.DataFrame({"name": [np.nan]})
        result = apply_route_name_fallback(edges, {1: "Linea 7"})
        self.assertTrue(pd.isna(result["name"].iloc[0]))

    def test_missing_name_column_is_created(self):
        edges = pd.DataFrame({"osmid": [1]})
        result = apply_route_name_fallback(edges, {1: "Linea 7"})
        self.assertEqual(result["name"].iloc[0], "Linea 7")

    def test_list_osmid_uses_first_element(self):
        edges = pd.DataFrame({"osmid": [[1, 2]], "name": [np.nan]})
        result = apply_route_name_fallback(edges, {1: "Linea 7"})
        self.assertEqual(result["name"].iloc[0], "Linea 7")

    def test_does_not_mutate_input(self):
        edges = pd.DataFrame({"osmid": [1], "name": [np.nan]})
        apply_route_name_fallback(edges, {1: "Linea 7"})
        self.assertTrue(pd.isna(edges["name"].iloc[0]))


if __name__ == "__main__":
    unittest.main()
