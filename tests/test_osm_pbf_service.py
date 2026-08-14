import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ltsbikeplan.services.osm_pbf_service import normalize_edge_columns, normalize_node_columns


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


if __name__ == "__main__":
    unittest.main()
