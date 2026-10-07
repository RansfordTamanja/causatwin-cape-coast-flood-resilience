"""
fetch_climate.py

Fetches daily rainfall and temperature data for Cape Coast, Ghana from the
NASA POWER API (https://power.larc.nasa.gov/), which is free and requires
no account or API key.

If the API cannot be reached from the current network (some sandboxed /
CI environments block it via robots.txt or firewall rules — this is a
network-policy issue, not a data-availability issue; the API itself is
public), this script falls back to a small set of cited published climate
figures for Cape Coast so that the rest of the pipeline still has numbers
to work with. Every fallback value is tagged with its source.

Writes:
    outputs/data/climate_daily.csv      (only if the live fetch succeeds)
    outputs/data/climate_summary.csv    (always — live-derived or fallback)
"""

import csv
import os
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "data")
os.makedirs(DATA_DIR, exist_ok=True)

LATITUDE = 5.106
LONGITUDE = -1.246
START = "20200101"
END = "20241231"

# Cited published figures, used only if the live API is unreachable.
FALLBACK = {
    "mean_elevation_m": (110.87, "weatherandclimate.com, Cape Coast Climate Profile"),
    "mean_annual_temp_c": (27.6, "weatherandclimate.com, Cape Coast Climate Profile"),
    "rainy_days_per_year": (205.89, "weatherandclimate.com, Cape Coast Climate Profile"),
    "rainfall_coastal_low_mm": (90, "Wikipedia: Cape Coast, citing Ghana Meteorological Agency data"),
    "rainfall_coastal_high_mm": (110, "Wikipedia: Cape Coast, citing Ghana Meteorological Agency data"),
    "rainfall_hinterland_low_mm": (110, "Wikipedia: Cape Coast, citing Ghana Meteorological Agency data"),
    "rainfall_hinterland_high_mm": (160, "Wikipedia: Cape Coast, citing Ghana Meteorological Agency data"),
    "vegetation_1991_km2": (71.13, "2023 land-cover change study, cited in Wikipedia: Cape Coast"),
    "vegetation_2018_km2": (47.12, "2023 land-cover change study, cited in Wikipedia: Cape Coast"),
    "vegetation_loss_pct": (24.01, "2023 land-cover change study, cited in Wikipedia: Cape Coast"),
}


def try_fetch_live():
    """Attempt a live NASA POWER daily-point request. Returns a list of
    row-dicts on success, or None on any failure (network, HTTP, parse)."""
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR",
        "community": "RE",
        "longitude": LONGITUDE,
        "latitude": LATITUDE,
        "start": START,
        "end": END,
        "format": "JSON",
    }
    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()["properties"]["parameter"]
        dates = sorted(next(iter(payload.values())).keys())
        rows = []
        for d in dates:
            rows.append({
                "date": d,
                "T2M": payload["T2M"][d],
                "T2M_MAX": payload["T2M_MAX"][d],
                "T2M_MIN": payload["T2M_MIN"][d],
                "PRECTOTCORR": payload["PRECTOTCORR"][d],
            })
        return rows
    except Exception as e:
        print(f"  [fetch_climate] Live NASA POWER fetch failed: {e}")
        return None


def write_summary_from_live(rows):
    n = len(rows)
    mean_temp = sum(float(r["T2M"]) for r in rows) / n
    total_rain = sum(float(r["PRECTOTCORR"]) for r in rows if float(r["PRECTOTCORR"]) != -999)
    years = n / 365.25
    mean_annual_rain = total_rain / years
    max_daily_rain = max(float(r["PRECTOTCORR"]) for r in rows)

    daily_path = os.path.join(DATA_DIR, "climate_daily.csv")
    with open(daily_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"])
        w.writeheader()
        w.writerows(rows)

    summary_path = os.path.join(DATA_DIR, "climate_summary.csv")
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "unit", "source"])
        w.writerow(["mean_annual_temp_c", round(mean_temp, 2), "degrees C", "NASA POWER API (live), point query"])
        w.writerow(["mean_annual_rainfall_mm", round(mean_annual_rain, 1), "mm/year", "NASA POWER API (live), point query"])
        w.writerow(["max_daily_rainfall_mm", round(max_daily_rain, 1), "mm/day", "NASA POWER API (live), point query"])
        w.writerow(["data_mode", "live", "-", f"NASA POWER daily point API, {START}-{END}"])
    print(f"  [fetch_climate] Live fetch succeeded: {n} days. Wrote {daily_path} and {summary_path}")


def write_summary_from_fallback():
    summary_path = os.path.join(DATA_DIR, "climate_summary.csv")
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "unit", "source"])
        for metric, (value, source) in FALLBACK.items():
            w.writerow([metric, value, "", source])
        w.writerow(["data_mode", "fallback", "-", "Live NASA POWER API unreachable from this network"])
    print(f"  [fetch_climate] Using fallback published figures. Wrote {summary_path}")


def main():
    print("[fetch_climate] Requesting NASA POWER data for Cape Coast (5.106, -1.246) ...")
    rows = try_fetch_live()
    if rows:
        write_summary_from_live(rows)
    else:
        write_summary_from_fallback()


if __name__ == "__main__":
    main()
