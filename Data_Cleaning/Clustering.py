"""
=============
Applies ML clustering (KMeans + Agglomerative/Hierarchical, both tuned via
silhouette score) to the meshed CSV+Parquet flood dataset produced by
Data_Cleaning/Processing.py.

Reads:  Map_Visualization/Frontend/src/data/points_2011.json
Writes: same file, in place, with kmeans_cluster / hierarchical_cluster
        added to each point's "metrics" object.

Usage:
    python clustering.py
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

# ─────────────────────────── CONFIGURATION ────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_PATH = PROJECT_ROOT / "Map_Visualization" / "Frontend" / "src" / "data" / "points_2011.json"
OUTPUT_PATH = INPUT_PATH  # overwrite in place; change if you want a separate file

K_RANGE = range(2, 8)


# ─────────────────────────── HELPERS ──────────────────────────────────────────

def flatten_for_clustering(meshed_points: list) -> pd.DataFrame:
    """
    Pulls numeric fields out of meshed_points, then aggregates Parquet
    fragments that share the same XLSX event (matched_event_id) into one
    row — otherwise one large event with many satellite polygon fragments
    would dominate clustering just by fragment count.
    """
    rows = []
    for p in meshed_points:
        m = p["metrics"]
        rows.append({
            "id": p["id"],
            "matched_event_id": m.get("matched_event_id", p["id"]),  # fallback if missing
            "parquet_area_km2": m["parquet_area_km2"],
            "parquet_duration_days": m["parquet_duration_days"],
            "csv_area_km2": m["csv_area_km2"],
            "csv_duration_days": m["csv_duration_days"],
            "fatalities": m["fatalities"],
            "displaced": m["displaced"],
        })
    df = pd.DataFrame(rows)

    agg = df.groupby("matched_event_id").agg(
        total_parquet_area_km2=("parquet_area_km2", "sum"),
        max_parquet_duration_days=("parquet_duration_days", "max"),
        fragment_count=("id", "count"),
        csv_area_km2=("csv_area_km2", "first"),
        csv_duration_days=("csv_duration_days", "first"),
        fatalities=("fatalities", "first"),
        displaced=("displaced", "first"),
    ).reset_index()

    print(f"\n  Aggregated {len(df)} Parquet fragments → {len(agg)} distinct XLSX events")
    print(f"  Fragment count per event — min: {agg['fragment_count'].min()}, "
          f"max: {agg['fragment_count'].max()}, mean: {agg['fragment_count'].mean():.1f}")

    return agg


def _best_k_by_silhouette(X, cluster_fn, k_range=K_RANGE):
    """Tries each k, scores with silhouette_score, returns (labels, k, score) for the best k."""
    best_k, best_score, best_labels = None, -1, None
    for k in k_range:
        model = cluster_fn(k)
        labels = model.fit_predict(X)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(X, labels)
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels
    return best_labels, best_k, best_score


def assign_ml_clusters(df: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame({
        "log_parquet_area": np.log1p(df["total_parquet_area_km2"].fillna(0)),
        "parquet_duration": df["max_parquet_duration_days"].fillna(0),
        "log_fatalities":   np.log1p(df["fatalities"].fillna(0)),
        "log_displaced":    np.log1p(df["displaced"].fillna(0)),
    })
    X = StandardScaler().fit_transform(feats)

    km_labels, km_k, km_score = _best_k_by_silhouette(
        X, lambda k: KMeans(n_clusters=k, random_state=42, n_init=10)
    )
    df["kmeans_cluster"] = km_labels
    print(f"\n  KMeans: best k={km_k} (silhouette={km_score:.3f})")
    print(df["kmeans_cluster"].value_counts().sort_index().to_string())

    hc_labels, hc_k, hc_score = _best_k_by_silhouette(
        X, lambda k: AgglomerativeClustering(n_clusters=k, linkage="ward")
    )
    df["hierarchical_cluster"] = hc_labels
    print(f"\n  Hierarchical: best k={hc_k} (silhouette={hc_score:.3f})")
    print(df["hierarchical_cluster"].value_counts().sort_index().to_string())

    print("\n  KMeans cluster profiles (mean values):")
    print(df.groupby("kmeans_cluster")[
        ["total_parquet_area_km2", "max_parquet_duration_days", "fatalities", "displaced"]
    ].mean().round(2).to_string())

    return df


# ─────────────────────────── MAIN ─────────────────────────────────────────────

def main():
    if not INPUT_PATH.exists():
        print(f"[!] {INPUT_PATH} not found. Run Data_Cleaning/Processing.py first.")
        return

    with open(INPUT_PATH) as f:
        meshed_points = json.load(f)

    if not meshed_points:
        print("[!] No meshed points to cluster.")
        return

    print(f"Loaded {len(meshed_points)} meshed points from {INPUT_PATH}")

    cluster_df = flatten_for_clustering(meshed_points)
    cluster_df = assign_ml_clusters(cluster_df)
    cluster_lookup = cluster_df.set_index("matched_event_id")[
        ["kmeans_cluster", "hierarchical_cluster"]
    ].to_dict("index")

    for p in meshed_points:
        labels = cluster_lookup.get(p["id"], {})
        p["metrics"]["kmeans_cluster"] = int(labels.get("kmeans_cluster", -1))
        p["metrics"]["hierarchical_cluster"] = int(labels.get("hierarchical_cluster", -1))
    
    with open(OUTPUT_PATH, "w") as f:
        json.dump(meshed_points, f, indent=2)
    print(f"\n✓ Wrote cluster labels back to {OUTPUT_PATH}")

    print("\n  KMeans cluster profiles (mean values):")
    print(cluster_df.groupby("kmeans_cluster")[
        ["parquet_area_km2", "parquet_duration_days", "fatalities", "displaced"]
    ].mean().round(2).to_string())

    print("\n  Hierarchical cluster profiles (mean values):")
    print(cluster_df.groupby("hierarchical_cluster")[
        ["parquet_area_km2", "parquet_duration_days", "fatalities", "displaced"]
    ].mean().round(2).to_string())

    with open(OUTPUT_PATH, "w") as f:
        json.dump(meshed_points, f, indent=2)
    print(f"\n✓ Wrote cluster labels back to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()