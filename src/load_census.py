"""
load_census.py

Loads the Ghana Statistical Service 2021 Population and Housing Census
subnational population statistics (admin level 2), and extracts the row
for the Cape Coast Metropolis, including the full 17-band age-sex
breakdown used for the population pyramid.

Source dataset: "Ghana - Subnational Population Statistics"
    https://data.humdata.org/dataset/cod-ps-gha
(a Humanitarian Data Exchange release of the official 2021 GSS census,
used here because GSS's own portal does not expose a bulk-download API.)

Input (default; override with --csv):
    inputs/gha_admpop_adm2_2021.csv

Writes:
    outputs/data/cape_coast_population.json
    outputs/data/national_population_ranked.json
"""

import argparse
import csv
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "inputs", "gha_admpop_adm2_2021.csv")
os.makedirs(DATA_DIR, exist_ok=True)

AGE_BANDS = ["00_04", "05_09", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39",
             "40_44", "45_49", "50_54", "55_59", "60_64", "65_69", "70_74", "75_79", "80PLUS"]
AGE_LABELS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
              "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"]


def write_national_ranking(rows, cape_coast_row):
    """Rank every district in the census file by total population, and
    record Cape Coast's rank among them -- gives the case study a sense
    of scale beyond a single-city snapshot."""
    ranked = sorted(
        ({"district": r["ADM2_NAME"].title(), "region": r["ADM1_NAME"].title(), "population": int(r["T_TL"])}
         for r in rows if r["T_TL"].strip().isdigit()),
        key=lambda d: -d["population"],
    )
    for i, d in enumerate(ranked, start=1):
        d["rank"] = i

    cape_coast_name = cape_coast_row["ADM2_NAME"].title()
    cape_coast_entry = next((d for d in ranked if d["district"] == cape_coast_name), None)

    result = {
        "total_districts": len(ranked),
        "top_15": ranked[:15],
        "cape_coast_rank": cape_coast_entry["rank"] if cape_coast_entry else None,
        "cape_coast_population": cape_coast_entry["population"] if cape_coast_entry else None,
    }
    out_path = os.path.join(DATA_DIR, "national_population_ranked.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[load_census] Cape Coast ranks #{result['cape_coast_rank']} of {result['total_districts']} "
          f"districts by population. Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract Cape Coast row from GSS 2021 census CSV.")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to gha_admpop_adm2_2021.csv")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"[load_census] ERROR: census CSV not found at {args.csv}")
        print("              Download from https://data.humdata.org/dataset/cod-ps-gha")
        print("              and place it at inputs/gha_admpop_adm2_2021.csv, or pass --csv <path>.")
        sys.exit(1)

    with open(args.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    matches = [r for r in rows if "CAPE COAST" in r["ADM2_NAME"].upper()]
    if not matches:
        print("[load_census] ERROR: no row matching 'CAPE COAST' found in the census CSV.")
        sys.exit(1)
    row = matches[0]

    female = [int(row[f"F_{b}"]) for b in AGE_BANDS]
    male = [int(row[f"M_{b}"]) for b in AGE_BANDS]
    total = int(row["T_TL"])

    under5 = female[0] + male[0]
    over65 = sum(female[13:]) + sum(male[13:])  # bands 65-69..80+ start at index 13

    result = {
        "district_name": row["ADM2_NAME"],
        "region_name": row["ADM1_NAME"],
        "total_population": total,
        "female_population": int(row["F_TL"]),
        "male_population": int(row["M_TL"]),
        "under5_population": under5,
        "under5_pct": round(under5 / total * 100, 1),
        "over65_population": over65,
        "over65_pct": round(over65 / total * 100, 1),
        "age_labels": AGE_LABELS,
        "female_by_age": female,
        "male_by_age": male,
        "source": "Ghana Statistical Service, 2021 Population and Housing Census "
                   "(via HDX cod-ps-gha subnational release)",
    }

    out_path = os.path.join(DATA_DIR, "cape_coast_population.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[load_census] Found {result['district_name']} ({result['region_name']}): "
          f"population {total:,}")
    print(f"[load_census] Wrote {out_path}")

    write_national_ranking(rows, row)


if __name__ == "__main__":
    main()
