import numpy as np
import pandas as pd

# sac_scale values beyond plain "hiking" (T1) - roots, exposure, scrambling -
# aren't something a city or e-bike can realistically ride, even though the
# way is legally a highway=path/footway. See BikePathAnalysis.is_separated_path.
#
# mtb:scale is deliberately NOT used here (it was, briefly) - even its
# lowest value (0, per the OSM wiki: "no particular difficulties") already
# describes terrain aimed at a mountain bike, not the city/e-bike audience
# this project is scoped to, so the tag can't usefully distinguish "fine
# for our riders" from "not." The dimension that should actually decide a
# trail's difficulty here is steepness, and that's already handled
# separately and more granularly by BikePathAnalysis.slope_penalty.
_HARD_SAC_SCALE_VALUES = {
    "mountain_hiking",
    "demanding_mountain_hiking",
    "alpine_hiking",
    "demanding_alpine_hiking",
    "difficult_alpine_hiking",
}

# Surface quality LTS penalty (BikePathAnalysis.surface_penalty) - none of
# the rules above look at `surface` at all, so a ground/dirt cycleway and a
# paved one both land on the same lts today. Two tiers: MODERATE is
# rideable on most bikes with extra effort (compacted gravel, cobblestone),
# SEVERE is meaningfully harder or risky especially wet (loose dirt, sand,
# mud, snow/ice, loose pebblestone). Anything not listed - paved surfaces,
# and a missing/unset `surface` tag (common in OSM) - gets no penalty, same
# "don't penalize missing data" convention as slope_penalty/get_average_
# width_based_on_highway.
_MODERATE_SURFACE_VALUES = {
    "compacted",
    "fine_gravel",
    "gravel",
    "sett",
    "cobblestone",
    "unhewn_cobblestone",
    "woodchips",
    "unpaved",
}
_SEVERE_SURFACE_VALUES = {
    "ground",
    "dirt",
    "earth",
    "sand",
    "mud",
    "grass",
    "pebblestone",
    "ice",
    "snow",
}
# SEVERE is a flat +1 regardless of length - losing traction on sand/mud/
# ground is an immediate problem, not one that only matters once it's
# accumulated over distance the way climbing effort does, but capped at
# the same +1 a short stretch gets (real case: a beach-access path in
# Pachino, OSM way 1160130131, chopped into a dozen ~15-28m graph edges by
# intersection nodes - it's a car-free separated path either way, just a
# physically harder one, not worth the full +2 slope_penalty gives a
# genuinely steep/long climb). MODERATE keeps the same 500m long-segment
# threshold as slope_penalty (a short rough patch of compacted gravel is
# genuinely tolerable).
_MODERATE_SURFACE_LONG_THRESHOLD_M = 500.0


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

    # access values meaning "not open to the general public, only with the
    # owner's permission" - computing an LTS for these makes no sense: a
    # street nobody but a permit-holder/customer/resident can legally enter
    # isn't part of the public cycling network. "no" is handled by its own
    # p6 condition below (unchanged rule code, kept distinct from p11 since
    # it's the one value LTS_decisionrule_dict.json already documents from
    # the reproduced paper). "destination" is included here (not just "no
    # through traffic") per explicit product decision: entry still requires
    # the street to actually BE your destination, not general cycling
    # access. All excluded UNLESS a more specific bicycle=* tag explicitly
    # overrides the general access restriction (see bicycle_permitted_
    # override below) - standard OSM tag-hierarchy convention, e.g.
    # access=destination + bicycle=yes means cyclists specifically are let
    # through even though the general public isn't.
    #
    # "private" is deliberately NOT in this set (see access_private below):
    # unlike the other restricted values, a bicycle=yes/designated/... next
    # to access=private is treated as a mapper mistake, not a genuine
    # cyclist-specific carve-out - product decision, since "private" means
    # the owner personally admits people, and a blanket bicycle=designated
    # can't stand in for that individual permission the way it can for a
    # generic "customers"/"destination" restriction.
    _RESTRICTED_ACCESS_VALUES = {"permit", "customers", "delivery", "agricultural", "forestry", "destination", "military"}

    @staticmethod
    def biking_permitted(gdf_edges):
        gdf_edges = gdf_edges.copy()
        has_bicycle_col = "bicycle" in gdf_edges.columns
        bicycle_no = (gdf_edges["bicycle"] == "no") if has_bicycle_col else False
        bicycle_yes = (gdf_edges["bicycle"] == "yes") if has_bicycle_col else pd.Series(False, index=gdf_edges.index)
        # Broader than bicycle_yes above (which only means "not a sidewalk
        # exclusion" for footway_sidewalk below) - any of these values is an
        # explicit, cycling-specific permission that should win over a
        # general access=private/destination/... restriction or a plain
        # highway=service exclusion (see restricted_access/service_excluded
        # below).
        bicycle_permitted_override = (
            gdf_edges["bicycle"].isin(["yes", "designated", "permissive", "official"])
            if has_bicycle_col
            else pd.Series(False, index=gdf_edges.index)
        )

        if "footway" in gdf_edges.columns:
            footway_sidewalk = (
                (gdf_edges["footway"] == "sidewalk")
                & ~bicycle_yes
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

        # "no" kept as its own condition/rule code (p6, unchanged) rather
        # than folded into restricted_access below - see the class-level
        # comment on _RESTRICTED_ACCESS_VALUES.
        access_no = (gdf_edges["access"] == "no") & ~bicycle_permitted_override
        # No bicycle_permitted_override here, unlike access_no/restricted_
        # access below - see the _RESTRICTED_ACCESS_VALUES comment for why
        # access=private stays excluded even next to bicycle=designated.
        access_private = gdf_edges["access"] == "private"
        restricted_access = (
            gdf_edges["access"].isin(BikePathAnalysis._RESTRICTED_ACCESS_VALUES) & ~bicycle_permitted_override
        )
        # Only service=driveway (single-property access), emergency_access
        # (restricted to emergency vehicles), and parking_aisle (the
        # internal lanes of a parking lot - almost never a through-route,
        # usually a dead-end branch that only reaches parking spaces) are
        # excluded here - NOT every highway=service. A service road with no
        # sub-tag, or service=alley, is often shared/quasi-public
        # infrastructure a cyclist can actually use - in practice
        # frequently the literal entry point onto a real cycleway (a short
        # service-tagged connector, sometimes a chain of them, before
        # reaching the ciclabile itself). Blanket-excluding all of
        # highway=service broke exactly those connections. mixed_traffic
        # below already scores alley/generic service (m2/m16) same as
        # before; genuinely private access is still caught separately by
        # access=private/... above regardless of highway type.
        service_value = gdf_edges["service"] if "service" in gdf_edges.columns else pd.Series(None, index=gdf_edges.index)
        service_excluded = service_value.isin(["driveway", "emergency_access", "parking_aisle"]) & ~bicycle_permitted_override

        conditions = [
            bicycle_no,
            access_no,
            access_private,
            (gdf_edges["highway"] == "motorway"),
            (gdf_edges["highway"] == "motorway_link"),
            (gdf_edges["highway"] == "proposed"),
            footway_sidewalk,
            trunk_motorroad,
            restricted_access,
            service_excluded,
        ]

        gdf_edges.loc[:, "rule"] = np.select(
            conditions, ["p2", "p6", "p13", "p3", "p4", "p7", "p5", "p10", "p11", "p12"], default="p0"
        )

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
        # well be a genuine mountain trail. Where sac_scale records that,
        # reclassify to "s9": not a stress level, a physical impossibility
        # for a city/e-bike, the same treatment BikePathAnalysis.steps_
        # analysis gives stairs without a ramp. Restricted to s1/s2 - a
        # cycleway (s3) or a track/opposite_track cycleway (s7/s8) is road
        # infrastructure, not a trail, so this tag wouldn't apply there.
        # (mtb:scale was checked here too at one point - see
        # _HARD_SAC_SCALE_VALUES above for why it was dropped.)
        natural_trail = gdf_edges["rule"].isin(["s1", "s2"])
        hard_sac_scale = gdf_edges["sac_scale"].isin(_HARD_SAC_SCALE_VALUES) if "sac_scale" in gdf_edges.columns else False
        impassable_trail = natural_trail & hard_sac_scale
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

        def parse_lanes(val):
            # OSM's `lanes` tag is meant to be a plain integer (or a list
            # of them, for the rare way carrying more than one lanes:*
            # sub-value) - real-world tagging isn't always clean, though: a
            # single malformed way in Polistena had lanes="\\" (a literal
            # backslash), crashing `np.array(x, dtype="int")` with
            # `ValueError: invalid literal for int() with base 10: '\\'`
            # and taking down the whole area's compute-lts run over one bad
            # tag. Anything that doesn't parse as an int now falls back to
            # default_lanes instead.
            values = val if isinstance(val, list) else [val]
            parsed = []
            for item in values:
                try:
                    parsed.append(int(item))
                except (ValueError, TypeError):
                    pass
            return max(parsed) if parsed else default_lanes

        gdf_edges["lanes_assumed"] = gdf_edges["lanes"].fillna(default_lanes).apply(parse_lanes)
        return gdf_edges

    @staticmethod
    def get_max_speed(gdf_edges, national=90, local=50, motorway=130, primary=90, secondary=90, urban=50):
        # Italian "Zona 30" (and other countries' equivalent traffic-calmed
        # zones) are frequently tagged ONLY with zone:maxspeed=IT:30 - no
        # plain maxspeed at all, since the limit comes from the zone, not
        # signage on this specific way. Without this, such a way fell
        # through to the generic `local` (50) default below, understating
        # how calm it actually is - a real accuracy gap, not just a missing
        # nicety, since every mixed_traffic/bike-lane rule in this file is a
        # <=40/<=50/... speed-threshold check. Takes priority over the
        # highway-type defaults right below (motorway/primary/secondary/
        # urban) since an explicit zone designation is more specific/
        # authoritative than a guess from road class - but never overrides
        # a real `maxspeed` value already on the way itself.
        def parse_zone_maxspeed(val):
            item = val[0] if isinstance(val, list) and val else val
            if not isinstance(item, str):
                return np.nan
            try:
                return int(item.split(":")[-1])
            except ValueError:
                return np.nan

        zone_speed = gdf_edges["zone:maxspeed"].apply(parse_zone_maxspeed)

        conditions = [
            (gdf_edges["maxspeed"] == "national"),
            (gdf_edges["maxspeed"].isna()) & zone_speed.notna(),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "motorway"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "primary"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "secondary"),
            (gdf_edges["maxspeed"].isna()) & (gdf_edges["highway"] == "urban"),
            (gdf_edges["maxspeed"].isna()),
        ]
        values = [national, zone_speed, motorway, primary, secondary, urban, local]
        gdf_edges["maxspeed_assumed"] = np.select(conditions, values, default=gdf_edges["maxspeed"])

        # OSM's implicit-speed-limit convention for Italy (see the "Default
        # speed limits" table on the OSM wiki): maxspeed can be a zone name
        # instead of a number, meaning "whatever the legal default is for
        # this road type" - IT:urban=50 (already handled), but IT:rural=90
        # and IT:motorway=130 were missing, so a "IT:rural" tag (confirmed
        # live: 54 edges in Paceco, all highway=tertiary) fell all the way
        # through to `return val`, leaving the literal string "IT:rural" in
        # maxspeed_assumed - crashed the very next comparison against it
        # (`<= 50` etc. throughout this file) with `TypeError: '<=' not
        # supported between instances of 'str' and 'int'`. Any other
        # unrecognized string/empty list now falls back to `local` (the
        # same default already used above for a genuinely missing maxspeed)
        # instead of leaking a non-numeric value into a column every rule
        # in this file assumes is numeric.
        known_speed_zones = {"IT:urban": urban, "IT:rural": national, "IT:motorway": motorway}

        def convert_to_int(val):
            if isinstance(val, list):
                int_list = []
                for item in val:
                    try:
                        int_list.append(int(item))
                    except ValueError:
                        if item in known_speed_zones:
                            int_list.append(known_speed_zones[item])
                return max(int_list) if int_list else local
            try:
                return int(val)
            except ValueError:
                return known_speed_zones.get(val, local)

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

        # A real state/provincial/regional road (Italy: SS/SP/SR, similar
        # conventions elsewhere) reliably carries a `ref`, regardless of
        # its `highway` tag - but `highway=tertiary`/`unclassified`/
        # `service` is also routinely used in Italian OSM mapping practice
        # for a quiet local connector that's functionally no different
        # from a `residential` street (same real traffic, same speed/lane
        # count), just tagged one notch up by convention. Below, only
        # THESE three highway values get the ref-based leniency - not
        # every non-residential class - because the confirmed real case
        # this fixes (Trento's "Strada Imperiale"/Civezzano's "Strada alla
        # Fersina": tertiary, no ref, genuinely a quiet hillside road) and
        # its confirmed counter-case (Bolzano's "Strada Statale
        # dell'Abetone e del Brennero"/"Via Sarentino": primary and
        # unclassified segments of the SAME real state highways, WITH a
        # ref) are both in this set. `primary`/`secondary`/`trunk` are
        # deliberately excluded - those functional classes reliably mean a
        # real through-road even on the rare way that's missing its `ref`.
        has_ref = (
            gdf_edges["ref"].notna() & (gdf_edges["ref"].astype(str).str.strip() != "")
            if "ref" in gdf_edges.columns
            else pd.Series(False, index=gdf_edges.index)
        )
        residential_equivalent = (gdf_edges["highway"] == "residential") | (
            gdf_edges["highway"].isin(["tertiary", "unclassified", "service"]) & ~has_ref
        )

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
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 3) & residential_equivalent,
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 3),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] <= 5),
            (gdf_edges["maxspeed_assumed"] <= 40) & (gdf_edges["lanes_assumed"] > 5),
            (gdf_edges["maxspeed_assumed"] <= 50) & (gdf_edges["lanes_assumed"] < 3) & residential_equivalent,
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
        # MIN_RELIABLE_SLOPE_LENGTH_M: below this, the DEM-derived `slope`
        # value isn't trustworthy enough to penalize on, regardless of how
        # steep it claims to be. The Mapterhorn DEM is ~10m/cell, and an
        # edge's slope is the MEAN of whichever raster cells its geometry
        # crosses - a short edge crosses too few cells for that mean to
        # mean anything. Measured directly against a real batch of short
        # (<40m) edges wrongly bumped to LTS4 in Trento: median length
        # 17.8m crossing a median of only 3.5 cells (a quarter crossed 1-2
        # cells, one as few as a single 2.3m/1-cell edge), with a per-edge
        # cell-to-cell std of up to ~6 degrees - i.e. the "slope" swings by
        # several degrees between adjacent 10m cells within the SAME short
        # edge, which is measurement noise, not a real grade. Standard
        # error of that mean shrinks as sigma/sqrt(n_cells); solving for
        # n_cells against the observed sigma (~1-3 degrees) to keep the
        # residual error under ~1 degree (half a slope_class band's width)
        # needs roughly 4-36 cells, i.e. ~40-360m depending on how
        # conservative you want to be - 500m clears even the conservative
        # end with margin, so it's kept as the one length threshold here
        # (previously only gated "5-8: medium"; now also gates "8-10: hard"
        # and worse, which had no length floor at all before - exactly
        # what let a noisy 8m-long reading through).
        MIN_RELIABLE_SLOPE_LENGTH_M = 500

        if edges.empty:
            return edges

        # osmnx splits a single OSM way into one graph edge per node it
        # touches - including nodes that only exist because a driveway,
        # footway or flight of steps crosses it, not just real branching
        # intersections. A long, genuinely steep way can end up as a dozen+
        # short fragments, each individually under
        # MIN_RELIABLE_SLOPE_LENGTH_M, so no fragment ever qualified for a
        # slope penalty even though the whole way clearly should have
        # (reported live: OSM way 50240143 in Arenzano, a ~503m/~12% grade
        # tertiary road split into ~15 fragments of 2.7-112m, none reaching
        # 500m - some fragments read very high/noisy slope values, but
        # every one was individually "unreliable"). Reliability is
        # therefore judged on the summed length of every fragment sharing
        # the same osmid, and the grade on their length-weighted mean
        # (equivalent to total elevation change / total length) - not on
        # each fragment in isolation. Same osmid normalization as
        # pipeline/compute_lts.py's later `_flatten_tag`: a rare merged
        # edge (multiple original ways collapsed into one by osmnx's graph
        # simplification) can carry `osmid` as a list - the first value
        # stands in as the group key there too.
        def _osmid_key(value):
            return value[0] if isinstance(value, list) and value else value

        osmid_key = edges["osmid"].map(_osmid_key)
        group_length = edges["length"].groupby(osmid_key).transform("sum")

        # The weighted mean is taken only over fragments with a known
        # slope (DEM sampling can fail per-fragment, e.g. a nodata pixel),
        # so one NaN fragment doesn't silently drag down the group average
        # - if every fragment in a group lacks slope data, group_slope
        # comes out NaN and the group gets no penalty, same "don't
        # penalize missing data" convention as elsewhere in this file.
        slope_known = edges["slope"].notna()
        known_length = edges["length"].where(slope_known, 0)
        known_length_sum = known_length.groupby(osmid_key).transform("sum")
        weighted_rise_sum = (edges["slope"] * known_length).groupby(osmid_key).transform("sum")
        with np.errstate(invalid="ignore"):
            group_slope = weighted_rise_sum / known_length_sum
        group_slope = group_slope.where(known_length_sum > 0)
        group_slope_class = pd.cut(
            group_slope,
            bins=[0, 3, 5, 8, 10, 20, np.inf],
            # Same bin edges/labels as services/slope_strategies.py's
            # _SLOPE_CLASS_BINS/_SLOPE_CLASS_LABELS (which produce the
            # per-fragment `slope_class` this replaces for the reliability
            # decision) - duplicated rather than imported to avoid a
            # domain -> services dependency; keep the two in sync.
            labels=["0-3: flat", "3-5: mild", "5-8: medium", "8-10: hard", "10-20: extreme", ">20: impossible"],
            right=False,
        )
        group_reliable = group_length >= MIN_RELIABLE_SLOPE_LENGTH_M

        def adjust_lts(lts, context, slope_class, reliable):
            # Same "don't touch an excluded edge" guard as surface_penalty's
            # `rideable = original_lts >= 1`: lts=0 here isn't a real comfort
            # score to escalate, it's "not applicable" (motorway, bicycle=no,
            # an s9 mountain trail too hard to ride, steps without a ramp) -
            # if bikes can't go there at all, slope doesn't matter and the
            # calculation is skipped entirely rather than run and capped.
            if lts < 1:
                return lts
            if context == "urban":
                if slope_class in ["0-3: flat", "3-5: mild"]:
                    return lts
                if slope_class == "5-8: medium":
                    return min(lts + 1, 4) if reliable else lts
                if slope_class in ["8-10: hard", "10-20: extreme", ">20: impossible"]:
                    return min(lts + 2, 4) if reliable else lts
                return lts
            if slope_class in ["8-10: hard", "10-20: extreme", ">20: impossible"]:
                return min(lts + 2, 4) if reliable else lts
            return lts

        edges = edges.copy()
        edges["lts"] = [
            adjust_lts(lts, context, slope_class, reliable)
            for lts, context, slope_class, reliable in zip(
                edges["lts"], edges["context"], group_slope_class, group_reliable
            )
        ]
        return edges

    @staticmethod
    def surface_penalty(edges):
        """Surface-quality LTS penalty - a ground/gravel path is objectively
        more effortful than pavement, but no other rule ever looks at
        `surface`. SEVERE is a flat +1, any length. MODERATE is length-gated
        like slope_penalty (see _MODERATE_SURFACE_LONG_THRESHOLD_M above):
        +1 at length>=500m, +0 below. Vectorized (unlike slope_penalty's
        row-by-row `.apply`) - this runs on the same all_lts frame the rest
        of compute_lts.py is trying to keep fast at province scale.

        Only touches already-classified edges (lts >= 1): an excluded edge
        (lts=0 - motorway, bicycle=no, an s9 mountain trail too hard to
        ride at all) must stay excluded regardless of its surface, not get
        bumped back into the rideable 1-4 scale.

        Also records `surface_penalty_delta` - the EFFECTIVE change (post
        4-cap), not the nominal tier penalty - so the web popup can say
        "LTS raised by N for this surface" and have N match what the
        displayed LTS actually did (see i18n.js's surfacePenaltyTemplate /
        app.js's popupHtml). An edge already at lts=3 hit by a nominal +2
        only really moved by 1 once capped; the message should say 1, not 2.
        """
        edges = edges.copy()
        original_lts = edges["lts"]
        length = edges["length"]
        moderate_long = length.notna() & (length >= _MODERATE_SURFACE_LONG_THRESHOLD_M)
        rideable = original_lts >= 1
        is_severe = edges["surface"].isin(_SEVERE_SURFACE_VALUES)
        is_moderate = edges["surface"].isin(_MODERATE_SURFACE_VALUES)

        penalty = np.select(
            [
                rideable & is_severe,
                rideable & is_moderate & moderate_long,
            ],
            [1, 1],
            default=0,
        )
        new_lts = np.minimum(original_lts + penalty, 4)
        edges["surface_penalty_delta"] = new_lts - original_lts
        edges["lts"] = new_lts
        return edges
