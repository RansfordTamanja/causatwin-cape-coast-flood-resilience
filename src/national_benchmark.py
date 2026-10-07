"""
national_benchmark.py

Replaces the previous Health Agent benchmark (a generic "10,000 residents
per facility" figure with no clear source) with a real, empirically
computed national reference: Ghana's own population-to-hospital ratio,
derived from the SAME two data sources used everywhere else in this
pipeline (OpenStreetMap, GSS census).

WHY THIS MATTERS: WHO explicitly states there is no global norm for
hospital-bed or hospital-facility density relative to population (see
https://www.who.int/data/gho/indicator-metadata-registry/imr-details/97,
"there is no global norm for the density of hospital beds in relation to
total population"). An external round-number benchmark like "10,000"
therefore cannot be honestly attributed to an authority. Using Ghana's
own national ratio instead is internally consistent: it is computed from
the exact same OSM completeness characteristics and the exact same
census release as the Cape Coast figures it is compared against, so the
comparison is apples-to-apples rather than borrowing a number from an
unrelated country or context.

Requires the FULL, unclipped Ghana OSM extract (not the Cape Coast
bounding box used by parse_osm.py) and the full census CSV.

Writes:
    outputs/data/national_health_benchmark.json
"""

import argparse
import csv
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
DEFAULT_PBF = os.path.join(os.path.dirname(__file__), "..", "inputs", "ghana-latest.osm.pbf")
DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "inputs", "gha_admpop_adm2_2021.csv")
os.makedirs(DATA_DIR, exist_ok=True)


def count_national_facilities(pbf_path):
    import osmium

    class NationalHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.hospitals = 0
            self.clinics = 0

        def node(self, n):
            amenity = n.tags.get("amenity")
            if amenity == "hospital":
                self.hospitals += 1
            elif amenity == "clinic":
                self.clinics += 1

        def way(self, w):
            amenity = w.tags.get("amenity")
            if amenity == "hospital":
                self.hospitals += 1
            elif amenity == "clinic":
                self.clinics += 1

    h = NationalHandler()
    h.apply_file(pbf_path)
    return h.hospitals, h.clinics


def sum_national_population(csv_path):
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return sum(int(r["T_TL"]) for r in rows if r["T_TL"].strip().isdigit()), len(rows)


def main():
    parser = argparse.ArgumentParser(description="Compute Ghana's national OSM-derived health facility benchmark.")
    parser.add_argument("--pbf", default=DEFAULT_PBF, help="Path to the FULL (unclipped) Ghana .osm.pbf extract")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to gha_admpop_adm2_2021.csv")
    args = parser.parse_args()

    if not os.path.exists(args.pbf):
        print(f"[national_benchmark] ERROR: full Ghana PBF not found at {args.pbf}")
        print("                      This must be the UNCLIPPED national file, not a bounding-box subset.")
        sys.exit(1)
    if not os.path.exists(args.csv):
        print(f"[national_benchmark] ERROR: census CSV not found at {args.csv}")
        sys.exit(1)

    try:
        import osmium  # noqa: F401
    except ImportError:
        print("[national_benchmark] ERROR: 'osmium' not installed. Run: pip install osmium")
        sys.exit(1)

    print(f"[national_benchmark] Parsing full Ghana OSM extract for national facility counts "
          f"(this covers the whole country, so it takes longer than parse_osm.py) ...")
    hospitals, clinics = count_national_facilities(args.pbf)
    population, n_districts = sum_national_population(args.csv)

    pop_per_hospital = population / hospitals if hospitals else float("inf")
    pop_per_health_facility = population / (hospitals + clinics) if (hospitals + clinics) else float("inf")

    result = {
        "national_population": population,
        "national_districts": n_districts,
        "national_hospitals_osm": hospitals,
        "national_clinics_osm": clinics,
        "national_population_per_hospital": round(pop_per_hospital),
        "national_population_per_health_facility": round(pop_per_health_facility),
        "source": (
            "Computed from the same OpenStreetMap Ghana extract and GSS 2021 census "
            "used throughout this pipeline, not an external authority (WHO explicitly "
            "states no global norm exists for hospital-to-population density)."
        ),
    }

    out_path = os.path.join(DATA_DIR, "national_health_benchmark.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[national_benchmark] National population: {population:,}")
    print(f"[national_benchmark] National hospitals (OSM): {hospitals}")
    print(f"[national_benchmark] National population per hospital: {pop_per_hospital:,.0f}")
    print(f"[national_benchmark] Wrote {out_path}")


if __name__ == "__main__":
    main()
