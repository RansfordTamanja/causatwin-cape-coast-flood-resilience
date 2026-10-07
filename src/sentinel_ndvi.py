"""
sentinel_ndvi.py

Computes a real, live Normalized Difference Vegetation Index (NDVI) from
the Sentinel-2 Red (B04) and Near-Infrared (B08) bands downloaded by
sentinel_fetch.py, and estimates the current dense-vegetation cover for
the Cape Coast bounding box. This replaces the previously cited
secondary-literature figure (a 1991-2018 land-cover study) with a
directly computed, current measurement from the same open satellite
data referenced throughout the paper's proposed architecture.

NDVI = (NIR - Red) / (NIR + Red), computed per-pixel. Values above 0.4
are commonly used as an approximate threshold for dense/healthy
vegetation in tropical contexts; this script uses that threshold and
reports the sensitivity of the result to a +/-0.1 threshold shift so the
choice is not left unexamined.

Requires: pip install rasterio numpy

Writes:
    outputs/data/sentinel_vegetation.json
    outputs/figures/fig12_ndvi_map.png
"""

import json
import os
import sys

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
FIG_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "figures")
BAND_DIR = os.path.join(DATA_DIR, "sentinel_bands")
os.makedirs(FIG_DIR, exist_ok=True)

NDVI_DENSE_THRESHOLD = 0.4

# Same Cape Coast Metropolitan bounding box used by parse_osm.py and
# sentinel_fetch.py (min_lon, min_lat, max_lon, max_lat), in WGS84.
BBOX_WGS84 = (-1.34, 5.02, -1.15, 5.19)


def load_band_clipped(path, bbox_wgs84):
    """Reads only the pixels within the Cape Coast bounding box, not the
    full Sentinel-2 tile. A raw tile covers roughly 100km x 100km
    (~10,000 km^2), which for a coastal city like Cape Coast includes a
    large amount of open ocean; computing a vegetation percentage against
    that full tile area, as an earlier version of this script did,
    understates true land vegetation cover by diluting it with ocean
    pixels that have near-zero NDVI. Clipping to the actual area of
    interest first is required for this figure to mean what it claims to
    mean."""
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.open(path) as src:
        # The bbox is in WGS84 (EPSG:4326); Sentinel-2 bands are in a UTM
        # projection, so reproject the bbox into the raster's CRS first.
        min_lon, min_lat, max_lon, max_lat = bbox_wgs84
        left, bottom, right, top = transform_bounds("EPSG:4326", src.crs,
                                                      min_lon, min_lat, max_lon, max_lat)
        window = from_bounds(left, bottom, right, top, transform=src.transform)
        band = src.read(1, window=window).astype("float32")
        transform = src.window_transform(window)
        pixel_area_m2 = abs(transform.a * transform.e)
        crs = src.crs
    return band, pixel_area_m2, crs


def main():
    red_path = os.path.join(BAND_DIR, "B04_red.jp2")
    nir_path = os.path.join(BAND_DIR, "B08_nir.jp2")

    if not (os.path.exists(red_path) and os.path.exists(nir_path)):
        print(f"[sentinel_ndvi] ERROR: expected bands not found in {BAND_DIR}")
        print("                Run sentinel_fetch.py first.")
        sys.exit(1)

    try:
        import rasterio  # noqa: F401
    except ImportError:
        print("[sentinel_ndvi] ERROR: 'rasterio' not installed. Run: pip install rasterio")
        sys.exit(1)

    print(f"[sentinel_ndvi] Loading Sentinel-2 Red and NIR bands, clipped to the Cape Coast "
          f"bounding box {BBOX_WGS84} (not the full satellite tile) ...")
    red, pixel_area_m2, crs = load_band_clipped(red_path, BBOX_WGS84)
    nir, _, _ = load_band_clipped(nir_path, BBOX_WGS84)

    if red.shape != nir.shape:
        print(f"[sentinel_ndvi] ERROR: band shape mismatch ({red.shape} vs {nir.shape}).")
        sys.exit(1)
    if red.size == 0:
        print("[sentinel_ndvi] ERROR: the clipped window is empty. The downloaded scene may not "
              "actually overlap the Cape Coast bounding box; check sentinel_scene_metadata.json.")
        sys.exit(1)

    print("[sentinel_ndvi] Computing NDVI ...")
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    ndvi = np.nan_to_num(ndvi, nan=-1.0)

    valid_pixels = np.sum((red > 0) | (nir > 0))  # exclude no-data borders
    total_area_km2 = valid_pixels * pixel_area_m2 / 1e6

    results = {}
    for label, threshold in [("low_threshold_0.3", 0.3), ("used_threshold_0.4", NDVI_DENSE_THRESHOLD),
                              ("high_threshold_0.5", 0.5)]:
        dense_pixels = np.sum(ndvi > threshold)
        dense_area_km2 = dense_pixels * pixel_area_m2 / 1e6
        results[label] = {
            "threshold": threshold,
            "dense_vegetation_km2": round(dense_area_km2, 2),
            "pct_of_area": round(dense_area_km2 / total_area_km2 * 100, 2) if total_area_km2 else None,
        }

    output = {
        "crs": str(crs),
        "clipped_to_bbox_wgs84": list(BBOX_WGS84),
        "total_area_km2": round(total_area_km2, 2),
        "ndvi_dense_threshold_used": NDVI_DENSE_THRESHOLD,
        "dense_vegetation_km2": results["used_threshold_0.4"]["dense_vegetation_km2"],
        "threshold_sensitivity": results,
        "mean_ndvi": round(float(np.mean(ndvi[ndvi > -1])), 3),
        "source": "Computed live from Sentinel-2 L2A bands downloaded via the Copernicus Data "
                  "Space Ecosystem, clipped to the Cape Coast bounding box, not from cited "
                  "secondary literature and not diluted by the full satellite tile's ocean area.",
    }

    out_path = os.path.join(DATA_DIR, "sentinel_vegetation.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[sentinel_ndvi] Cape Coast bounding box area: {total_area_km2:.1f} km^2")
    print(f"[sentinel_ndvi] Dense vegetation (NDVI > {NDVI_DENSE_THRESHOLD}): "
          f"{output['dense_vegetation_km2']:.1f} km^2 "
          f"({results['used_threshold_0.4']['pct_of_area']:.1f}% of area)")
    print(f"[sentinel_ndvi] Threshold sensitivity: "
          f"{results['low_threshold_0.3']['dense_vegetation_km2']:.1f} km^2 @ NDVI>0.3, "
          f"{results['high_threshold_0.5']['dense_vegetation_km2']:.1f} km^2 @ NDVI>0.5")
    print(f"[sentinel_ndvi] Wrote {out_path}")

    # Simple visualization
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(ndvi, cmap="RdYlGn", vmin=-0.2, vmax=0.8)
    ax.set_title(f"Figure 12. NDVI, Cape Coast Bounding Box\nDense vegetation (NDVI > {NDVI_DENSE_THRESHOLD}): "
                 f"{output['dense_vegetation_km2']:.1f} km$^2$ ({results['used_threshold_0.4']['pct_of_area']:.1f}% of area)")
    ax.axis("off")
    plt.colorbar(im, ax=ax, label="NDVI", fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig_path = os.path.join(FIG_DIR, "fig12_ndvi_map.png")
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"[sentinel_ndvi] Wrote {fig_path}")


if __name__ == "__main__":
    main()
