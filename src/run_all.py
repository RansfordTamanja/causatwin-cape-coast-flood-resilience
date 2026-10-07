"""
run_all.py

Runs the full CausaTwin pipeline in order:

    fetch_climate.py       -> outputs/data/climate_summary.csv [+ climate_daily.csv]
    parse_osm.py            -> outputs/data/osm_stats.json
    load_census.py            -> outputs/data/cape_coast_population.json
    national_benchmark.py       -> outputs/data/national_health_benchmark.json
    sentinel_fetch.py             -> outputs/data/sentinel_bands/*.jp2 (OPTIONAL)
    sentinel_ndvi.py                -> outputs/data/sentinel_vegetation.json (OPTIONAL)
    causal_graph.py                   -> outputs/data/causal_graph_structure.json
    intervention_engine.py              -> outputs/data/interventions_results.json,
                                            outputs/tables/table_interventions.{csv,md}
    uncertainty.py                        -> outputs/data/uncertainty_results.json,
                                              outputs/tables/table_uncertainty.{csv,md}
    ranking.py                              -> outputs/data/ranking_results.json,
                                                outputs/tables/table_ranking.{csv,md}
    evaluate.py                               -> outputs/data/evaluate_results.json
    plotting.py                                 -> outputs/figures/*.png
    make_tables.py                                -> outputs/tables/table_graph_nodes.{csv,md}

Same optional-step pattern as CityMind: sentinel_fetch.py and
sentinel_ndvi.py are skipped automatically, with a clear message, if
COPERNICUS_USERNAME/COPERNICUS_PASSWORD are not set or rasterio is not
installed. When skipped, the Flood component of the causal model falls
back to a proxy vegetation estimate (see structural_equations.py), not
the live NDVI reading.
"""

import subprocess
import sys
import os

SRC = os.path.dirname(os.path.abspath(__file__))


def _rasterio_available():
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def _copernicus_credentials_set():
    return bool(os.environ.get("COPERNICUS_USERNAME") and os.environ.get("COPERNICUS_PASSWORD"))


PIPELINE = [
    ("fetch_climate.py", None),
    ("parse_osm.py", None),
    ("load_census.py", None),
    ("national_benchmark.py", None),
    ("sentinel_fetch.py", lambda: None if _copernicus_credentials_set() else
        "COPERNICUS_USERNAME/COPERNICUS_PASSWORD not set; the causal model will use a fallback "
        "vegetation estimate instead of a live Sentinel NDVI reading"),
    ("sentinel_ndvi.py", lambda: None if _rasterio_available() else
        "'rasterio' not installed (pip install rasterio); skipping live NDVI computation"),
    ("causal_graph.py", None),
    ("intervention_engine.py", None),
    ("synthetic_validation.py", None),
    ("uncertainty.py", None),
    ("ranking.py", None),
    ("dominance.py", None),
    ("evaluate.py", None),
    ("sensitivity_assumptions.py", None),
    ("plotting.py", None),
    ("make_tables.py", None),
]


def main():
    for step, skip_check in PIPELINE:
        if skip_check is not None:
            reason = skip_check()
            if reason:
                print(f"\n=== Skipping {step} ({reason}) ===")
                continue

        print(f"\n=== Running {step} ===")
        result = subprocess.run([sys.executable, os.path.join(SRC, step)])
        if result.returncode != 0:
            is_optional = step in ("sentinel_fetch.py", "sentinel_ndvi.py")
            if is_optional:
                print(f"\n[run_all] {step} failed (code {result.returncode}); continuing, "
                      f"since this is an optional enhancement step, not a required one.")
                continue
            print(f"\n[run_all] {step} exited with an error (code {result.returncode}). Stopping.")
            sys.exit(result.returncode)

    print("\n[run_all] Pipeline complete. See outputs/figures, outputs/tables, and outputs/data.")


if __name__ == "__main__":
    main()
