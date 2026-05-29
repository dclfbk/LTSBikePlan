import numpy as np


class BikePathAnalysis:
    @staticmethod
    def biking_permitted(gdf_edges):
        gdf_edges = gdf_edges.copy()
        bicycle_no = (gdf_edges["bicycle"] == "no") if "bicycle" in gdf_edges.columns else False

        if "footway" in gdf_edges.columns:
            footway_sidewalk = (
                (gdf_edges["footway"] == "sidewalk")
                & ~(gdf_edges["bicycle"] == "yes")
                & ((gdf_edges["highway"] == "footway") | (gdf_edges["highway"] == "path"))
            )
        else:
            footway_sidewalk = False

        conditions = [
            bicycle_no,
            (gdf_edges["access"] == "no"),
            (gdf_edges["highway"] == "motorway"),
            (gdf_edges["highway"] == "motorway_link"),
            (gdf_edges["highway"] == "proposed"),
            footway_sidewalk,
        ]

        gdf_edges.loc[:, "rule"] = np.select(conditions, ["p2", "p6", "p3", "p4", "p7", "p5"], default="p0")

        gdf_allowed = gdf_edges[gdf_edges["rule"] == "p0"]
        gdf_not_allowed = gdf_edges[gdf_edges["rule"] != "p0"]

        return gdf_allowed, gdf_not_allowed

    @staticmethod
    def is_separated_path(gdf_edges):
        gdf_edges = gdf_edges.copy()
        cycleway_tags = BikePathAnalysis._get_columns_by_prefix(gdf_edges, "cycleway")
        cycleway_track_condition = False
        cycleway_opposite_track_condition = False

        if cycleway_tags:
            cycleway_track_condition = (gdf_edges[cycleway_tags] == "track").any(axis=1)
            cycleway_opposite_track_condition = (gdf_edges[cycleway_tags] == "opposite_track").any(axis=1)

        if "footway" in gdf_edges.columns:
            footway_condition = (gdf_edges["highway"] == "footway") & ~(gdf_edges["footway"] == "crossing")
        else:
            footway_condition = gdf_edges["highway"] == "footway"

        conditions = [
            (gdf_edges["highway"] == "cycleway"),
            (gdf_edges["highway"] == "path"),
            footway_condition,
            cycleway_track_condition,
            cycleway_opposite_track_condition,
        ]

        gdf_edges.loc[:, "rule"] = np.select(conditions, ["s3", "s1", "s2", "s7", "s8"], default="s0")

        separated = gdf_edges[gdf_edges["rule"] != "s0"]
        not_separated = gdf_edges[gdf_edges["rule"] == "s0"].drop(columns="rule")

        return separated, not_separated

    @staticmethod
    def is_bike_lane(gdf_edges):
        gdf_edges = gdf_edges.copy()
        cycleway_tags = BikePathAnalysis._get_columns_by_prefix(gdf_edges, "cycleway")
        lane_identifiers = ["crossing", "lane", "left", "opposite", "opposite_lane", "right", "yes"]

        if "shoulder:access:bicycle" in gdf_edges.columns:
            lane_check = ((gdf_edges[cycleway_tags].isin(lane_identifiers).any(axis=1)) | (gdf_edges["shoulder:access:bicycle"] == "yes"))
        else:
            lane_check = gdf_edges[cycleway_tags].isin(lane_identifiers).any(axis=1)

        to_analyze = gdf_edges[lane_check]
        no_lane = gdf_edges[~lane_check]

        return to_analyze, no_lane

    @staticmethod
    def _get_columns_by_prefix(gdf, prefix):
        return [col for col in gdf.columns if col.startswith(prefix)]

    @staticmethod
    def parking_present(gdf_edges):
        parking_tags = BikePathAnalysis._get_columns_by_prefix(gdf_edges, "parking")
        parking_identifiers = ["yes", "parallel", "perpendicular", "diagonal", "marked"]
        parking_check = gdf_edges[parking_tags].isin(parking_identifiers).any(axis=1)

        parking_detected = gdf_edges[parking_check]
        parking_not_detected = gdf_edges[~parking_check]

        return parking_detected, parking_not_detected

    @staticmethod
    def get_lanes(gdf_edges, default_lanes=2):
        gdf_edges.loc[gdf_edges["oneway"] == True, "lanes"] = 1
        gdf_edges["lanes_assumed"] = (
            gdf_edges["lanes"].fillna(default_lanes).apply(lambda x: np.array(x, dtype="int")).apply(lambda x: np.max(x))
        )
        return gdf_edges

    @staticmethod
    def get_max_speed(gdf_edges, national=90, local=50, motorway=130, primary=90, secondary=90, urban=50):
        conditions = [
            (gdf_edges["maxspeed"] == "national"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "motorway"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "primary"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "secondary"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "urban"),
            (gdf_edges["maxspeed"].isna()),
        ]
        values = [national, motorway, primary, secondary, urban, local]
        gdf_edges["maxspeed_assumed"] = np.select(conditions, values, default=gdf_edges["maxspeed"])

        def convert_to_int(val):
            if isinstance(val, list):
                int_list = []
                for item in val:
                    try:
                        int_list.append(int(item))
                    except ValueError:
                        if item == "IT:urban":
                            int_list.append(urban)
                return max(int_list) if int_list else val
            try:
                return int(val)
            except ValueError:
                if val == "IT:urban":
                    return urban
                return val

        gdf_edges["maxspeed_assumed"] = gdf_edges["maxspeed_assumed"].apply(convert_to_int)
        return gdf_edges

    @staticmethod
    def get_average_width_based_on_highway(highway_type, is_oneway):
        if highway_type == "motorway":
            return 11.25
        if highway_type == "primary":
            width = 7
        elif highway_type == "secondary":
            width = 6
        else:
            width = 5
        if is_oneway and highway_type != "motorway":
            width /= 2
        return width

    @staticmethod
    def bike_lane_analysis_with_parking(gdf_edges):
        gdf_edges = BikePathAnalysis.get_lanes(gdf_edges)
        gdf_edges = BikePathAnalysis.get_max_speed(gdf_edges)

        if "width" in gdf_edges.columns:
            width_column = "width"
        elif "est_width" in gdf_edges.columns:
            width_column = "est_width"
        else:
            gdf_edges["width"] = np.nan
            width_column = "width"

        missing_widths = gdf_edges[width_column].isna()
        gdf_edges.loc[missing_widths, width_column] = gdf_edges[missing_widths].apply(
            lambda row: BikePathAnalysis.get_average_width_based_on_highway(row["highway"], row["oneway"]), axis=1
        )

        conditions = [
            (gdf_edges["lanes_assumed"] >= 3) & (gdf_edges["maxspeed_assumed"] <= 55),
            (gdf_edges[width_column] <= 4.1),
            (gdf_edges[width_column] <= 4.25),
            (gdf_edges[width_column] <= 4.5) & ((gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["highway"] == "residential")),
            (gdf_edges["maxspeed_assumed"] > 40) & (gdf_edges["maxspeed_assumed"] <= 50),
            (gdf_edges["maxspeed_assumed"] > 50) & (gdf_edges["maxspeed_assumed"] <= 55),
            (gdf_edges["maxspeed_assumed"] > 55),
            (gdf_edges["highway"] != "residential"),
        ]
        values = ["b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9"]
        gdf_edges["rule"] = np.select(conditions, values, default="b1")
        rule_dict = {"b1": 1, "b2": 3, "b3": 3, "b4": 2, "b5": 2, "b6": 2, "b7": 3, "b8": 4, "b9": 3}
        gdf_edges["lts"] = gdf_edges["rule"].map(rule_dict)
        return gdf_edges

    @staticmethod
    def bike_lane_analysis_without_parking(gdf_edges):
        gdf_edges = BikePathAnalysis.get_lanes(gdf_edges)
        gdf_edges = BikePathAnalysis.get_max_speed(gdf_edges)

        if "width" in gdf_edges.columns:
            width_column = "width"
        elif "est_width" in gdf_edges.columns:
            width_column = "est_width"
        else:
            gdf_edges["width"] = np.nan
            width_column = "width"

        missing_widths = gdf_edges[width_column].isna()
        gdf_edges.loc[missing_widths, width_column] = gdf_edges[missing_widths].apply(
            lambda row: BikePathAnalysis.get_average_width_based_on_highway(row["highway"], row["oneway"]), axis=1
        )

        conditions = [
            (gdf_edges["lanes_assumed"] >= 3) & (gdf_edges["maxspeed_assumed"] <= 55),
            (gdf_edges[width_column] <= 4.1),
            (gdf_edges[width_column] <= 4.25),
            (gdf_edges[width_column] <= 4.5) & ((gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["highway"] == "residential")),
            (gdf_edges["maxspeed_assumed"] > 40) & (gdf_edges["maxspeed_assumed"] <= 50),
            (gdf_edges["maxspeed_assumed"] > 50) & (gdf_edges["maxspeed_assumed"] <= 55),
            (gdf_edges["maxspeed_assumed"] > 55),
            (gdf_edges["highway"] != "residential"),
        ]

        values = ["b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9"]
        gdf_edges["rule"] = np.select(conditions, values, default="b1")
        rule_dict = {"b1": 1, "b2": 3, "b3": 3, "b4": 2, "b5": 2, "b6": 2, "b7": 3, "b8": 4, "b9": 3}
        gdf_edges["lts"] = gdf_edges["rule"].map(rule_dict)
        return gdf_edges

    @staticmethod
    def mixed_traffic(gdf_edges):
        gdf_edges = BikePathAnalysis.get_lanes(gdf_edges)
        gdf_edges = BikePathAnalysis.get_max_speed(gdf_edges)
        conditions = []
        values = []

        if "motor_vehicle" in gdf_edges.columns:
            conditions.append(gdf_edges["motor_vehicle"] == "no")
            values.append("m17")

        if "highway" in gdf_edges.columns:
            conditions.append(gdf_edges["highway"] == "pedestrian")
            values.append("m13")

            if "footway" in gdf_edges.columns:
                conditions.append((gdf_edges["highway"] == "footway") & (gdf_edges["footway"] == "crossing"))
                values.append("m14")

            if "service" in gdf_edges.columns:
                conditions.append((gdf_edges["highway"] == "service") & (gdf_edges["service"] == "alley"))
                values.append("m2")

            conditions.append(gdf_edges["highway"] == "track")
            values.append("m15")

        conditions.extend([
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["highway"] == "service") & (gdf_edges["service"] == "parking_aisle"),
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["highway"] == "service") & (gdf_edges["service"] == "driveway"),
            (gdf_edges["maxspeed_assumed"] <= 35) & (gdf_edges["highway"] == "service"),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 3) & (gdf_edges["highway"] == "residential"),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 3),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 5),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] > 5),
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["lanes_assumed"] < 3) & (gdf_edges["highway"] == "residential"),
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["lanes_assumed"] <= 3),
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["lanes_assumed"] > 3),
            (gdf_edges["maxspeed_assumed"] > 50),
        ])
        values.extend(["m3", "m4", "m16", "m5", "m6", "m7", "m8", "m9", "m10", "m11", "m12"])

        gdf_edges["rule"] = np.select(conditions, values, default="m0")

        rule_dict = {
            "m17": 1,
            "m13": 1,
            "m14": 2,
            "m2": 2,
            "m15": 2,
            "m3": 2,
            "m4": 2,
            "m16": 2,
            "m5": 2,
            "m6": 3,
            "m7": 3,
            "m8": 4,
            "m9": 2,
            "m10": 3,
            "m11": 4,
            "m12": 4,
        }
        gdf_edges["lts"] = gdf_edges["rule"].map(rule_dict)
        return gdf_edges

    @staticmethod
    def calculate_lts_nodes(row, all_lts):
        try:
            edges = all_lts.loc[row.name]
            max_lts = edges["lts"].max()
        except Exception:
            return np.nan, "Node not found in edges"

        control = row["highway"]
        if max_lts > 2:
            if control == "traffic_signals":
                return 2, "LTS 3-4 with traffic signals"
            return int(max_lts), "Node LTS is max intersecting LTS"
        if control in ["traffic_signals", "stop"]:
            return 1, "LTS 1-2 with traffic signals or stop"
        return int(max_lts), "Node LTS is max intersecting LTS"

    @staticmethod
    def slope_penalty(edges):
        def adjust_lts(row):
            if row["context"] == "urban":
                if row["slope_class"] in ["0-3: flat", "3-5: mild"]:
                    return row["lts"]
                if row["slope_class"] == "5-8: medium":
                    if not np.isnan(row["length"]) and row["length"] >= 500:
                        return min(row["lts"] + 1, 4)
                    if not np.isnan(row["length"]):
                        return row["lts"]
                if row["slope_class"] == "8-10: hard":
                    if not np.isnan(row["length"]) and row["length"] >= 500:
                        return min(row["lts"] + 2, 4)
                    if not np.isnan(row["length"]):
                        return min(row["lts"] + 1, 4)
                if row["slope_class"] in ["10-20: extreme", ">20: impossible"]:
                    return min(row["lts"] + 2, 4)
                return row["lts"]
            if row["slope_class"] in ["8-10: hard", "10-20: extreme", ">20: impossible"]:
                if not np.isnan(row["length"]) and row["length"] >= 500:
                    return min(row["lts"] + 2, 4)
                return min(row["lts"] + 1, 4)
            return row["lts"]

        edges["lts"] = edges.apply(adjust_lts, axis=1)
        return edges
