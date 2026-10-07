"""
sentinel_fetch.py

Closes the one limitation this project could not previously address
without external account credentials: authenticates with the Copernicus
Data Space Ecosystem, searches for a low-cloud Sentinel-2 Level-2A scene
over the Cape Coast bounding box, and downloads the Red (B04) and
Near-Infrared (B08) bands needed to compute a real NDVI-based vegetation
estimate in sentinel_ndvi.py.

CREDENTIALS: this script reads your Copernicus username and password
from environment variables, exactly like the ANTHROPIC_API_KEY /
GEMINI_API_KEY pattern used elsewhere in this pipeline. It never asks
for them interactively, never logs them, and never stores them anywhere
on disk. Set them before running:

    Windows (PowerShell):
        $env:COPERNICUS_USERNAME = "your-email@example.com"
        $env:COPERNICUS_PASSWORD = "your-password"
    macOS/Linux:
        export COPERNICUS_USERNAME="your-email@example.com"
        export COPERNICUS_PASSWORD="your-password"

Sign up for a free account at: https://dataspace.copernicus.eu/

Writes:
    outputs/data/sentinel_scene_metadata.json
    outputs/data/sentinel_bands/  (downloaded GeoTIFF band files)
"""

import json
import os
import sys
import zipfile

import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
BAND_DIR = os.path.join(DATA_DIR, "sentinel_bands")
os.makedirs(DATA_DIR, exist_ok=True)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
ZIPPER_URL_TEMPLATE = "https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"

# Cape Coast Metropolitan bounding box (same as parse_osm.py)
BBOX = (-1.34, 5.02, -1.15, 5.19)
MAX_CLOUD_COVER = 20
COLLECTION = "SENTINEL-2"
PRODUCT_TYPE = "MSIL2A"  # Level-2A, atmospherically corrected, ready for NDVI


def get_access_token(username, password):
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    if not r.ok:
        try:
            detail = r.json().get("error_description", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Copernicus authentication failed ({r.status_code}): {detail}")
    return r.json()["access_token"]


def search_scenes(start_date="2024-01-01T00:00:00Z", end_date="2024-12-31T23:59:59Z"):
    min_lon, min_lat, max_lon, max_lat = BBOX
    footprint = (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )
    filter_str = (
        f"Collection/Name eq '{COLLECTION}' and "
        f"contains(Name,'{PRODUCT_TYPE}') and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{footprint}') and "
        f"ContentDate/Start gt {start_date} and ContentDate/Start lt {end_date} and "
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and "
        f"att/OData.CSC.DoubleAttribute/Value lt {MAX_CLOUD_COVER})"
    )
    params = {"$filter": filter_str, "$orderby": "ContentDate/Start desc", "$top": 10}

    print("[sentinel_fetch] Searching Sentinel-2 L2A catalog for Cape Coast scenes ...")
    r = requests.get(SEARCH_URL, params=params, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Copernicus catalog search failed ({r.status_code}): {r.text}")
    results = r.json()
    scenes = results.get("value", [])
    print(f"[sentinel_fetch] Found {len(scenes)} matching scene(s).")

    meta_path = os.path.join(DATA_DIR, "sentinel_scene_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(scenes, f, indent=2)
    print(f"[sentinel_fetch] Wrote {meta_path}")
    return scenes


def download_and_extract(product_id, product_name, token):
    """Downloads the full scene zip and extracts only the B04 and B08
    JP2 bands at 10m resolution, since the full product can exceed 1GB
    and only two bands are needed for NDVI."""
    os.makedirs(BAND_DIR, exist_ok=True)
    url = ZIPPER_URL_TEMPLATE.format(product_id=product_id)
    headers = {"Authorization": f"Bearer {token}"}
    zip_path = os.path.join(DATA_DIR, "sentinel_scene.zip")

    print(f"[sentinel_fetch] Downloading {product_name} (this can be 700MB-1GB, please be patient) ...")
    with requests.get(url, headers=headers, stream=True, timeout=600) as r:
        if not r.ok:
            raise RuntimeError(f"Scene download failed ({r.status_code}): {r.text[:500]}")
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r[sentinel_fetch]   {downloaded/1e6:.0f}MB / {total/1e6:.0f}MB ({pct:.0f}%)", end="")
    print()

    print("[sentinel_fetch] Extracting Red (B04) and NIR (B08) 10m bands ...")
    extracted = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith("_B04_10m.jp2"):
                out_path = os.path.join(BAND_DIR, "B04_red.jp2")
                with z.open(name) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                extracted["red_band"] = out_path
            elif name.endswith("_B08_10m.jp2"):
                out_path = os.path.join(BAND_DIR, "B08_nir.jp2")
                with z.open(name) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                extracted["nir_band"] = out_path

    os.remove(zip_path)  # the full zip is large; keep only the two bands we need
    if "red_band" not in extracted or "nir_band" not in extracted:
        raise RuntimeError("Could not find expected B04/B08 10m bands in the downloaded scene.")

    print(f"[sentinel_fetch] Extracted bands to {BAND_DIR}")
    return extracted


def main():
    username = os.environ.get("COPERNICUS_USERNAME")
    password = os.environ.get("COPERNICUS_PASSWORD")
    if not username or not password:
        print("[sentinel_fetch] ERROR: COPERNICUS_USERNAME and/or COPERNICUS_PASSWORD not set.")
        print("                 Set them in your terminal session before running this script.")
        print("                 Sign up for free at https://dataspace.copernicus.eu/")
        sys.exit(1)

    try:
        token = get_access_token(username, password)
    except Exception as e:
        print(f"[sentinel_fetch] ERROR: {e}")
        sys.exit(1)
    print("[sentinel_fetch] Authenticated successfully.")

    scenes = search_scenes()
    if not scenes:
        print("[sentinel_fetch] No scenes matched. Try widening MAX_CLOUD_COVER or the date range "
              "in this script.")
        sys.exit(1)

    best = scenes[0]
    extracted = download_and_extract(best["Id"], best["Name"], token)

    bands_meta_path = os.path.join(DATA_DIR, "sentinel_bands_downloaded.json")
    with open(bands_meta_path, "w") as f:
        json.dump({"scene_name": best["Name"], "scene_id": best["Id"], **extracted}, f, indent=2)
    print(f"[sentinel_fetch] Wrote {bands_meta_path}")
    print("[sentinel_fetch] Done. Run sentinel_ndvi.py next to compute real vegetation cover.")


if __name__ == "__main__":
    main()
