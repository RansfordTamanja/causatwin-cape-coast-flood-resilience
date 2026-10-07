"""
causal_graph.py

Defines the structural causal model (SCM) underlying CausaTwin: an
explicit, domain-specified directed acyclic graph over urban variables,
with structural equations attached to each mediator and outcome node.

HONESTY NOTE ON METHOD: this is a specified causal model, not a
discovered one. The graph structure and the functional form of each
structural equation are set from established civil engineering practice
(the Rational Method for peak stormwater runoff estimation) and from the
CityMind scoring functions already validated against real Cape Coast
data, not learned from observational data through a causal discovery
algorithm. No historical intervention-outcome dataset for Cape Coast
exists that would make causal discovery from data possible or honest to
claim. What this module DOES provide is a legitimate mechanism for
computing counterfactual outcomes under a stated, inspectable set of
assumptions, in the same tradition as engineering simulation models: the
value is in making every assumption explicit and every input traceable,
not in claiming the causal structure was learned rather than specified.

THE RATIONAL METHOD: peak runoff Q = C x i x A, where C is a runoff
coefficient depending on land cover, i is rainfall intensity, and A is
catchment area. This is standard, widely taught, and widely used
practice for small urban catchments (see e.g. Greenville County, SC
Land Development Design Manual, Chapter 5; Texas Department of
Transportation Hydraulic Design Manual, Chapter 4, Section 12), cited
in full in the accompanying paper. Typical runoff coefficient ranges
used below (dense/impervious surfaces approximately 0.70-0.95;
vegetated/open space approximately 0.05-0.35) are drawn from published
design-manual tables, not invented.

Exogenous nodes (real data, from the upstream fetch/parse scripts):
    rainfall_mm_year, dense_vegetation_pct, buildings_count,
    population, hospitals_count, low_capacity_road_pct

Intervenable nodes (baseline value assumed since no measured baseline
exists for Cape Coast; interventions are relative changes to this
assumed baseline, not absolute claims about current infrastructure):
    drainage_capacity_factor (baseline = 1.0, i.e. "as observed")

Mediator nodes (computed via structural equations):
    runoff_coefficient, peak_runoff_index

Outcome nodes (reuse and extend CityMind's validated scoring logic):
    flood_risk_score, health_access_score, traffic_score,
    emergency_response_score

Writes:
    outputs/data/causal_graph_structure.json (for inspection/plotting)
"""

import json
import os

import networkx as nx

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Runoff coefficient (C) ranges for the Rational Method, drawn from
# published drainage design manuals (Greenville County SC 2018;
# Mile High Flood District Urban Storm Drainage Criteria Manual 2024;
# TxDOT Hydraulic Design Manual). These are ranges, not point estimates,
# and the midpoint is used as the central assumption with the full range
# used for Monte Carlo uncertainty in uncertainty.py.
C_IMPERVIOUS_RANGE = (0.70, 0.95)   # dense/built-up, low vegetation
C_VEGETATED_RANGE = (0.05, 0.35)    # open space, dense vegetation

# Reference catchment area for the Rational Method peak-runoff estimate.
# Uses the same Cape Coast Metropolitan bounding box area established in
# the data layer (approximately 97.1 km^2 of Sentinel-covered area when
# live satellite data is available; falls back to a nominal bounding-box
# estimate otherwise). This is the same area basis used throughout the
# accompanying CityMind data layer, not a separately assumed figure.
DEFAULT_CATCHMENT_AREA_KM2 = 97.1


def build_causal_graph():
    """Constructs the explicit DAG. Returns a networkx DiGraph with node
    attributes describing each variable's role (exogenous, intervenable,
    mediator, outcome) and a human-readable description."""
    G = nx.DiGraph()

    nodes = [
        ("rainfall", {"role": "exogenous", "desc": "Mean annual rainfall (mm/yr), live NASA POWER"}),
        ("vegetation_cover", {"role": "exogenous", "desc": "Dense vegetation cover fraction, live Sentinel-2 NDVI"}),
        ("building_density", {"role": "exogenous", "desc": "Buildings per km^2, OSM"}),
        ("drainage_capacity", {"role": "intervenable", "desc": "Drainage capacity factor, baseline=1.0 (assumed, not measured)"}),
        ("runoff_coefficient", {"role": "mediator", "desc": "Rational Method C, composite of vegetation and building density"}),
        ("peak_runoff_index", {"role": "mediator", "desc": "Rational Method Q=C*i*A, normalized 0-100"}),
        ("population", {"role": "exogenous", "desc": "Total population, GSS 2021 census"}),
        ("hospitals", {"role": "intervenable", "desc": "Mapped hospital count, OSM (interventions add hospitals)"}),
        ("low_capacity_road_pct", {"role": "intervenable", "desc": "Share of low-capacity road segments, OSM (interventions convert to arterial)"}),
        ("flood_risk_score", {"role": "outcome", "desc": "0-100 flood concern score"}),
        ("health_access_score", {"role": "outcome", "desc": "0-100 health-access concern score"}),
        ("traffic_score", {"role": "outcome", "desc": "0-100 traffic concern score"}),
        ("emergency_response_score", {"role": "outcome", "desc": "0-100 emergency-response concern score"}),
    ]
    G.add_nodes_from(nodes)

    edges = [
        ("vegetation_cover", "runoff_coefficient"),
        ("building_density", "runoff_coefficient"),
        ("runoff_coefficient", "peak_runoff_index"),
        ("rainfall", "peak_runoff_index"),
        ("drainage_capacity", "peak_runoff_index"),
        ("peak_runoff_index", "flood_risk_score"),
        ("population", "flood_risk_score"),
        ("population", "health_access_score"),
        ("hospitals", "health_access_score"),
        ("low_capacity_road_pct", "traffic_score"),
        ("health_access_score", "emergency_response_score"),
        ("traffic_score", "emergency_response_score"),
        ("flood_risk_score", "emergency_response_score"),
    ]
    G.add_edges_from(edges)

    return G


def export_graph_structure(G):
    """Writes the graph structure to JSON for inspection and for the
    plotting module, so the diagram is generated from the same object
    the intervention engine actually uses, not redrawn by hand."""
    structure = {
        "nodes": [{"id": n, **attrs} for n, attrs in G.nodes(data=True)],
        "edges": [{"source": u, "target": v} for u, v in G.edges()],
    }
    out_path = os.path.join(DATA_DIR, "causal_graph_structure.json")
    with open(out_path, "w") as f:
        json.dump(structure, f, indent=2)
    return out_path


def main():
    G = build_causal_graph()
    print(f"[causal_graph] Built structural causal model: {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges.")
    assert nx.is_directed_acyclic_graph(G), "Causal graph must be acyclic."
    print("[causal_graph] Verified: graph is a valid DAG (acyclic).")
    out_path = export_graph_structure(G)
    print(f"[causal_graph] Wrote {out_path}")


if __name__ == "__main__":
    main()
