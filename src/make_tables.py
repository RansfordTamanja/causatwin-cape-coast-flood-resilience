"""
make_tables.py

Generates the one additional table not already produced by
intervention_engine.py, uncertainty.py, and ranking.py: a listing of
every node in the causal graph, its role, and its description, so the
paper can present the graph structure in table form alongside the
diagram from plotting.py.
"""

import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
TAB_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
os.makedirs(TAB_DIR, exist_ok=True)


def table_graph_structure():
    path = os.path.join(DATA_DIR, "causal_graph_structure.json")
    if not os.path.exists(path):
        print(f"  [table_graph_structure] skipped: {path} not found. Run causal_graph.py first.")
        return
    with open(path) as f:
        structure = json.load(f)

    csv_path = os.path.join(TAB_DIR, "table_graph_nodes.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Node", "Role", "Description"])
        for n in structure["nodes"]:
            w.writerow([n["id"], n["role"], n["desc"]])

    md_path = os.path.join(TAB_DIR, "table_graph_nodes.md")
    with open(md_path, "w") as f:
        f.write("| Node | Role | Description |\n|---|---|---|\n")
        for n in structure["nodes"]:
            f.write(f"| {n['id']} | {n['role']} | {n['desc']} |\n")

    print(f"  wrote {csv_path}")
    print(f"  wrote {md_path}")


def main():
    print("[make_tables] Generating remaining CausaTwin tables ...")
    table_graph_structure()
    print("[make_tables] Done. (Intervention, uncertainty, and ranking tables are written "
          "directly by intervention_engine.py, uncertainty.py, and ranking.py.)")


if __name__ == "__main__":
    main()
