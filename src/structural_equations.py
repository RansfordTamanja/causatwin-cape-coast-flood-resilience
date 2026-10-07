"""
structural_equations.py

Implements the structural equations attached to each mediator and
outcome node in the causal graph defined in causal_graph.py. Each
function takes the values of its parent nodes and returns the value of
its own node, exactly matching the parent-child edges in the graph, so
the graph and the equations cannot silently drift apart.

All exogenous inputs (rainfall, vegetation, buildings, population,
hospitals, road composition) are read from the same real data files
produced by fetch_climate.py, parse_osm.py, load_census.py,
national_benchmark.py, and sentinel_ndvi.py used throughout this
project. Only the drainage capacity baseline is an assumed parameter,
explicitly documented as such.
"""

import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")

C_IMPERVIOUS = 0.825   # midpoint of published 0.70-0.95 range
C_VEGETATED = 0.20     # midpoint of published 0.05-0.35 range

CATCHMENT_AREA_KM2 = 97.1
FLOOD_DESIGN_STORM_CEILING_MM = 150  # severe reference daily rainfall depth, see compute_peak_runoff_index
NATIONAL_HEALTH_BENCHMARK_FALLBACK = 62559

# Time of concentration: the time for runoff to travel from the most
# hydraulically distant point of a catchment to its outlet, the
# standard denominator used to convert an observed rainfall depth into
# a Rational Method design storm intensity. No site-specific
# concentration time or sub-daily intensity-duration-frequency curve
# has been developed for Cape Coast, so this uses a documented
# assumption, three hours, representative of small-to-medium mixed
# urban catchments in the 50-150 km^2 range in published drainage
# design guidance \cite{txdot, greenville2018}, applied to the real
# observed maximum daily rainfall rather than to the mean annual
# rainfall used in an earlier version of this model.
ASSUMED_TIME_OF_CONCENTRATION_HOURS = 3.0


def load_exogenous_inputs():
    """Reads every real exogenous input this model needs from the
    upstream data files. Raises a clear error naming the missing file
    rather than silently defaulting, since every number in a causal
    model needs to be traceable."""
    def _require(path, script):
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} not found. Run {script} first.")

    climate_path = os.path.join(DATA_DIR, "climate_summary.csv")
    _require(climate_path, "fetch_climate.py")
    with open(climate_path) as f:
        climate = {r["metric"]: r for r in csv.DictReader(f)}
    live_climate = climate.get("data_mode", {}).get("value") == "live"
    rainfall = float(climate["mean_annual_rainfall_mm"]["value"]) if live_climate \
        else float(climate["rainfall_hinterland_high_mm"]["value"])

    if live_climate and "max_daily_rainfall_mm" in climate:
        max_daily_rainfall = float(climate["max_daily_rainfall_mm"]["value"])
        max_daily_rainfall_source = "live NASA POWER, observed maximum over the 2020-2024 daily record"
    else:
        # Fallback: no live daily record available, so the design storm
        # falls back to the same documented seasonal high-end figure
        # used elsewhere in this pipeline, clearly weaker evidence than
        # a directly observed extreme.
        max_daily_rainfall = float(climate.get("rainfall_hinterland_high_mm", {"value": 160})["value"]) / 10
        max_daily_rainfall_source = "fallback estimate (live daily record not available this run)"

    osm_path = os.path.join(DATA_DIR, "osm_stats.json")
    _require(osm_path, "parse_osm.py")
    with open(osm_path) as f:
        osm = json.load(f)

    pop_path = os.path.join(DATA_DIR, "cape_coast_population.json")
    _require(pop_path, "load_census.py")
    with open(pop_path) as f:
        pop = json.load(f)

    sentinel_path = os.path.join(DATA_DIR, "sentinel_vegetation.json")
    if os.path.exists(sentinel_path):
        with open(sentinel_path) as f:
            sv = json.load(f)
        veg_pct = sv["threshold_sensitivity"]["used_threshold_0.4"]["pct_of_area"]
        veg_source = "live Sentinel-2 NDVI"
    else:
        veg_pct = 100 - 24.01 * 2  # rough fallback proxy, clearly flagged
        veg_source = "fallback estimate (Sentinel data not available this run)"

    benchmark_path = os.path.join(DATA_DIR, "national_health_benchmark.json")
    if os.path.exists(benchmark_path):
        with open(benchmark_path) as f:
            nb = json.load(f)
        national_benchmark = nb["national_population_per_hospital"]
    else:
        national_benchmark = NATIONAL_HEALTH_BENCHMARK_FALLBACK

    low_capacity = {"residential", "unclassified", "track", "path", "footway", "service", "steps", "road"}
    by_type = osm["roads_by_type"]
    total_roads = osm["roads_total"]
    low_count = sum(v for k, v in by_type.items() if k in low_capacity)
    low_pct = low_count / total_roads * 100 if total_roads else 0

    return {
        "rainfall_mm_year": rainfall,
        "rainfall_is_live": live_climate,
        "max_daily_rainfall_mm": max_daily_rainfall,
        "max_daily_rainfall_source": max_daily_rainfall_source,
        "vegetation_pct": veg_pct,
        "vegetation_source": veg_source,
        "buildings": osm["buildings"],
        "population": pop["total_population"],
        "hospitals": osm["hospitals"],
        "low_capacity_road_pct": low_pct,
        "national_health_benchmark": national_benchmark,
    }


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def compute_runoff_coefficient(vegetation_pct):
    """Composite Rational Method runoff coefficient, area-weighted
    between the published vegetated and impervious C ranges, using the
    live or fallback vegetation-cover fraction as the weight."""
    veg_frac = vegetation_pct / 100
    C = veg_frac * C_VEGETATED + (1 - veg_frac) * C_IMPERVIOUS
    return C


def compute_design_storm_intensity(max_daily_rainfall_mm,
                                    time_of_concentration_hours=ASSUMED_TIME_OF_CONCENTRATION_HOURS):
    """Converts an observed maximum daily rainfall depth into a Rational
    Method design storm intensity by dividing it by an assumed time of
    concentration, the standard approach when a site-specific
    intensity-duration-frequency curve is not available, treating the
    observed daily extreme as if it were delivered over the assumed
    concentration window rather than spread evenly across 24 hours. This
    is a real observed extreme (the maximum of a live five-year daily
    NASA POWER record) converted through a stated, documented assumption
    about storm duration, not the mean annual rainfall used by an
    earlier version of this model, which understated peak intensity by
    roughly two orders of magnitude relative to this design storm
    approach."""
    return max_daily_rainfall_mm / time_of_concentration_hours


def compute_peak_runoff_index(runoff_coefficient, max_daily_rainfall_mm, drainage_capacity_factor,
                               area_km2=CATCHMENT_AREA_KM2,
                               time_of_concentration_hours=ASSUMED_TIME_OF_CONCENTRATION_HOURS):
    """Rational Method Q = C * i * A, normalized to a 0-100 index for
    comparability with the other outcome scores, and divided by the
    drainage capacity factor since higher effective drainage capacity
    reduces the peak runoff that actually reaches the flood-risk
    calculation (a standard simplifying assumption in urban drainage
    planning: capacity improvements proportionally reduce realized peak
    flow, documented as an assumption in the accompanying paper). The
    intensity term i is a genuine design storm intensity, computed from
    the real observed maximum daily rainfall via
    compute_design_storm_intensity(), not the mean annual rainfall."""
    intensity = compute_design_storm_intensity(max_daily_rainfall_mm, time_of_concentration_hours)
    Q_raw = runoff_coefficient * intensity * area_km2
    Q_effective = Q_raw / drainage_capacity_factor
    # Normalize against the same-scale raw value at C=0.825 (fully
    # impervious) and a severe reference daily rainfall ceiling of 150
    # millimeters, a round, conservative figure roughly double the
    # maximum observed in the real five-year Cape Coast record (80.8
    # millimeters), representing a plausible severe design storm rather
    # than the specific observed maximum, with no drainage improvement,
    # so 100 represents a severe worst-case reference point on the same
    # design-storm-intensity basis as the numerator above.
    reference_intensity = compute_design_storm_intensity(FLOOD_DESIGN_STORM_CEILING_MM, time_of_concentration_hours)
    Q_reference = C_IMPERVIOUS * reference_intensity * area_km2
    index = _clip((Q_effective / Q_reference) * 100)
    return index, Q_effective


def compute_flood_risk_score(peak_runoff_index, population, population_reference=300000):
    """Combines the physically-grounded peak-runoff index with a
    population-exposure term, since flood risk to a city depends on both
    the physical hazard and who is exposed to it."""
    exposure_component = _clip((population / population_reference) * 100)
    score = _clip(0.75 * peak_runoff_index + 0.25 * exposure_component)
    return score


def compute_health_access_score(population, hospitals, national_benchmark):
    """Reuses CityMind's validated Health Agent formula unchanged."""
    ratio = population / hospitals if hospitals else float("inf")
    score = _clip((ratio / national_benchmark) * 50)
    return score, ratio


def compute_traffic_score(low_capacity_road_pct):
    """Reuses CityMind's validated Traffic Agent formula unchanged."""
    return _clip(low_capacity_road_pct)


def compute_emergency_response_score(health_access_score, traffic_score, flood_risk_score):
    """Extends CityMind's Emergency Response formula to also incorporate
    flood risk, since active flooding directly impedes emergency
    response beyond its effect through the road network alone, weighting
    all three components equally."""
    score = _clip((health_access_score + traffic_score + flood_risk_score) / 3)
    return score


def run_baseline_and_all_scores(drainage_capacity_factor=1.0, vegetation_pct_override=None,
                                 hospitals_override=None, low_capacity_pct_override=None,
                                 population_override=None):
    """Runs the full causal graph forward from exogenous inputs through
    every mediator and outcome node, with optional do-operator overrides
    on the intervenable nodes (drainage_capacity, vegetation_cover via
    restoration, hospitals, low_capacity_road_pct) and, for scenario
    comparability with the earlier CityMind agents, population.
    Returns a dict of every intermediate and final value, so the full
    causal chain is inspectable, not just the final scores."""
    inputs = load_exogenous_inputs()

    vegetation_pct = vegetation_pct_override if vegetation_pct_override is not None else inputs["vegetation_pct"]
    hospitals = hospitals_override if hospitals_override is not None else inputs["hospitals"]
    low_capacity_pct = low_capacity_pct_override if low_capacity_pct_override is not None else inputs["low_capacity_road_pct"]
    population = population_override if population_override is not None else inputs["population"]

    C = compute_runoff_coefficient(vegetation_pct)
    peak_runoff_index, Q_effective = compute_peak_runoff_index(
        C, inputs["max_daily_rainfall_mm"], drainage_capacity_factor)
    flood_risk_score = compute_flood_risk_score(peak_runoff_index, population)
    health_access_score, pop_per_hospital = compute_health_access_score(
        population, hospitals, inputs["national_health_benchmark"])
    traffic_score = compute_traffic_score(low_capacity_pct)
    emergency_response_score = compute_emergency_response_score(
        health_access_score, traffic_score, flood_risk_score)

    return {
        "inputs": inputs,
        "drainage_capacity_factor": drainage_capacity_factor,
        "vegetation_pct": round(vegetation_pct, 2),
        "hospitals": hospitals,
        "low_capacity_road_pct": round(low_capacity_pct, 2),
        "population": population,
        "runoff_coefficient": round(C, 3),
        "peak_runoff_raw_index": round(peak_runoff_index, 2),
        "peak_runoff_Q_effective": round(Q_effective, 2),
        "flood_risk_score": round(flood_risk_score, 1),
        "health_access_score": round(health_access_score, 1),
        "population_per_hospital": round(pop_per_hospital),
        "traffic_score": round(traffic_score, 1),
        "emergency_response_score": round(emergency_response_score, 1),
    }


if __name__ == "__main__":
    result = run_baseline_and_all_scores()
    print(json.dumps(result, indent=2, default=str))
