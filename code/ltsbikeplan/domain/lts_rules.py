import numpy as np
import pandas as pd

# sac_scale values beyond plain "hiking" (T1) - roots, exposure, scrambling -
# aren't something a city or e-bike can realistically ride, even though the
# way is legally a highway=path/footway. mtb:scale >= 2 is the same idea
# from the mountain-bike side: per the OSM wiki, 0-1 are rideable on a
# hybrid, 2+ needs real technical MTB handling. See
# BikePathAnalysis.is_separated_path.
_HARD_SAC_SCALE_VALUES = {
    "mountain_hiking",
    "demanding_mountain_hiking",
    "alpine_hiking",
    "demanding_alpine_hiking",
    "difficult_alpine_hiking",
}
_HARD_MTB_SCALE_MIN = 2


class BikePathAnalysis:
    @staticmethod
    def steps_analysis(gdf_edges):
        # highway=steps is stairs - not rideable at all, unless the way also
        # carries a bicycle ramp (ramp=yes or ramp:bicycle=yes), in which
        # case it's a dedicated low-stress facility (LTS 1). Handled before
        # biking_permitted() because the generic pipeline downstream
        # (is_separated_path/is_bike_lane/mixed_traffic) has no notion of
        # stairs and would otherwise fall through to a mixed-traffic default.
        gdf_edges = gdf_edges.copy()
        is_steps = gdf_edges["highway"] == "steps"

        ramp_yes = gdf_edges["ramp"] == "yes" if "ramp" in gdf_edges.columns else pd.Series(False, index=gdf_edges.index)
        ramp_bicycle_yes = (
            gdf_edges["ramp:bicycle"] == "yes"
            if "ramp:bicycle" in gdf_edges.columns
            else pd.Series(False, index=gdf_edges.index)
        )
        has_bicycle_ramp = ramp_yes | ramp_bicycle_yes

        steps_edges = gdf_edges[is_steps].copy()
        other_edges = gdf_edges[~is_steps]

        if not steps_edges.empty:
            steps_has_ramp = has_bicycle_ramp[is_steps]
            steps_edges["rule"] = np.where(steps_has_ramp, "p9", "p8")
            steps_edges["lts"] = np.where(steps_has_ramp, 1, 0)

        return steps_edges, other_edges

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

        # `motorroad=yes` is the OSM tag Italian mappers use for
        # tangenziali/superstrade where the Codice della Strada bars slow
        # vehicles regardless of whether a bicycle=no sign was ever mapped -
        # restricted to trunk/trunk_link since a motorroad=yes on a lower
        # class (e.g. a primary bypass) isn't the same legal category.
        motorroad_yes = (gdf_edges["motorroad"] == "yes") if "motorroad" in gdf_edges.columns else False
        trunk_motorroad = motorroad_yes & gdf_edges["highway"].isin(["trunk", "trunk_link"])

        conditions = [
            bicycle_no,
            (gdf_edges["access"] == "no"),
            (gdf_edges["highway"] == "motorway"),
            (gdf_edges["highway"] == "motorway_link"),
            (gdf_edges["highway"] == "proposed"),
            footway_sidewalk,
            trunk_motorroad,
        ]

        gdf_edges.loc[:, "rule"] = np.select(conditions, ["p2", "p6", "p3", "p4", "p7", "p5", "p10"], default="p0")

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

        # A highway=path/footway (s1/s2) isn't automatically a comfortable
        # cycling facility the way a dedicated cycleway is - it can just as
        # well be a genuine mountain trail. Where sac_scale/mtb:scale record
        # that, reclassify to "s9": not a stress level, a physical
        # impossibility for a city/e-bike, the same treatment
        # BikePathAnalysis.steps_analysis gives stairs without a ramp.
        # Restricted to s1/s2 - a cycleway (s3) or a track/opposite_track
        # cycleway (s7/s8) is road infrastructure, not a trail, so these
        # tags wouldn't apply there.
        natural_trail = gdf_edges["rule"].isin(["s1", "s2"])
        hard_sac_scale = gdf_edges["sac_scale"].isin(_HARD_SAC_SCALE_VALUES) if "sac_scale" in gdf_edges.columns else False
        if "mtb:scale" in gdf_edges.columns:
            hard_mtb_scale = pd.to_numeric(gdf_edges["mtb:scale"], errors="coerce") >= _HARD_MTB_SCALE_MIN
        else:
            hard_mtb_scale = False
        impassable_trail = natural_trail & (hard_sac_scale | hard_mtb_scale)
        gdf_edges.loc[impassable_trail, "rule"] = "s9"

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

        # OSM's `width` tag is free text in practice (units, typos, comma
        # decimals) - coerce to numeric so the `<=` comparisons below don't
        # crash on a str/float comparison. Non-numeric values become NaN and
        # fall through to the highway-based estimate right after, same as
        # values that were already missing.
        gdf_edges[width_column] = pd.to_numeric(gdf_edges[width_column], errors="coerce")

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

        # OSM's `width` tag is free text in practice (units, typos, comma
        # decimals) - coerce to numeric so the `<=` comparisons below don't
        # crash on a str/float comparison. Non-numeric values become NaN and
        # fall through to the highway-based estimate right after, same as
        # values that were already missing.
        gdf_edges[width_column] = pd.to_numeric(gdf_edges[width_column], errors="coerce")

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
