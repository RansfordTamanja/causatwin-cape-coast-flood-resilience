"""
plotting.py

Generates all figures for the CausaTwin paper: the causal graph diagram
itself (drawn from the actual graph object in causal_graph.py, not
redrawn by hand), the baseline-versus-counterfactual comparison for each
intervention, the Monte Carlo uncertainty bands, and the benefit-per-cost
ranking chart.
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from causal_graph import build_causal_graph

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
FIG_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

COLOR_BY_ROLE = {
    "exogenous": "#2a9d8f",
    "intervenable": "#e9c46a",
    "mediator": "#4a90d9",
    "outcome": "#e76f51",
}


def fig1_causal_graph():
    G = build_causal_graph()

    # Layered layout following topological generations, which reads far
    # more clearly for a DAG than a force-directed layout: exogenous and
    # intervenable inputs on the left, mediators in the middle, outcomes
    # on the right, with vertical position breaking ties within a layer.
    generations = list(nx.topological_generations(G))
    pos = {}
    for x, layer in enumerate(generations):
        n = len(layer)
        for i, node in enumerate(layer):
            y = (i - (n - 1) / 2)
            pos[node] = (x * 2.4, y * 1.9)

    fig, ax = plt.subplots(figsize=(13, 8.5))
    for role, color in COLOR_BY_ROLE.items():
        nodes = [n for n, d in G.nodes(data=True) if d["role"] == role]
        nx.draw_networkx_nodes(G, pos, nodelist=nodes, node_color=color, node_size=3200,
                                ax=ax, edgecolors="black", linewidths=1)
    nx.draw_networkx_edges(G, pos, ax=ax, arrowstyle="-|>", arrowsize=20, width=1.3,
                            connectionstyle="arc3,rad=0.08", arrows=True, node_size=3200,
                            min_source_margin=15, min_target_margin=15)
    labels = {n: n.replace("_", "\n") for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7.5, ax=ax)

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=14,
                           markeredgecolor="black", label=role.capitalize())
               for role, c in COLOR_BY_ROLE.items()]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=4,
              fontsize=10, frameon=True)
    ax.axis("off")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig1_causal_graph.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig2_intervention_comparison():
    path = os.path.join(DATA_DIR, "interventions_results.json")
    if not os.path.exists(path):
        print(f"  [fig2] skipped: {path} not found. Run intervention_engine.py first.")
        return
    with open(path) as f:
        results = json.load(f)

    names = [r["name"].split("[")[0].strip() for r in results]
    flood = [r["flood_risk_score"] for r in results]
    emergency = [r["emergency_response_score"] for r in results]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = range(len(names))
    width = 0.35
    ax.bar([i - width / 2 for i in x], flood, width, label="Flood risk score", color="#e76f51")
    ax.bar([i + width / 2 for i in x], emergency, width, label="Emergency response score", color="#4a90d9")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Score (0-100)")
    ax.legend()
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig2_intervention_comparison.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig3_uncertainty_bands():
    path = os.path.join(DATA_DIR, "uncertainty_results.json")
    if not os.path.exists(path):
        print(f"  [fig3] skipped: {path} not found. Run uncertainty.py first.")
        return
    with open(path) as f:
        results = json.load(f)

    names = [r["name"].split("[")[0].strip() for r in results]
    means = [r["mean"] for r in results]
    lower = [r["mean"] - r["p5"] for r in results]
    upper = [r["p95"] - r["mean"] for r in results]

    fig, ax = plt.subplots(figsize=(9, 6))
    y = range(len(names))
    ax.errorbar(means, y, xerr=[lower, upper], fmt="o", color="#e76f51", ecolor="grey",
                elinewidth=2, capsize=4, markersize=8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Flood risk score (0-100), with 5th-95th percentile uncertainty interval")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig3_uncertainty.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig4_ranking():
    path = os.path.join(DATA_DIR, "ranking_results.json")
    if not os.path.exists(path):
        print(f"  [fig4] skipped: {path} not found. Run ranking.py first.")
        return
    with open(path) as f:
        data = json.load(f)
    ranked = data["ranking"]

    names = [r["name"].split("[")[0].strip() for r in ranked]
    values = [r["benefit_per_cost_usd_million"] for r in ranked]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.barh(names, values, color="#2a9d8f")
    ax.invert_yaxis()
    ax.set_xlabel("Benefit per US$ million (higher is better)")
    for b, v in zip(bars, values):
        ax.annotate(f"{v}", (b.get_width(), b.get_y() + b.get_height() / 2),
                    va="center", ha="left", fontsize=9, xytext=(4, 0), textcoords="offset points")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig4_ranking.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig5_outcome_heatmap():
    """Shows all four outcome scores across all interventions as a
    heatmap, making visually explicit which interventions affect which
    outcomes and which do not, reinforcing the sanity check reported in
    Section VI and IX: hospitals and road interventions correctly show
    zero change in the flood risk column, since neither is a causal
    parent of flood risk in the graph."""
    path = os.path.join(DATA_DIR, "interventions_results.json")
    if not os.path.exists(path):
        print(f"  [fig5] skipped: {path} not found. Run intervention_engine.py first.")
        return
    with open(path) as f:
        results = json.load(f)

    outcome_keys = ["flood_risk_score", "health_access_score", "traffic_score", "emergency_response_score"]
    outcome_labels = ["Flood risk", "Health access", "Traffic", "Emergency response"]
    names = [r["name"].split("[")[0].strip() for r in results]
    matrix = [[r[k] for k in outcome_keys] for r in results]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(outcome_labels)))
    ax.set_xticklabels(outcome_labels, rotation=20, ha="right")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    for i in range(len(names)):
        for j in range(len(outcome_labels)):
            ax.text(j, i, f"{matrix[i][j]:.1f}", ha="center", va="center", fontsize=8,
                     color="black")
    plt.colorbar(im, ax=ax, label="Score (0-100)", fraction=0.046, pad=0.04)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig5_outcome_heatmap.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig6_montecarlo_distributions():
    """Overlays the full Monte Carlo sampled distributions (not just
    mean and interval) for three representative interventions, making
    directly visible how much the baseline and the +50% drainage
    capacity distributions actually separate, beyond what a single
    error bar can show."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from structural_equations import load_exogenous_inputs
    from intervention_engine import INTERVENTIONS, apply_intervention
    from uncertainty import sample_flood_score, N_SAMPLES

    try:
        baseline_inputs = load_exogenous_inputs()
    except FileNotFoundError as e:
        print(f"  [fig6] skipped: {e}")
        return

    selected = {
        "Baseline (observed)": "#6c757d",
        "do(drainage_capacity = 1.5)  [+50% drainage capacity]": "#e9c46a",
        "do(drainage_capacity = 1.5, vegetation += 15pp)  [combined flood package]": "#2a9d8f",
    }

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for intervention in INTERVENTIONS:
        if intervention["name"] not in selected:
            continue
        kwargs = apply_intervention(intervention["overrides"], baseline_inputs)
        drainage = kwargs.get("drainage_capacity_factor", 1.0)
        vegetation_pct = kwargs.get("vegetation_pct_override", baseline_inputs["vegetation_pct"])
        population = baseline_inputs["population"]
        samples = [sample_flood_score(baseline_inputs, drainage, vegetation_pct, population, seed_offset=i)
                   for i in range(N_SAMPLES)]
        label = intervention["name"].split("[")[1].rstrip("]") if "[" in intervention["name"] else intervention["name"]
        ax.hist(samples, bins=40, alpha=0.55, label=label, color=selected[intervention["name"]], density=True)

    ax.set_xlabel("Flood risk score (0-100)")
    ax.set_ylabel("Density")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig6_montecarlo_distributions.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig7_runoff_coefficient_curve():
    """Plots the Rational Method composite runoff coefficient as a
    continuous function of vegetation cover fraction from 0 to 100
    percent, marking Cape Coast's actual observed point, so the reader
    can see directly where the real city falls on this curve and how
    sensitive the coefficient is to further vegetation change in either
    direction."""
    from structural_equations import C_IMPERVIOUS, C_VEGETATED, compute_runoff_coefficient

    veg_range = [i / 2 for i in range(0, 201)]  # 0 to 100 in 0.5 steps
    C_values = [compute_runoff_coefficient(v) for v in veg_range]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(veg_range, C_values, color="#4a90d9", linewidth=2)
    ax.axhline(C_IMPERVIOUS, color="#e76f51", linestyle="--", linewidth=1,
               label=f"Fully impervious reference (C={C_IMPERVIOUS})")
    ax.axhline(C_VEGETATED, color="#2a9d8f", linestyle="--", linewidth=1,
               label=f"Fully vegetated reference (C={C_VEGETATED})")

    path = os.path.join(DATA_DIR, "sentinel_vegetation.json")
    if os.path.exists(path):
        with open(path) as f:
            sv = json.load(f)
        cape_coast_veg = sv["threshold_sensitivity"]["used_threshold_0.4"]["pct_of_area"]
        source_label = "Cape Coast (live Sentinel-2 NDVI)"
    else:
        cape_coast_veg = 51.98
        source_label = "Cape Coast (fallback estimate)"
    cape_coast_C = compute_runoff_coefficient(cape_coast_veg)
    ax.scatter([cape_coast_veg], [cape_coast_C], color="black", s=90, zorder=5,
               label=f"{source_label}: {cape_coast_veg:.1f}% veg, C={cape_coast_C:.3f}")

    ax.set_xlabel("Dense vegetation cover (%)")
    ax.set_ylabel("Composite Rational Method runoff coefficient (C)")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig7_runoff_coefficient_curve.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def fig8_active_paths():
    """Draws the causal graph twice side by side, highlighting in red
    the specific path activated by a drainage capacity intervention
    (which reaches flood risk) versus a hospitals intervention (which
    does not), giving a direct visual explanation for the zero-effect
    sanity check reported in Sections VI and IX."""
    G = build_causal_graph()
    generations = list(nx.topological_generations(G))
    pos = {}
    for x, layer in enumerate(generations):
        n = len(layer)
        for i, node in enumerate(layer):
            y = (i - (n - 1) / 2)
            pos[node] = (x * 2.4, y * 1.9)

    def draw_panel(ax, active_nodes, active_edges, title):
        node_colors = ["#e76f51" if n in active_nodes else "#d9d9d9" for n in G.nodes()]
        edge_colors = ["#e76f51" if e in active_edges else "#d9d9d9" for e in G.edges()]
        edge_widths = [2.2 if e in active_edges else 0.8 for e in G.edges()]
        edge_z = [3 if e in active_edges else 1 for e in G.edges()]
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2600, ax=ax,
                                edgecolors="black", linewidths=0.8)
        # Draw inactive edges first (straight, background), then active
        # edges on top with a small curvature only, so a highlighted edge
        # cannot visually swoop through an unrelated node's position.
        inactive = [e for e in G.edges() if e not in active_edges]
        active = [e for e in G.edges() if e in active_edges]
        nx.draw_networkx_edges(G, pos, edgelist=inactive, ax=ax, arrowstyle="-|>", arrowsize=14,
                                width=0.8, edge_color="#d9d9d9", connectionstyle="arc3,rad=0.0",
                                arrows=True, node_size=2600, min_source_margin=13, min_target_margin=13)
        nx.draw_networkx_edges(G, pos, edgelist=active, ax=ax, arrowstyle="-|>", arrowsize=18,
                                width=2.4, edge_color="#e76f51", connectionstyle="arc3,rad=0.3",
                                arrows=True, node_size=2600, min_source_margin=13, min_target_margin=13)
        labels = {n: n.replace("_", "\n") for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=6, ax=ax)
        ax.set_title(title, fontsize=10)
        ax.axis("off")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    drainage_nodes = {"drainage_capacity", "peak_runoff_index", "flood_risk_score", "emergency_response_score"}
    drainage_edges = [("drainage_capacity", "peak_runoff_index"), ("peak_runoff_index", "flood_risk_score"),
                       ("flood_risk_score", "emergency_response_score")]
    draw_panel(axes[0], drainage_nodes, drainage_edges,
               "do(drainage_capacity): reaches flood risk\n(and, through it, emergency response)")

    hospital_nodes = {"hospitals", "health_access_score", "emergency_response_score"}
    hospital_edges = [("hospitals", "health_access_score"), ("health_access_score", "emergency_response_score")]
    draw_panel(axes[1], hospital_nodes, hospital_edges,
               "do(hospitals): reaches health access\n(never touches flood risk)")

    fig.tight_layout()
    out = os.path.join(FIG_DIR, "fig8_active_paths.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    print(f"  wrote {out}")


def main():
    print("[plotting] Generating all CausaTwin figures ...")
    fig1_causal_graph()
    fig2_intervention_comparison()
    fig3_uncertainty_bands()
    fig4_ranking()
    fig5_outcome_heatmap()
    fig6_montecarlo_distributions()
    fig7_runoff_coefficient_curve()
    fig8_active_paths()
    print("[plotting] Done.")


if __name__ == "__main__":
    main()