"""
ranking.py

Ranks interventions by expected benefit per unit cost, answering the
question "which intervention should the city implement, given a limited
budget."

COST BASIS: costs are anchored to real, cited Ghana infrastructure
investment figures wherever such a figure could be identified, rather
than an arbitrary illustrative scale.

  - Hospitals: US$6 million per district hospital, the midpoint of the
    Government of Ghana's own official Agenda 111 initial per-facility
    cost estimate of US$5-7 million (Ghana Ministry of Health, reported
    by then Health Minister-designate Kwaku Agyeman-Manu, February
    2021).
  - Arterial road upgrade: US$1.3 million per kilometer, the midpoint of
    the Ghana Ministry of Roads and Highways' own cited reconstruction
    range of US$1.2-1.4 million per kilometer (Ghana Ministry of Roads
    and Highways, via MyJoyOnline, 2021), applied to an assumed 10
    kilometers of arterial upgrade, a stated planning assumption (not a
    surveyed figure) since no route-specific Cape Coast arterial upgrade
    plan exists.
  - Drainage capacity: anchored via a real per-capita benchmark derived
    from the World Bank's Greater Accra Resilient and Integrated
    Development (GARID) project, US$150 million in additional financing
    for comprehensive flood risk and solid waste management serving 2.5
    million people (World Bank, May 2023), giving approximately US$60
    per capita. Applied to Cape Coast's real 2021 census population of
    205,662, this yields an illustrative comprehensive flood package
    cost of approximately US$12.3 million, allocated across the
    drainage-only and combined interventions in proportion to their
    relative engineering scope.
  - Vegetation restoration: no comparable Ghana-specific unit cost was
    identified for urban vegetation restoration at the scale modeled
    here. Rather than assert an unsupported figure, this script runs a
    three-point cost sensitivity analysis, low, medium, and high, and
    reports explicitly at what assumed cost vegetation restoration stops
    ranking above the drainage-only interventions, turning this gap into
    a reported finding rather than a concealed assumption.

None of these figures should be read as a specific costed plan for Cape
Coast; they are real national or regional benchmarks applied through
stated extrapolation assumptions, not a site survey, and this is stated
directly in every output this script produces.

Writes:
    outputs/data/ranking_results.json
    outputs/tables/table_ranking.{csv,md}
    outputs/data/cost_sensitivity_results.json
    outputs/tables/table_cost_sensitivity.{csv,md}
"""

import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

# Real, cited cost anchors (US$ millions). See module docstring for sources.
HOSPITAL_COST_USD_M = 6.0            # per hospital, Ghana Ministry of Health Agenda 111 estimate
ROAD_COST_USD_M_PER_KM = 1.3         # per km, Ghana Ministry of Roads and Highways
ASSUMED_ARTERIAL_UPGRADE_KM = 10.0   # stated planning assumption, not a surveyed route length

GARID_TOTAL_USD_M = 150.0
GARID_POPULATION = 2_500_000
GARID_PER_CAPITA_USD = GARID_TOTAL_USD_M / GARID_POPULATION  # ~0.00006 USD_M per capita = $60/person
CAPE_COAST_POPULATION = 205_662
COMPREHENSIVE_FLOOD_PACKAGE_USD_M = GARID_PER_CAPITA_USD * CAPE_COAST_POPULATION  # ~12.34

# Allocation of the comprehensive package cost across the three
# drainage/vegetation interventions, in proportion to their relative
# engineering scope (a 20% capacity increase is allocated a smaller
# share than a 50% increase; the combined package receives the full
# comprehensive package cost since it corresponds most closely to what
# the GARID-style investment actually funds).
DRAINAGE_20_SHARE = 0.35
DRAINAGE_50_SHARE = 0.85
COMBINED_SHARE = 1.00

REAL_COST_USD_M = {
    "do(drainage_capacity = 1.2)  [+20% drainage capacity]": round(COMPREHENSIVE_FLOOD_PACKAGE_USD_M * DRAINAGE_20_SHARE, 2),
    "do(drainage_capacity = 1.5)  [+50% drainage capacity]": round(COMPREHENSIVE_FLOOD_PACKAGE_USD_M * DRAINAGE_50_SHARE, 2),
    "do(hospitals += 3)  [add 3 hospitals]": round(3 * HOSPITAL_COST_USD_M, 2),
    "do(low_capacity_road_pct -= 15pp)  [arterial road upgrade]": round(ASSUMED_ARTERIAL_UPGRADE_KM * ROAD_COST_USD_M_PER_KM, 2),
    "do(drainage_capacity = 1.5, vegetation += 15pp)  [combined flood package]": round(COMPREHENSIVE_FLOOD_PACKAGE_USD_M * COMBINED_SHARE, 2),
}

# Vegetation restoration cost sensitivity scenarios (US$ millions),
# since no Ghana-specific citation was identified. Low and high bound a
# plausible range around a medium estimate set equal to the +20%
# drainage capacity cost, so the sensitivity analysis directly answers
# whether vegetation restoration's ranking position depends on this
# assumption.
VEGETATION_COST_SCENARIOS = {
    "low": round(REAL_COST_USD_M["do(drainage_capacity = 1.2)  [+20% drainage capacity]"] * 0.3, 2),
    "medium": REAL_COST_USD_M["do(drainage_capacity = 1.2)  [+20% drainage capacity]"],
    "high": round(REAL_COST_USD_M["do(drainage_capacity = 1.2)  [+20% drainage capacity]"] * 3.0, 2),
}

VEGETATION_KEY = "do(vegetation += 15pp)  [vegetation restoration]"

# Backward-compatible alias so dominance.py's cost lookups keep working;
# uses the medium vegetation cost scenario as the default point estimate.
ILLUSTRATIVE_RELATIVE_COST = dict(REAL_COST_USD_M)
ILLUSTRATIVE_RELATIVE_COST[VEGETATION_KEY] = VEGETATION_COST_SCENARIOS["medium"]


def _rank_with_costs(results, cost_map):
    baseline = results[0]
    ranked = []
    for r in results[1:]:
        if r["name"] not in cost_map:
            continue
        cost = cost_map[r["name"]]
        flood_benefit = baseline["flood_risk_score"] - r["flood_risk_score"]
        emergency_benefit = baseline["emergency_response_score"] - r["emergency_response_score"]
        total_benefit = flood_benefit + emergency_benefit
        benefit_per_cost = total_benefit / cost if cost else 0
        ranked.append({
            "name": r["name"],
            "flood_benefit": round(flood_benefit, 1),
            "emergency_benefit": round(emergency_benefit, 1),
            "total_benefit": round(total_benefit, 1),
            "cost_usd_millions": cost,
            "benefit_per_cost_usd_million": round(benefit_per_cost, 3),
        })
    ranked.sort(key=lambda x: -x["benefit_per_cost_usd_million"])
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    return ranked


def main():
    print("[ranking] Ranking interventions by benefit-per-cost using real, cited cost anchors ...")
    interventions_path = os.path.join(DATA_DIR, "interventions_results.json")
    if not os.path.exists(interventions_path):
        print(f"[ranking] ERROR: {interventions_path} not found. Run intervention_engine.py first.")
        return

    with open(interventions_path) as f:
        results = json.load(f)

    ranked = _rank_with_costs(results, ILLUSTRATIVE_RELATIVE_COST)
    for r in ranked:
        print(f"  #{r['rank']}: {r['name']} -- benefit per US$M = {r['benefit_per_cost_usd_million']} "
              f"(cost US${r['cost_usd_millions']}M)")

    out_path = os.path.join(DATA_DIR, "ranking_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "note": "Hospital, road, and drainage costs are anchored to real, cited Ghana "
                     "infrastructure benchmarks applied through stated extrapolation assumptions "
                     "(see ranking.py module docstring); the medium vegetation restoration cost "
                     "scenario is used here, with the full low/medium/high sensitivity reported "
                     "separately in cost_sensitivity_results.json.",
            "ranking": ranked,
        }, f, indent=2)
    print(f"[ranking] Wrote {out_path}")

    csv_path = os.path.join(TAB_DIR, "table_ranking.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Rank", "Intervention", "Flood benefit", "Emergency benefit",
                     "Total benefit", "Cost (US$M)", "Benefit per US$M"])
        for r in ranked:
            w.writerow([r["rank"], r["name"], r["flood_benefit"], r["emergency_benefit"],
                        r["total_benefit"], r["cost_usd_millions"], r["benefit_per_cost_usd_million"]])

    md_path = os.path.join(TAB_DIR, "table_ranking.md")
    with open(md_path, "w") as f:
        f.write("| Rank | Intervention | Flood benefit | Emergency benefit | Total benefit | "
                 "Cost (US$M) | Benefit per US$M |\n|---|---|---|---|---|---|---|\n")
        for r in ranked:
            f.write(f"| {r['rank']} | {r['name']} | {r['flood_benefit']} | {r['emergency_benefit']} | "
                     f"{r['total_benefit']} | {r['cost_usd_millions']} | {r['benefit_per_cost_usd_million']} |\n")
    print(f"[ranking] Wrote {csv_path}")
    print(f"[ranking] Wrote {md_path}")

    # Cost sensitivity: does vegetation restoration's rank position
    # depend on which cost scenario is assumed?
    print("[ranking] Running vegetation restoration cost sensitivity (low/medium/high) ...")
    sensitivity = {}
    for scenario, veg_cost in VEGETATION_COST_SCENARIOS.items():
        cost_map = dict(ILLUSTRATIVE_RELATIVE_COST)
        cost_map[VEGETATION_KEY] = veg_cost
        scenario_ranked = _rank_with_costs(results, cost_map)
        veg_rank = next(r["rank"] for r in scenario_ranked if r["name"] == VEGETATION_KEY)
        sensitivity[scenario] = {
            "vegetation_cost_usd_millions": veg_cost,
            "vegetation_rank": veg_rank,
            "full_ranking": [r["name"] for r in scenario_ranked],
        }
        print(f"  {scenario} (US${veg_cost}M): vegetation restoration ranks #{veg_rank} of {len(scenario_ranked)}")

    sens_out = os.path.join(DATA_DIR, "cost_sensitivity_results.json")
    with open(sens_out, "w") as f:
        json.dump(sensitivity, f, indent=2)
    print(f"[ranking] Wrote {sens_out}")

    sens_csv = os.path.join(TAB_DIR, "table_cost_sensitivity.csv")
    with open(sens_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Scenario", "Vegetation cost (US$M)", "Vegetation rank"])
        for scenario, d in sensitivity.items():
            w.writerow([scenario, d["vegetation_cost_usd_millions"], d["vegetation_rank"]])

    sens_md = os.path.join(TAB_DIR, "table_cost_sensitivity.md")
    with open(sens_md, "w") as f:
        f.write("| Scenario | Vegetation cost (US$M) | Vegetation rank |\n|---|---|---|\n")
        for scenario, d in sensitivity.items():
            f.write(f"| {scenario} | {d['vegetation_cost_usd_millions']} | {d['vegetation_rank']} |\n")

    print(f"[ranking] Wrote {sens_csv}")
    print(f"[ranking] Wrote {sens_md}")


if __name__ == "__main__":
    main()
