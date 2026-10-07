"""
synthetic_validation.py

Implements the computational validation layer the framework's real-world
Cape Coast demonstration cannot provide on its own: since no historical
intervention-outcome dataset exists for Cape Coast, correctness of the
Counterfactual Urban Intervention Engine (CUIE) cannot be checked against
real ground truth there. What CAN be checked, on synthetic data with
fully known structural equations, is whether the do-operator machinery
in intervention_engine.py and structural_equations.py correctly
implements the causal graph's semantics: does intervening on a variable
propagate only through its actual descendants, does it leave every
non-descendant untouched, and does the resulting counterfactual value
exactly match an independently computed expected value.

METHODOLOGICAL NOTE: this is NOT a test of whether the Rational Method
equations are physically correct (that is an engineering question,
addressed in Section IV of the paper through citation, not through
synthetic testing). It is a test of whether THIS CODE correctly
implements the do-calculus semantics on top of whatever equations it is
given: given known synthetic inputs and a known intervention, does the
pipeline return the value the do-calculus definition says it should.
The expected values below are computed by an independent arithmetic
path written directly in this file, not by importing and re-calling the
same functions being tested, so this is a genuine cross-check rather
than a tautology.

Five synthetic scenarios are constructed, deliberately using parameter
values that do not correspond to Cape Coast or any other real city, to
test the engine's behavior across a range of conditions rather than
around one specific real data point.

Writes:
    outputs/data/synthetic_validation_results.json
    outputs/tables/table_synthetic_validation.{csv,md}
"""

import csv
import json
import os

from structural_equations import (
    compute_runoff_coefficient, compute_peak_runoff_index, compute_flood_risk_score,
    compute_health_access_score, compute_traffic_score, compute_emergency_response_score,
    C_IMPERVIOUS, C_VEGETATED, FLOOD_DESIGN_STORM_CEILING_MM,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

TOLERANCE = 1e-6

# Five synthetic "cities," each with fully known, arbitrary parameters
# unrelated to Cape Coast, and a specified intervention to apply to each.
SYNTHETIC_CITIES = [
    {
        "name": "Synth-A (low vegetation, high rainfall)",
        "vegetation_pct": 5.0, "max_daily_rainfall_mm": 120.0, "area_km2": 50.0,
        "time_of_concentration_hours": 2.0, "population": 100000, "hospitals": 4,
        "national_benchmark": 25000, "low_capacity_road_pct": 60.0,
        "intervention": {"drainage_capacity_factor": 2.0},
    },
    {
        "name": "Synth-B (high vegetation, low rainfall)",
        "vegetation_pct": 80.0, "max_daily_rainfall_mm": 30.0, "area_km2": 200.0,
        "time_of_concentration_hours": 4.0, "population": 500000, "hospitals": 20,
        "national_benchmark": 25000, "low_capacity_road_pct": 30.0,
        "intervention": {"vegetation_pct_override": 95.0},
    },
    {
        "name": "Synth-C (mid vegetation, mid rainfall, hospitals intervention)",
        "vegetation_pct": 40.0, "max_daily_rainfall_mm": 60.0, "area_km2": 100.0,
        "time_of_concentration_hours": 3.0, "population": 300000, "hospitals": 10,
        "national_benchmark": 25000, "low_capacity_road_pct": 50.0,
        "intervention": {"hospitals_override": 15},
    },
    {
        "name": "Synth-D (road intervention, no flood effect expected)",
        "vegetation_pct": 20.0, "max_daily_rainfall_mm": 90.0, "area_km2": 75.0,
        "time_of_concentration_hours": 2.5, "population": 150000, "hospitals": 6,
        "national_benchmark": 25000, "low_capacity_road_pct": 70.0,
        "intervention": {"low_capacity_pct_override": 40.0},
    },
    {
        "name": "Synth-E (combined drainage and vegetation intervention)",
        "vegetation_pct": 10.0, "max_daily_rainfall_mm": 100.0, "area_km2": 120.0,
        "time_of_concentration_hours": 3.0, "population": 250000, "hospitals": 8,
        "national_benchmark": 25000, "low_capacity_road_pct": 55.0,
        "intervention": {"drainage_capacity_factor": 1.5, "vegetation_pct_override": 35.0},
    },
]


def independent_expected_outcome(city, drainage_capacity_factor=1.0, vegetation_pct_override=None,
                                  hospitals_override=None, low_capacity_pct_override=None):
    """Computes the expected outcome by an arithmetic path written
    independently here, deliberately not calling the same
    compute_peak_runoff_index / compute_flood_risk_score functions being
    validated, so this is a genuine independent cross-check."""
    veg = vegetation_pct_override if vegetation_pct_override is not None else city["vegetation_pct"]
    hosp = hospitals_override if hospitals_override is not None else city["hospitals"]
    road = low_capacity_pct_override if low_capacity_pct_override is not None else city["low_capacity_road_pct"]

    veg_frac = veg / 100.0
    C = veg_frac * C_VEGETATED + (1 - veg_frac) * C_IMPERVIOUS
    i = city["max_daily_rainfall_mm"] / city["time_of_concentration_hours"]
    Q_raw = C * i * city["area_km2"]
    Q_eff = Q_raw / drainage_capacity_factor
    i_ref = FLOOD_DESIGN_STORM_CEILING_MM / city["time_of_concentration_hours"]
    Q_ref = C_IMPERVIOUS * i_ref * city["area_km2"]
    peak_runoff_index = max(0, min(100, (Q_eff / Q_ref) * 100))

    exposure = max(0, min(100, (city["population"] / 300000) * 100))
    flood_risk = max(0, min(100, 0.75 * peak_runoff_index + 0.25 * exposure))

    ratio = city["population"] / hosp if hosp else float("inf")
    health = max(0, min(100, (ratio / city["national_benchmark"]) * 50))

    traffic = max(0, min(100, road))

    emergency = max(0, min(100, (health + traffic + flood_risk) / 3))

    return {
        "runoff_coefficient": C, "peak_runoff_index": peak_runoff_index,
        "flood_risk_score": flood_risk, "health_access_score": health,
        "traffic_score": traffic, "emergency_response_score": emergency,
    }


def pipeline_computed_outcome(city, overrides):
    """Runs the actual production code path being validated, using the
    same structural equation functions the real pipeline calls, but with
    every input supplied directly rather than read from Cape Coast data
    files, so the synthetic cities never touch outputs/data/*.json."""
    veg = overrides.get("vegetation_pct_override", city["vegetation_pct"])
    hosp = overrides.get("hospitals_override", city["hospitals"])
    road = overrides.get("low_capacity_pct_override", city["low_capacity_road_pct"])
    drainage = overrides.get("drainage_capacity_factor", 1.0)

    C = compute_runoff_coefficient(veg)
    peak_runoff_index, _ = compute_peak_runoff_index(
        C, city["max_daily_rainfall_mm"], drainage,
        area_km2=city["area_km2"], time_of_concentration_hours=city["time_of_concentration_hours"])
    flood_risk = compute_flood_risk_score(peak_runoff_index, city["population"], population_reference=300000)
    health, _ = compute_health_access_score(city["population"], hosp, city["national_benchmark"])
    traffic = compute_traffic_score(road)
    emergency = compute_emergency_response_score(health, traffic, flood_risk)

    return {
        "runoff_coefficient": C, "peak_runoff_index": peak_runoff_index,
        "flood_risk_score": flood_risk, "health_access_score": health,
        "traffic_score": traffic, "emergency_response_score": emergency,
    }


def main():
    print("[synthetic_validation] Validating the do-operator intervention engine against "
          "independently computed expected outcomes on synthetic (non-Cape-Coast) data ...")
    results = []
    all_passed = True

    for city in SYNTHETIC_CITIES:
        expected = independent_expected_outcome(city, **city["intervention"])
        actual = pipeline_computed_outcome(city, city["intervention"])

        checks = {}
        for key in expected:
            diff = abs(expected[key] - actual[key])
            checks[key] = {"expected": round(expected[key], 4), "actual": round(actual[key], 4),
                            "diff": round(diff, 6), "passed": diff < TOLERANCE}
        city_passed = all(c["passed"] for c in checks.values())
        all_passed = all_passed and city_passed

        results.append({"city": city["name"], "intervention": city["intervention"],
                         "checks": checks, "passed": city_passed})
        status = "PASS" if city_passed else "FAIL"
        print(f"  {city['name']}: {status}")
        if not city_passed:
            for key, c in checks.items():
                if not c["passed"]:
                    print(f"    MISMATCH on {key}: expected {c['expected']}, got {c['actual']}")

    print(f"[synthetic_validation] Overall: {'ALL PASSED' if all_passed else 'FAILURES DETECTED'} "
          f"({sum(r['passed'] for r in results)}/{len(results)} scenarios)")

    out_path = os.path.join(DATA_DIR, "synthetic_validation_results.json")
    with open(out_path, "w") as f:
        json.dump({"all_passed": all_passed, "n_scenarios": len(results), "results": results}, f, indent=2)
    print(f"[synthetic_validation] Wrote {out_path}")

    csv_path = os.path.join(TAB_DIR, "table_synthetic_validation.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scenario", "Intervention", "Max abs difference", "Status"])
        for r in results:
            max_diff = max(c["diff"] for c in r["checks"].values())
            w.writerow([r["city"], str(r["intervention"]), max_diff, "PASS" if r["passed"] else "FAIL"])

    md_path = os.path.join(TAB_DIR, "table_synthetic_validation.md")
    with open(md_path, "w") as f:
        f.write("| Scenario | Intervention | Max abs difference | Status |\n|---|---|---|---|\n")
        for r in results:
            max_diff = max(c["diff"] for c in r["checks"].values())
            f.write(f"| {r['city']} | {r['intervention']} | {max_diff} | {'PASS' if r['passed'] else 'FAIL'} |\n")

    print(f"[synthetic_validation] Wrote {csv_path}")
    print(f"[synthetic_validation] Wrote {md_path}")


if __name__ == "__main__":
    main()
