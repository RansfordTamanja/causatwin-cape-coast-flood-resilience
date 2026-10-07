"""
dominance.py

Multi-objective Pareto dominance analysis over the seven interventions,
using four decision objectives, flood risk reduction, emergency response
improvement, health access improvement, and traffic improvement, plus
illustrative cost as a fifth objective to minimize. This is a genuine
multi-objective decision-support layer, distinct from and complementary
to the single-metric benefit-per-cost ranking in ranking.py.

DEFINITION: intervention A is dominated by intervention B if B achieves
an equal or greater improvement on every objective while costing no
more, and a strictly greater improvement on at least one objective. An
intervention with no other intervention dominating it is non-dominated,
meaning no other intervention is unambiguously at least as good on
every axis simultaneously; being non-dominated does not mean an
intervention is the best choice on any single objective, only that
choosing it cannot be strictly improved upon in every dimension by
switching to another single intervention.

Writes:
    outputs/data/dominance_results.json
    outputs/tables/table_dominance.{csv,md}
"""

import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

# Same illustrative relative costs used in ranking.py, imported directly
# so the two analyses cannot silently diverge.
from ranking import ILLUSTRATIVE_RELATIVE_COST


def dominates(a, b):
    """Returns True if intervention a dominates intervention b: equal or
    greater improvement on every objective, no higher cost, and
    strictly better on at least one dimension."""
    objectives_a = [a["flood_benefit"], a["emergency_benefit"], a["health_benefit"], a["traffic_benefit"]]
    objectives_b = [b["flood_benefit"], b["emergency_benefit"], b["health_benefit"], b["traffic_benefit"]]
    cost_ok = a["cost"] <= b["cost"]
    at_least_as_good = all(oa >= ob for oa, ob in zip(objectives_a, objectives_b))
    strictly_better = any(oa > ob for oa, ob in zip(objectives_a, objectives_b)) or a["cost"] < b["cost"]
    return cost_ok and at_least_as_good and strictly_better


def main():
    print("[dominance] Running multi-objective Pareto dominance analysis ...")
    interventions_path = os.path.join(DATA_DIR, "interventions_results.json")
    if not os.path.exists(interventions_path):
        print(f"[dominance] ERROR: {interventions_path} not found. Run intervention_engine.py first.")
        return

    with open(interventions_path) as f:
        results = json.load(f)
    baseline = results[0]

    candidates = []
    for r in results[1:]:
        if r["name"] not in ILLUSTRATIVE_RELATIVE_COST:
            continue
        candidates.append({
            "name": r["name"],
            "flood_benefit": round(baseline["flood_risk_score"] - r["flood_risk_score"], 1),
            "emergency_benefit": round(baseline["emergency_response_score"] - r["emergency_response_score"], 1),
            "health_benefit": round(baseline["health_access_score"] - r["health_access_score"], 1),
            "traffic_benefit": round(baseline["traffic_score"] - r["traffic_score"], 1),
            "cost": ILLUSTRATIVE_RELATIVE_COST[r["name"]],
        })

    for c in candidates:
        dominated_by = [other["name"] for other in candidates if other["name"] != c["name"] and dominates(other, c)]
        c["dominated"] = len(dominated_by) > 0
        c["dominated_by"] = dominated_by

    for c in candidates:
        status = "Dominated by " + "; ".join(c["dominated_by"]) if c["dominated"] else "Non-dominated"
        print(f"  {c['name']}: {status}")

    out_path = os.path.join(DATA_DIR, "dominance_results.json")
    with open(out_path, "w") as f:
        json.dump(candidates, f, indent=2)
    print(f"[dominance] Wrote {out_path}")

    csv_path = os.path.join(TAB_DIR, "table_dominance.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Intervention", "Flood benefit", "Emergency benefit", "Health benefit",
                     "Traffic benefit", "Illustrative cost", "Status"])
        for c in candidates:
            status = "Dominated" if c["dominated"] else "Non-dominated"
            w.writerow([c["name"], c["flood_benefit"], c["emergency_benefit"], c["health_benefit"],
                        c["traffic_benefit"], c["cost"], status])

    md_path = os.path.join(TAB_DIR, "table_dominance.md")
    with open(md_path, "w") as f:
        f.write("| Intervention | Flood benefit | Emergency benefit | Health benefit | Traffic benefit | "
                 "Illustrative cost | Status |\n|---|---|---|---|---|---|---|\n")
        for c in candidates:
            status = "Dominated" if c["dominated"] else "Non-dominated"
            f.write(f"| {c['name']} | {c['flood_benefit']} | {c['emergency_benefit']} | {c['health_benefit']} | "
                     f"{c['traffic_benefit']} | {c['cost']} | {status} |\n")

    print(f"[dominance] Wrote {csv_path}")
    print(f"[dominance] Wrote {md_path}")


if __name__ == "__main__":
    main()
