"""
uncertainty.py

Quantifies uncertainty in the counterfactual outcomes computed by
intervention_engine.py through Monte Carlo sampling over the published
ranges of the Rational Method runoff coefficients (C_IMPERVIOUS,
C_VEGETATED), rather than reporting the midpoint-derived scores as if
they were exact.

HONESTY NOTE ON WHAT KIND OF UNCERTAINTY THIS IS: this is parameter
uncertainty over a specified structural model, propagated through Monte
Carlo sampling of the coefficient ranges published in drainage design
literature. It is not statistical uncertainty estimated from historical
Cape Coast outcome data, since no such dataset exists. The resulting
confidence intervals describe how sensitive the model's own output is to
where within the published coefficient range the true local value falls,
not a calibrated probability that the model itself is correct.

Writes:
    outputs/data/uncertainty_results.json
    outputs/tables/table_uncertainty.{csv,md}
"""

import json
import os
import random

from structural_equations import (
    load_exogenous_inputs, compute_runoff_coefficient, compute_peak_runoff_index,
    compute_flood_risk_score, compute_health_access_score, compute_traffic_score,
    compute_emergency_response_score, C_IMPERVIOUS, C_VEGETATED,
)
from intervention_engine import INTERVENTIONS, apply_intervention

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

# Published ranges (see causal_graph.py docstring for sources)
C_IMPERVIOUS_RANGE = (0.70, 0.95)
C_VEGETATED_RANGE = (0.05, 0.35)

N_SAMPLES = 2000


def sample_flood_score(inputs, drainage_capacity_factor, vegetation_pct, population, seed_offset=0):
    """Draws one Monte Carlo sample of the flood risk score by sampling
    both runoff coefficients uniformly from their published ranges."""
    rng = random.Random(seed_offset)
    c_imp = rng.uniform(*C_IMPERVIOUS_RANGE)
    c_veg = rng.uniform(*C_VEGETATED_RANGE)
    veg_frac = vegetation_pct / 100
    C = veg_frac * c_veg + (1 - veg_frac) * c_imp
    peak_runoff_index, _ = compute_peak_runoff_index(C, inputs["max_daily_rainfall_mm"], drainage_capacity_factor)
    return compute_flood_risk_score(peak_runoff_index, population)


def monte_carlo_intervention(intervention, baseline_inputs, n_samples=N_SAMPLES):
    kwargs = apply_intervention(intervention["overrides"], baseline_inputs)
    drainage = kwargs.get("drainage_capacity_factor", 1.0)
    vegetation_pct = kwargs.get("vegetation_pct_override", baseline_inputs["vegetation_pct"])
    population = baseline_inputs["population"]

    samples = [
        sample_flood_score(baseline_inputs, drainage, vegetation_pct, population, seed_offset=i)
        for i in range(n_samples)
    ]
    samples.sort()
    n = len(samples)
    return {
        "mean": round(sum(samples) / n, 1),
        "p5": round(samples[int(0.05 * n)], 1),
        "p50": round(samples[int(0.50 * n)], 1),
        "p95": round(samples[int(0.95 * n)], 1),
        "n_samples": n,
    }


def main():
    print(f"[uncertainty] Running Monte Carlo uncertainty quantification "
          f"({N_SAMPLES} samples per intervention, over published Rational Method "
          f"coefficient ranges) ...")
    baseline_inputs = load_exogenous_inputs()

    results = []
    for intervention in INTERVENTIONS:
        stats = monte_carlo_intervention(intervention, baseline_inputs)
        results.append({"name": intervention["name"], "kind": intervention["kind"], **stats})
        print(f"  {intervention['name']}: flood risk mean={stats['mean']} "
              f"[90% interval {stats['p5']}-{stats['p95']}]")

    out_path = os.path.join(DATA_DIR, "uncertainty_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[uncertainty] Wrote {out_path}")

    csv_path = os.path.join(TAB_DIR, "table_uncertainty.csv")
    with open(csv_path, "w", newline="") as f:
        import csv as _csv
        w = _csv.writer(f)
        w.writerow(["Intervention", "Mean flood risk", "P5", "P50", "P95"])
        for r in results:
            w.writerow([r["name"], r["mean"], r["p5"], r["p50"], r["p95"]])

    md_path = os.path.join(TAB_DIR, "table_uncertainty.md")
    with open(md_path, "w") as f:
        f.write("| Intervention | Mean flood risk | P5 | P50 | P95 |\n|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['name']} | {r['mean']} | {r['p5']} | {r['p50']} | {r['p95']} |\n")

    print(f"[uncertainty] Wrote {csv_path}")
    print(f"[uncertainty] Wrote {md_path}")


if __name__ == "__main__":
    main()
