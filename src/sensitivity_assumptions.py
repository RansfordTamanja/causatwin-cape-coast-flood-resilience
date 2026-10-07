"""
sensitivity_assumptions.py

Tests the sensitivity of CausaTwin's headline results to the two
structural assumptions most exposed to reviewer scrutiny: the assumed
drainage capacity baseline (1.0, representing current, unmeasured
conditions) and the assumed time of concentration (3 hours, used to
convert the observed maximum daily rainfall into a design storm
intensity). Both were flagged directly by external review as
assumptions a reviewer could reasonably attack, and this module answers
that concern with a computed result rather than a restated caveat.

FINDING 1, TIME OF CONCENTRATION: because the design storm intensity in
Equation 3 of the paper appears identically in both the numerator (via
the intervention's runoff calculation) and the denominator (via the
severe-storm reference used for normalization) of the peak runoff
index, the assumed time of concentration cancels exactly and
algebraically, the same mathematical mechanism already documented for
catchment area invariance in evaluate.py. This is verified numerically
below, not merely asserted, by recomputing the baseline peak runoff
index across a six-fold range of assumed time-of-concentration values
and confirming the result is identical.

FINDING 2, DRAINAGE BASELINE: unlike catchment area and time of
concentration, the assumed drainage capacity baseline does not cancel
exactly, because the flood risk score is a weighted combination of the
peak runoff index and a population exposure term that does not depend
on drainage capacity at all. This module quantifies the resulting
sensitivity directly: for the fifty percent drainage capacity
intervention, interpreted as a genuine relative increase from whatever
the true, unmeasured baseline capacity actually is, the resulting
Counterfactual Effect Reduction is computed across a plausible range of
assumed true baseline values, so a reader can see the real bound on
this sensitivity rather than only being told the baseline is assumed.

Writes:
    outputs/data/sensitivity_assumptions_results.json
    outputs/tables/table_toc_invariance.{csv,md}
    outputs/tables/table_drainage_baseline_sensitivity.{csv,md}
"""

import csv
import json
import os

from structural_equations import (
    compute_runoff_coefficient, compute_peak_runoff_index, compute_flood_risk_score,
    load_exogenous_inputs,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)

# Time of concentration values tested, spanning well beyond the
# plausible range for small-to-medium mixed urban catchments in
# published drainage design guidance.
TOC_TEST_VALUES_HOURS = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

# Candidate true baseline drainage capacity factors tested, representing
# roughly a plus-or-minus thirty percent uncertainty band around the
# assumed value of 1.0, since no measured baseline exists to bound this
# more precisely.
BASELINE_TEST_VALUES = [0.7, 0.85, 1.0, 1.15, 1.3]
INTERVENTION_MULTIPLIERS = {"drainage_capacity = +20%": 1.2, "drainage_capacity = +50%": 1.5}


def toc_invariance_check():
    inputs = load_exogenous_inputs()
    C = compute_runoff_coefficient(inputs["vegetation_pct"])
    rainfall = inputs["max_daily_rainfall_mm"]

    results = []
    for tc in TOC_TEST_VALUES_HOURS:
        idx, Q = compute_peak_runoff_index(C, rainfall, 1.0, time_of_concentration_hours=tc)
        results.append({"time_of_concentration_hours": tc, "peak_runoff_index": round(idx, 6),
                         "Q_effective": round(Q, 4)})

    all_identical = len(set(r["peak_runoff_index"] for r in results)) == 1
    return results, all_identical


def drainage_baseline_sensitivity():
    inputs = load_exogenous_inputs()
    C = compute_runoff_coefficient(inputs["vegetation_pct"])
    rainfall = inputs["max_daily_rainfall_mm"]
    population = inputs["population"]

    results = {}
    for label, multiplier in INTERVENTION_MULTIPLIERS.items():
        rows = []
        for true_baseline in BASELINE_TEST_VALUES:
            idx_base, _ = compute_peak_runoff_index(C, rainfall, true_baseline)
            flood_base = compute_flood_risk_score(idx_base, population)

            intervention_value = true_baseline * multiplier
            idx_int, _ = compute_peak_runoff_index(C, rainfall, intervention_value)
            flood_int = compute_flood_risk_score(idx_int, population)

            cer = (flood_base - flood_int) / flood_base * 100 if flood_base else 0.0
            rows.append({"assumed_true_baseline": true_baseline,
                         "baseline_flood_risk": round(flood_base, 2),
                         "intervention_flood_risk": round(flood_int, 2),
                         "CER_pct": round(cer, 2)})
        results[label] = rows
    return results


def main():
    print("[sensitivity_assumptions] Testing sensitivity to the two most reviewer-exposed "
          "structural assumptions: time of concentration and drainage capacity baseline ...")

    toc_results, toc_invariant = toc_invariance_check()
    print(f"[sensitivity_assumptions] Time of concentration swept from "
          f"{TOC_TEST_VALUES_HOURS[0]}h to {TOC_TEST_VALUES_HOURS[-1]}h:")
    for r in toc_results:
        print(f"  tc={r['time_of_concentration_hours']}h: peak_runoff_index={r['peak_runoff_index']}")
    print(f"[sensitivity_assumptions] Result identical across all tested values: {toc_invariant} "
          f"(this is an exact algebraic cancellation, not an empirical robustness finding)")

    baseline_results = drainage_baseline_sensitivity()
    print("[sensitivity_assumptions] Drainage capacity baseline swept from "
          f"{BASELINE_TEST_VALUES[0]} to {BASELINE_TEST_VALUES[-1]} "
          f"(assumed value is {1.0}):")
    for label, rows in baseline_results.items():
        cers = [r["CER_pct"] for r in rows]
        print(f"  {label}: CER ranges from {min(cers):.2f}% to {max(cers):.2f}% "
              f"across tested baselines")

    out_path = os.path.join(DATA_DIR, "sensitivity_assumptions_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "toc_invariance": {"results": toc_results, "exactly_invariant": toc_invariant},
            "drainage_baseline_sensitivity": baseline_results,
        }, f, indent=2)
    print(f"[sensitivity_assumptions] Wrote {out_path}")

    toc_csv = os.path.join(TAB_DIR, "table_toc_invariance.csv")
    with open(toc_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Time of concentration (h)", "Peak runoff index"])
        for r in toc_results:
            w.writerow([r["time_of_concentration_hours"], r["peak_runoff_index"]])
    toc_md = os.path.join(TAB_DIR, "table_toc_invariance.md")
    with open(toc_md, "w") as f:
        f.write("| Time of concentration (h) | Peak runoff index |\n|---|---|\n")
        for r in toc_results:
            f.write(f"| {r['time_of_concentration_hours']} | {r['peak_runoff_index']} |\n")

    base_csv = os.path.join(TAB_DIR, "table_drainage_baseline_sensitivity.csv")
    with open(base_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Intervention", "Assumed true baseline", "Baseline flood risk",
                     "Intervention flood risk", "CER %"])
        for label, rows in baseline_results.items():
            for r in rows:
                w.writerow([label, r["assumed_true_baseline"], r["baseline_flood_risk"],
                            r["intervention_flood_risk"], r["CER_pct"]])
    base_md = os.path.join(TAB_DIR, "table_drainage_baseline_sensitivity.md")
    with open(base_md, "w") as f:
        f.write("| Intervention | Assumed true baseline | Baseline flood risk | "
                 "Intervention flood risk | CER % |\n|---|---|---|---|---|\n")
        for label, rows in baseline_results.items():
            for r in rows:
                f.write(f"| {label} | {r['assumed_true_baseline']} | {r['baseline_flood_risk']} | "
                         f"{r['intervention_flood_risk']} | {r['CER_pct']} |\n")

    print(f"[sensitivity_assumptions] Wrote {toc_csv}, {toc_md}, {base_csv}, {base_md}")


if __name__ == "__main__":
    main()
