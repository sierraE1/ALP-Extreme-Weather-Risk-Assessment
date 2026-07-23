"""
estimate_parquet_events.py
===========================
Estimates the number of distinct flood *events* in the Groundsource Parquet
dataset by spatiotemporally clustering its 2.6M individual polygon detections.

Method:
  1. Extract centroid lat/lng from each polygon's geometry.
  2. Per year, spatially cluster centroids with DBSCAN (haversine distance).
  3. Within each spatial cluster, split into separate events wherever
     consecutive dates have a gap larger than MAX_GAP_DAYS (handles the same
     location flooding repeatedly in unrelated events).

Usage:
    python estimate_parquet_events.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from shapely import wkt, wkb
from sklearn.cluster import DBSCAN

BASE_DIR = Path(__file__).resolve().parent
PARQUET_PATH = BASE_DIR / "groundsource_2026.parquet"

EPS_KM = 50            # points within this distance are spatially "the same place"
MAX_GAP_DAYS = 4        # temporal gap threshold to split events at the same place
EARTH_RADIUS_KM = 6371.0


def extract_centroids(df: pd.DataFrame) -> pd.DataFrame:
    """Parses each row's geometry into a centroid lat/lng. Slow at full scale — see note below."""
    lats, lngs, valid_idx = [], [], []
    for idx, geom in df["geometry"].items():
        if pd.isna(geom):
            continue
        try:
            poly = wkt.loads(geom) if isinstance(geom, str) else wkb.loads(geom)
            c = poly.centroid
            lats.append(c.y)
            lngs.append(c.x)
            valid_idx.append(idx)
        except Exception:
            continue

    out = df.loc[valid_idx].copy()
    out["centroid_lat"] = lats
    out["centroid_lng"] = lngs
    return out


def cluster_year(year_df: pd.DataFrame, eps_km=EPS_KM, max_gap_days=MAX_GAP_DAYS) -> int:
    """Returns the estimated number of distinct events within a single year's data."""
    if len(year_df) == 0:
        return 0

    # DBSCAN with haversine needs radians, and eps expressed as radians too
    coords = np.radians(year_df[["centroid_lat", "centroid_lng"]].values)
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=1, metric="haversine", algorithm="ball_tree")
    spatial_labels = db.fit_predict(coords)
    year_df = year_df.copy()
    year_df["spatial_cluster"] = spatial_labels

    event_count = 0
    for _, group in year_df.groupby("spatial_cluster"):
        dates = group["start_date"].sort_values().reset_index(drop=True)
        if len(dates) == 1:
            event_count += 1
            continue
        gaps = dates.diff().dt.days.fillna(0)
        # every time the gap exceeds max_gap_days, that's a new event starting
        event_count += (gaps > max_gap_days).sum() + 1

    return event_count


def main():
    print("Loading Parquet...")
    df = pd.read_parquet(PARQUET_PATH)
    df.columns = df.columns.str.strip()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["Year"] = df["start_date"].dt.year
    print(f"  Loaded {len(df):,} rows")

    print("Extracting centroids (this is the slow step)...")
    df = extract_centroids(df)
    print(f"  {len(df):,} rows with valid centroids")

    total_events = 0
    print("\nClustering per year:")
    for year, year_df in df.groupby("Year"):
        n_events = cluster_year(year_df)
        total_events += n_events
        print(f"  {year}: {len(year_df):>8,} polygons  →  ~{n_events:>6,} estimated events")

    print(f"\n✓ Estimated total distinct flood events in Parquet: ~{total_events:,}")
    print(f"  (from {len(df):,} raw polygon detections — "
          f"~{len(df)/total_events:.1f} fragments per event on average)")


if __name__ == "__main__":
    main()