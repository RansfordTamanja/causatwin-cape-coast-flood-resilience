# CausaTwin: A Causal Digital Twin for Counterfactual Urban Decision-Making

A reproducible Python pipeline supporting a proposed paper on causal,
counterfactual urban decision support for flood resilience in the Cape
Coast Metropolis, Ghana. Reuses the real, live data foundation built for
the earlier CityMind project (NASA POWER climate, OpenStreetMap
infrastructure, Ghana Statistical Service census, Copernicus Sentinel-2
satellite imagery) and adds a structural causal model with a
counterfactual intervention engine, Monte Carlo uncertainty
quantification, and an illustrative benefit-per-cost ranking.

## The central research question

Not "what is likely to happen," but **"what would happen if the city
implemented a specific intervention"**, for example: what happens to
flood risk if drainage capacity increases by 20 percent, or if
vegetation cover is restored by 15 percentage points.

## Critical methodological honesty note

**This is a specified causal model, not a discovered one.** The causal
graph structure (`causal_graph.py`) and the functional form of each
structural equation (`structural_equations.py`) are set from established
civil engineering practice, specifically the Rational Method for peak
stormwater runoff estimation (Q = C x i x A), documented in published
drainage design manuals, and from the CityMind scoring functions already
validated against real Cape Coast data. **No causal discovery algorithm
was run on observational data**, because no historical Cape Coast
intervention-outcome dataset exists that would make causal discovery
possible or honest to claim. The paper accompanying this code must state
this distinction explicitly, since it is the single most important
methodological fact a reviewer will check.

## What's in this package

```
src/                    All source code (see "Module guide" below)
inputs/                 Real data files (census CSV, OSM .pbf), reused from CityMind
outputs/figures/        4 figures: causal graph, intervention comparison, uncertainty, ranking
outputs/tables/         6 tables: graph nodes, interventions, uncertainty, ranking
outputs/data/           Intermediate data (all JSON, fully inspectable)
```

## Module guide

| File | Role |
|---|---|
| `fetch_climate.py`, `parse_osm.py`, `load_census.py`, `national_benchmark.py`, `sentinel_fetch.py`, `sentinel_ndvi.py` | Unchanged from CityMind — the same real, live data foundation. See the CityMind README for full documentation of each. |
| `causal_graph.py` | Defines the explicit, domain-specified structural causal model as a `networkx` DAG: 13 nodes (exogenous, intervenable, mediator, outcome), 13 edges. Verifies the graph is acyclic. Writes `causal_graph_structure.json`. |
| `structural_equations.py` | Implements the actual equation attached to every mediator and outcome node, most importantly the Rational Method runoff calculation. Reads every exogenous input from the real upstream data files — nothing is hardcoded except the drainage capacity baseline (1.0, i.e. "as observed"), which is explicitly flagged as assumed since no measured baseline exists. |
| `intervention_engine.py` | The Counterfactual Urban Intervention Engine (CUIE): applies `do()` operator interventions (fixing an intervenable node to a new value) and recomputes every downstream outcome through the identical code path used for the baseline. 7 interventions defined, including a combined package. Writes `interventions_results.json` and `table_interventions.{csv,md}`. |
| `uncertainty.py` | Monte Carlo uncertainty quantification (2,000 samples per intervention) over the *published* Rational Method coefficient ranges — parameter uncertainty over a specified model, not statistical uncertainty from real outcome data (none exists). Writes `uncertainty_results.json` and `table_uncertainty.{csv,md}`. |
| `ranking.py` | Ranks interventions by benefit-per-cost. **Costs are illustrative placeholders on an arbitrary relative scale, not real budget figures** — no real Cape Coast infrastructure cost data was available. This is stated in every output the script produces. Writes `ranking_results.json` and `table_ranking.{csv,md}`. |
| `evaluate.py` | Sensitivity and sanity checks: confirms the model's peak-runoff index is mathematically area-invariant by construction (not an empirical robustness finding — the module is explicit about the distinction), and confirms every drainage/vegetation intervention correctly reduces rather than increases flood risk. Reports the Decision Improvement dimension as **not evaluated**, since no historical outcome data exists to validate against. |
| `plotting.py` | Generates all 4 figures, including drawing the causal graph diagram directly from the same `networkx` object the intervention engine uses (not redrawn by hand, so the figure and the code can't silently drift apart). |
| `make_tables.py` | Generates the causal graph node/role/description table. |
| `run_all.py` | Runs the whole pipeline in order, with the same optional-step skip pattern as CityMind for Sentinel and rasterio. |

## Reproducing

```bash
pip install requests pandas matplotlib networkx osmium
# optional, for live Sentinel vegetation data:
pip install rasterio
cd src
python run_all.py
```

Both real input files (`gha_admpop_adm2_2021.csv`, `ghana-latest.osm.pbf`)
are included in `inputs/`. Sentinel imagery requires your own free
Copernicus account (same pattern as CityMind — see that project's README
for setup instructions); without it, the causal model falls back to a
proxy vegetation estimate, clearly labeled as such in every output.

## Headline results (this run, with live NASA POWER and Sentinel data)

**Baseline (real data):** Cape Coast flood risk score 65.2/100, computed
from a live 1,688.1 mm/year rainfall observation and a live Sentinel-2
NDVI reading showing 6.8 percent dense vegetation cover.

**Largest single intervention effect:** +50% drainage capacity reduces
the flood risk score from 65.2 to 49.2 (a 16-point reduction). The
combined drainage-and-vegetation package reduces it further to 45.3.

**Uncertainty:** Monte Carlo intervals (90%) over the published Rational
Method coefficient ranges do not overlap between the baseline and the
+50% drainage scenario (58.7-71.6 vs 44.8-53.5), indicating the
intervention effect is not simply an artifact of coefficient choice
within the cited literature ranges.

**Ranking (illustrative costs only):** vegetation restoration ranks
highest on benefit-per-illustrative-cost-unit (2.57), ahead of the more
expensive drainage capacity upgrades (1.07-1.34) — a genuinely
interesting finding, though contingent entirely on the illustrative cost
assumptions stated in `ranking.py` and not on real budget data.

## Honest limitations

- **The causal graph is specified, not discovered** — this is the
  central methodological claim of the whole project and must not be
  blurred in the paper.
- **Intervention magnitudes are scenario choices** (e.g., "+20%
  drainage capacity"), not specific costed, funded infrastructure
  projects.
- **Costs used for ranking are illustrative placeholders** on an
  arbitrary relative scale, not real Cape Coast budget or engineering
  cost data. Replacing them with real cost data is required before this
  ranking could inform an actual funding decision.
- **The catchment area sensitivity check in `evaluate.py` demonstrates a
  mathematical design property** (the index is invariant to the assumed
  area by construction), not genuine empirical robustness — this
  distinction is documented directly in the module's code and output.
- **Decision Improvement cannot be evaluated**, since no historical
  Cape Coast intervention-outcome dataset exists to validate the model's
  predictions against.
- **Drainage capacity has no measured baseline** for Cape Coast; the
  assumed baseline of 1.0 ("as currently observed, whatever that is")
  is a modeling convenience, not a claim about actual current drainage
  infrastructure capacity.
- Inherits every data-layer limitation already documented for CityMind:
  OpenStreetMap completeness, city-level (not sub-community) resolution,
  and partial Sentinel tile coverage of the bounding box when live
  satellite data is used.
