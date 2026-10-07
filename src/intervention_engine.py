"""
intervention_engine.py

Implements the Counterfactual Urban Intervention Engine (CUIE): applies
Pearl-style do-operator interventions to the structural causal model
defined in causal_graph.py and structural_equations.py, and compares the
resulting counterfactual outcomes against the observed baseline.

A do-operator intervention do(X = x) sets a variable to a fixed value,
severing it from its normal causes, and propagates the consequences
forward through the graph. Here, every intervenable node
(drainage_capacity, vegetation_cover, hospitals, low_capacity_road_pct)
can be set directly; every downstream mediator and outcome is then
recomputed from that forced value using the same structural equations
that produced the baseline, so baseline and counterfactual are always
computed by the identical code path and differ only in the intervened
value.

HONESTY NOTE: these are interventions on a specified, not discovered,
causal model (see causal_graph.py). The magnitude of each intervention
(for example, "+20% drainage capacity") is a scenario choice, not a
claim about a specific, costed, funded infrastructure project. Where an
illustrative cost is attached to an intervention for ranking purposes in
ranking.py, that cost is explicitly labeled as illustrative, since no
real infrastructure cost data for Cape Coast was available for this
study.

Writes:
    outputs/data/interventions_results.json
    outputs/tables/table_interventions.{csv,md}
"""

import json
import os

from structural_equations import run_baseline_and_all_scores

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

OUTCOME_KEYS = ["flood_risk_score", "health_access_score", "traffic_score", "emergency_response_score"]

# Each intervention is defined as a do-operator assignment: which
# intervenable node is fixed, and to what value or delta. Magnitudes are
# illustrative scenario choices (documented above), not specific funded
# projects.
INTERVENTIONS = [
    {
        "name": "Baseline (observed)",
        "kind": "baseline",
        "overrides": {},
    },
    {
        "name": "do(drainage_capacity = 1.2)  [+20% drainage capacity]",
        "kind": "drainage",
        "overrides": {"drainage_capacity_factor": 1.2},
    },
    {
        "name": "do(drainage_capacity = 1.5)  [+50% drainage capacity]",
        "kind": "drainage",
        "overrides": {"drainage_capacity_factor": 1.5},
    },
    {
        "name": "do(vegetation += 15pp)  [vegetation restoration]",
        "kind": "vegetation",
        "overrides": {"vegetation_delta_pp": 15},
    },
    {
        "name": "do(hospitals += 3)  [add 3 hospitals]",
        "kind": "health",
        "overrides": {"hospitals_delta": 3},
    },
    {
        "name": "do(low_capacity_road_pct -= 15pp)  [arterial road upgrade]",
        "kind": "traffic",
        "overrides": {"low_capacity_delta_pp": -15},
    },
    {
        "name": "do(drainage_capacity = 1.5, vegetation += 15pp)  [combined flood package]",
        "kind": "combined",
        "overrides": {"drainage_capacity_factor": 1.5, "vegetation_delta_pp": 15},
    },
]


def apply_intervention(overrides, baseline_inputs):
    """Translates a set of do-operator overrides into the keyword
    arguments run_baseline_and_all_scores() expects, resolving deltas
    (e.g. vegetation_delta_pp) against the real observed baseline value
    rather than against an arbitrary reference point."""
    kwargs = {}
    if "drainage_capacity_factor" in overrides:
        kwargs["drainage_capacity_factor"] = overrides["drainage_capacity_factor"]
    else:
        kwargs["drainage_capacity_factor"] = 1.0

    if "vegetation_delta_pp" in overrides:
        kwargs["vegetation_pct_override"] = min(
            100.0, baseline_inputs["vegetation_pct"] + overrides["vegetation_delta_pp"])

    if "hospitals_delta" in overrides:
        kwargs["hospitals_override"] = baseline_inputs["hospitals"] + overrides["hospitals_delta"]

    if "low_capacity_delta_pp" in overrides:
        kwargs["low_capacity_pct_override"] = max(
            0.0, baseline_inputs["low_capacity_road_pct"] + overrides["low_capacity_delta_pp"])

    return kwargs


def main():
    print("[intervention_engine] Running the Counterfactual Urban Intervention Engine (CUIE) ...")
    baseline_result = run_baseline_and_all_scores()
    baseline_inputs = baseline_result["inputs"]

    all_results = []
    for intervention in INTERVENTIONS:
        kwargs = apply_intervention(intervention["overrides"], baseline_inputs)
        result = run_baseline_and_all_scores(**kwargs)
        record = {
            "name": intervention["name"],
            "kind": intervention["kind"],
            **{k: result[k] for k in OUTCOME_KEYS},
            "runoff_coefficient": result["runoff_coefficient"],
            "peak_runoff_raw_index": result["peak_runoff_raw_index"],
        }
        all_results.append(record)
        print(f"  {intervention['name']}")
        print(f"    Flood={result['flood_risk_score']} Health={result['health_access_score']} "
              f"Traffic={result['traffic_score']} Emergency={result['emergency_response_score']}")

    # Compute deltas relative to baseline for easy reading
    baseline_scores = {k: all_results[0][k] for k in OUTCOME_KEYS}
    for record in all_results[1:]:
        record["delta_vs_baseline"] = {k: round(record[k] - baseline_scores[k], 1) for k in OUTCOME_KEYS}
        # Counterfactual Effect Reduction (CER): percentage reduction in
        # flood risk relative to baseline, CER(X) = (Y_baseline -
        # Y_do(X=x)) / Y_baseline * 100. Only meaningful when the
        # baseline is nonzero, which it always is here.
        record["CER_flood_pct"] = round((baseline_scores["flood_risk_score"] - record["flood_risk_score"])
                                          / baseline_scores["flood_risk_score"] * 100, 1)
        record["CER_emergency_pct"] = round((baseline_scores["emergency_response_score"]
                                              - record["emergency_response_score"])
                                             / baseline_scores["emergency_response_score"] * 100, 1)

    out_path = os.path.join(DATA_DIR, "interventions_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[intervention_engine] Wrote {out_path}")

    csv_path = os.path.join(TAB_DIR, "table_interventions.csv")
    with open(csv_path, "w", newline="") as f:
        import csv as _csv
        w = _csv.writer(f)
        w.writerow(["Intervention", "Flood", "Health", "Traffic", "Emergency", "CER Flood %", "CER Emergency %"])
        for r in all_results:
            cer_f = r.get("CER_flood_pct", "-")
            cer_e = r.get("CER_emergency_pct", "-")
            w.writerow([r["name"], r["flood_risk_score"], r["health_access_score"],
                        r["traffic_score"], r["emergency_response_score"], cer_f, cer_e])

    md_path = os.path.join(TAB_DIR, "table_interventions.md")
    with open(md_path, "w") as f:
        f.write("| Intervention | Flood | Health | Traffic | Emergency | CER Flood % | CER Emergency % |\n|---|---|---|---|---|---|---|\n")
        for r in all_results:
            cer_f = r.get("CER_flood_pct", "-")
            cer_e = r.get("CER_emergency_pct", "-")
            f.write(f"| {r['name']} | {r['flood_risk_score']} | {r['health_access_score']} | "
                     f"{r['traffic_score']} | {r['emergency_response_score']} | {cer_f} | {cer_e} |\n")

    print(f"[intervention_engine] Wrote {csv_path}")
    print(f"[intervention_engine] Wrote {md_path}")


if __name__ == "__main__":
    main()
