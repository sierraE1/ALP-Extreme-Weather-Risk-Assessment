"""
clustering.py
=============
Clusters meshed CSV+Parquet flood data by user-selected dimensions.
Each dataset (XLSX, Parquet) is clustered independently — they don't
share a feature space since Parquet lacks impact metrics.

Reads:  Map_Visualization/Frontend/src/data/points_all_years.json
Writes: same file, in place, with xlsx_kmeans_cluster / xlsx_hierarchical_cluster
        and/or parquet_kmeans_cluster / parquet_hierarchical_cluster added.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import math

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_PATH = PROJECT_ROOT / "Map_Visualization" / "Frontend" / "src" / "data" / "points_all_years.json"
OUTPUT_PATH = PROJECT_ROOT / "Map_Visualization" / "Frontend" / "public" / "data" / "events_clustered.json"

XLSX_DIMENSIONS = {
    "area": ("area_km2", True),
    "duration": ("Duration (days)", False),
    "fatalities": ("Fatalities", True),
    "displaced": ("Displaced", True),
}
PARQUET_DIMENSIONS = {
    "area": ("area_km2", True),
    "duration": ("Duration (days)", False),
}

SELECTED_DIMENSIONS = ["area"]   # start 1D — add more names to go multi-dimensional


from sklearn.cluster import DBSCAN

EPS_KM = 50            # points within this distance are spatially "the same place"
MAX_GAP_DAYS = 4         # temporal gap threshold to split events at the same place
EARTH_RADIUS_KM = 6371.0


def assign_parquet_event_ids(red_points: list) -> dict:
    """
    Groups Parquet-only (unmatched) points into synthetic events using
    spatial (DBSCAN, haversine) + temporal (gap-split) clustering — same
    method as estimate_parquet_events.py, but returns an id per point
    instead of just a count, and works on the already-meshed point dicts.
    Returns: {point_id: synthetic_event_id}
    """
    if not red_points:
        return {}

    df = pd.DataFrame([{
        "id": p["id"],
        "year": p["year"],
        "lat": p["lat"],
        "lng": p["lng"],
        "start_date": p["metrics"].get("start_date"),  # see note below if missing
    } for p in red_points])

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    event_id_map = {}

    for year, year_df in df.groupby("year"):
        coords = np.radians(year_df[["lat", "lng"]].values)
        eps_rad = EPS_KM / EARTH_RADIUS_KM
        db = DBSCAN(eps=eps_rad, min_samples=1, metric="haversine", algorithm="ball_tree")
        spatial_labels = db.fit_predict(coords)
        year_df = year_df.copy()
        year_df["spatial_cluster"] = spatial_labels

        for spatial_id, group in year_df.groupby("spatial_cluster"):
            group = group.sort_values("start_date").reset_index(drop=True)
            event_counter = 0
            prev_date = None
            for _, row in group.iterrows():
                if prev_date is not None:
                    gap = (row["start_date"] - prev_date).days if pd.notna(row["start_date"]) and pd.notna(prev_date) else 0
                    if gap > MAX_GAP_DAYS:
                        event_counter += 1
                synthetic_id = f"pq-{year}-{spatial_id}-{event_counter}"
                event_id_map[row["id"]] = synthetic_id
                prev_date = row["start_date"]

    return event_id_map


def aggregate_by_event(meshed_points: list) -> pd.DataFrame:
    """
    Collapses raw polygon-level meshed_points into one row per real event:
      - Matched (purple) points  -> grouped by matched_event_id (XLSX row)
      - Parquet-only (red) points -> grouped by synthetic DBSCAN event id
      - XLSX-only (blue) points  -> already one row per event, kept as-is
    """
    red_points = [p for p in meshed_points if p["source_flags"]["in_parquet"] and not p["source_flags"]["in_csv"]]
    other_points = [p for p in meshed_points if not (p["source_flags"]["in_parquet"] and not p["source_flags"]["in_csv"])]

    print(f"  Grouping {len(red_points):,} Parquet-only points into synthetic events...")
    red_event_ids = assign_parquet_event_ids(red_points)

    rows = []
    for p in other_points:
        event_id = p["metrics"].get("matched_event_id") or p["id"]
        rows.append({**p["metrics"], "id": p["id"], "event_id": event_id,
                     "lat": p["lat"], "lng": p["lng"],          # ← add this
                     "in_parquet": p["source_flags"]["in_parquet"],
                     "in_csv": p["source_flags"]["in_csv"]})
    for p in red_points:
        event_id = red_event_ids.get(p["id"], p["id"])
        rows.append({**p["metrics"], "id": p["id"], "event_id": event_id,
                     "lat": p["lat"], "lng": p["lng"],          # ← add this
                     "in_parquet": True, "in_csv": False})

    df = pd.DataFrame(rows)

    agg = df.groupby("event_id").agg(
        lat=("lat", "mean"),                        
        lng=("lng", "mean"), 
        parquet_area_km2=("parquet_area_km2", "sum"),
        parquet_duration_days=("parquet_duration_days", "max"),
        csv_area_km2=("csv_area_km2", "first"),
        csv_duration_days=("csv_duration_days", "first"),
        fatalities=("fatalities", "first"),
        displaced=("displaced", "first"),
        fragment_count=("id", "count"),
        in_parquet=("in_parquet", "any"),
        in_csv=("in_csv", "any"),
    ).reset_index()

    print(f"  Aggregated {len(df):,} points → {len(agg):,} distinct events")
    print(f"  Fragment count per event — min: {agg['fragment_count'].min()}, "
          f"max: {agg['fragment_count'].max()}, mean: {agg['fragment_count'].mean():.1f}")

    return agg

def build_feature_matrix(df, dim_map, selected):
    missing = [d for d in selected if d not in dim_map]
    if missing:
        raise ValueError(f"Unknown dimension(s): {missing}. Available: {list(dim_map.keys())}")
    feats = {}
    for dim in selected:
        col, log = dim_map[dim]
        values = df[col].fillna(0)
        feats[dim] = np.log1p(values) if log else values
    return pd.DataFrame(feats)


def cluster_dataset(df, dim_map, selected, label):
    if len(df) == 0:
        print(f"  [{label}] No rows — skipping.")
        return df

    feats = build_feature_matrix(df, dim_map, selected)
    X = StandardScaler().fit_transform(feats)

    n = len(df)
    max_k = min(10, n - 1)
    if max_k < 2:
        print(f"  [{label}] Only {n} samples — not enough to cluster.")
        df["kmeans_cluster"] = -1
        df["hierarchical_cluster"] = -1
        return df

    k_range = range(2, max_k + 1)

    def best_k(cluster_fn):
        best_k_, best_score_, best_labels_ = None, -1, None
        for k in k_range:
            labels = cluster_fn(k).fit_predict(X)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(X, labels)
            if score > best_score_:
                best_k_, best_score_, best_labels_ = k, score, labels
        return best_labels_, best_k_, best_score_

    km_labels, km_k, km_score = best_k(lambda k: KMeans(n_clusters=k, random_state=42, n_init=10))
    hc_labels, hc_k, hc_score = best_k(lambda k: AgglomerativeClustering(n_clusters=k, linkage="ward"))

    df["kmeans_cluster"] = km_labels if km_labels is not None else -1
    df["hierarchical_cluster"] = hc_labels if hc_labels is not None else -1

    print(f"\n  [{label}] Dimensions: {selected}  |  n={n}")
    print(f"  [{label}] KMeans: best k={km_k} (silhouette={km_score:.3f})" if km_k else f"  [{label}] KMeans: no valid k found")
    print(f"  [{label}] Hierarchical: best k={hc_k} (silhouette={hc_score:.3f})" if hc_k else f"  [{label}] Hierarchical: no valid k found")

    return df

def cluster_dataset_multi(df: pd.DataFrame, dim_map: dict, label: str) -> pd.DataFrame:
    """
    Runs 1D clustering separately for every dimension in dim_map,
    storing each as its own column pair: {dim}_kmeans_cluster, {dim}_hierarchical_cluster.
    """
    for dim_name in dim_map.keys():
        result = cluster_dataset(df.copy(), dim_map, [dim_name], f"{label}:{dim_name}")
        df[f"{dim_name}_kmeans_cluster"] = result["kmeans_cluster"]
        df[f"{dim_name}_hierarchical_cluster"] = result["hierarchical_cluster"]
    return df

def main():
    if not INPUT_PATH.exists():
        print(f"[!] {INPUT_PATH} not found. Run Data_Cleaning/Processing.py first.")
        return

    with open(INPUT_PATH) as f:
        meshed_points = json.load(f)

    if not meshed_points:
        print("[!] No meshed points to cluster.")
        return
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Loaded {len(meshed_points):,} meshed points from {INPUT_PATH}")

    event_df = aggregate_by_event(meshed_points)

    xlsx_rows = event_df[event_df["in_csv"]].rename(columns={
        "csv_area_km2": "area_km2", "csv_duration_days": "Duration (days)",
        "fatalities": "Fatalities", "displaced": "Displaced"
    })
    xlsx_rows = cluster_dataset_multi(xlsx_rows, XLSX_DIMENSIONS, "XLSX")

    parquet_rows = event_df[event_df["in_parquet"]].rename(columns={
        "parquet_area_km2": "area_km2", "parquet_duration_days": "Duration (days)"
    })
    parquet_rows = cluster_dataset_multi(parquet_rows, PARQUET_DIMENSIONS, "Parquet")

    xlsx_cluster_cols = [f"{d}_kmeans_cluster" for d in XLSX_DIMENSIONS] + [f"{d}_hierarchical_cluster" for d in XLSX_DIMENSIONS]
    parquet_cluster_cols = [f"{d}_kmeans_cluster" for d in PARQUET_DIMENSIONS] + [f"{d}_hierarchical_cluster" for d in PARQUET_DIMENSIONS]

    xlsx_lookup = xlsx_rows.set_index("event_id")[xlsx_cluster_cols].to_dict("index") if len(xlsx_rows) else {}
    parquet_lookup = parquet_rows.set_index("event_id")[parquet_cluster_cols].to_dict("index") if len(parquet_rows) else {}

    event_df["xlsx_clusters"] = event_df["event_id"].map(lambda e: xlsx_lookup.get(e, {}))
    event_df["parquet_clusters"] = event_df["event_id"].map(lambda e: parquet_lookup.get(e, {}))

    def clean_nans(obj):
        """Recursively replaces float NaN with None so JSON serializes as valid `null`."""
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: clean_nans(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_nans(v) for v in obj]
        return obj

    event_records = event_df.to_dict("records")
    event_records = clean_nans(event_records)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(event_records, f, indent=2)
    print(f"\n✓ Wrote {len(event_records):,} event-level records with cluster labels to {OUTPUT_PATH}")

    with open(OUTPUT_PATH) as f:
        data = json.load(f)

    print("Total records:", len(data))
    print("First record:", data[0])
    print("Has lat/lng?", "lat" in data[0], "lng" in data[0])


if __name__ == "__main__":
    main()