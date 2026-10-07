"""
parse_osm.py

Parses a Ghana OpenStreetMap .pbf extract (e.g. from Geofabrik:
https://download.geofabrik.de/africa/ghana.html), spatially clips it to a
bounding box around the Cape Coast Metropolitan area, and counts
infrastructure features relevant to the CityMind agents: hospitals,
clinics, schools, universities, road segments (by class), buildings, and
waterways.

Requires the `osmium` package (pip install osmium) and a local .pbf file.
If either is missing, this script exits with a clear message rather than
silently producing empty output — infrastructure counts are load-bearing
for the paper's Health, Traffic, and Emergency Response sections and
should never be silently faked.

Input (default; override with --pbf):
    inputs/ghana-latest.osm.pbf

Writes:
    outputs/data/osm_stats.json
"""

import argparse
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
DEFAULT_PBF = os.path.join(os.path.dirname(__file__), "..", "inputs", "ghana-latest.osm.pbf")
os.makedirs(DATA_DIR, exist_ok=True)

# Bounding box around Cape Coast Metropolitan Assembly and immediate
# surrounding communities (min_lon, min_lat, max_lon, max_lat)
BBOX = (-1.34, 5.02, -1.15, 5.19)


def in_bbox(lon, lat, bbox=BBOX):
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def build_handler():
    import osmium

    class CapeCoastHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.counts = {
                "hospitals": 0, "clinics": 0, "health_total": 0,
                "schools": 0, "universities": 0,
                "roads_total": 0, "roads_by_type": {},
                "buildings": 0, "rivers_waterways": 0,
                "named_places": 0,
            }

        def node(self, n):
            if not n.location.valid():
                return
            lon, lat = n.location.lon, n.location.lat
            if not in_bbox(lon, lat):
                return
            tags = dict(n.tags)
            amenity = tags.get("amenity")
            if amenity == "hospital":
                self.counts["hospitals"] += 1
                self.counts["health_total"] += 1
            elif amenity == "clinic":
                self.counts["clinics"] += 1
                self.counts["health_total"] += 1
            elif amenity == "school":
                self.counts["schools"] += 1
            elif amenity in ("university", "college"):
                self.counts["universities"] += 1
            if tags.get("place") in ("city", "town", "suburb", "village"):
                self.counts["named_places"] += 1

        def way(self, w):
            try:
                first = w.nodes[0]
                if not first.location.valid():
                    return
                lon, lat = first.location.lon, first.location.lat
            except Exception:
                return
            if not in_bbox(lon, lat):
                return
            tags = dict(w.tags)
            highway = tags.get("highway")
            if highway:
                self.counts["roads_total"] += 1
                self.counts["roads_by_type"][highway] = self.counts["roads_by_type"].get(highway, 0) + 1
            if tags.get("building"):
                self.counts["buildings"] += 1
            if tags.get("waterway"):
                self.counts["rivers_waterways"] += 1
            amenity = tags.get("amenity")
            if amenity == "hospital":
                self.counts["hospitals"] += 1
                self.counts["health_total"] += 1
            elif amenity == "school":
                self.counts["schools"] += 1

    return CapeCoastHandler()


def main():
    parser = argparse.ArgumentParser(description="Parse Ghana OSM .pbf for Cape Coast infrastructure stats.")
    parser.add_argument("--pbf", default=DEFAULT_PBF, help="Path to a Ghana .osm.pbf extract")
    args = parser.parse_args()

    if not os.path.exists(args.pbf):
        print(f"[parse_osm] ERROR: PBF file not found at {args.pbf}")
        print("            Download from https://download.geofabrik.de/africa/ghana.html")
        print("            and place it at inputs/ghana-latest.osm.pbf, or pass --pbf <path>.")
        sys.exit(1)

    try:
        import osmium  # noqa: F401
    except ImportError as e:
        print("[parse_osm] ERROR: could not import the 'osmium' package.")
        print(f"            Underlying error: {type(e).__name__}: {e}")
        print("            'pip show osmium' may report it as installed even when it fails to")
        print("            import, usually because of a missing/mismatched native DLL dependency")
        print("            on Windows. Try: pip uninstall osmium -y && pip install osmium")
        print("            If that doesn't fix it, try a clean virtual environment:")
        print("              python -m venv venv")
        print("              venv\\Scripts\\activate")
        print("              pip install osmium")
        sys.exit(1)
    except Exception as e:
        print(f"[parse_osm] ERROR: unexpected failure importing 'osmium': {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"[parse_osm] Parsing {args.pbf} (this can take a couple of minutes for a full-country extract) ...")
    handler = build_handler()
    handler.apply_file(args.pbf, locations=True)

    out_path = os.path.join(DATA_DIR, "osm_stats.json")
    with open(out_path, "w") as f:
        json.dump(handler.counts, f, indent=2)

    print(f"[parse_osm] Done: {handler.counts['roads_total']} road segments, "
          f"{handler.counts['buildings']} buildings, {handler.counts['hospitals']} hospitals, "
          f"{handler.counts['schools']} schools.")
    print(f"[parse_osm] Wrote {out_path}")


if __name__ == "__main__":
    main()
