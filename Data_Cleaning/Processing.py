"""
flood_analysis.py
=================
Analyzes two flood datasets:
  1. Global Flood Records  → CSV     (human-curated, ~5,500 events, impact metrics)
  2. Gemini Groundsource   → Parquet (LLM-curated, ~2.6M events, spatiotemporal only)

Groundsource schema (from paper Table 2):
    uuid        – unique record ID
    area_km2    – polygon area
    start_date  – YYYY-MM-DD
    end_date    – YYYY-MM-DD
    geometry    – WKT polygon (WGS 84)

Because Groundsource has NO impact metrics (fatalities/displaced), the two
datasets are analyzed on their shared axes: time, area, and duration.
Cluster proxies are built from those shared features.

Next step: replace assign_clusters() with sklearn KMeans/DBSCAN.

Usage:
    python flood_analysis.py

Dependencies:
    pip install pandas pyarrow matplotlib seaborn scikit-learn shapely
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
from pathlib import Path

# ─────────────────────────── CONFIGURATION ────────────────────────────────────
# Resolve data relative to this script, not the current terminal folder.
BASE_DIR     = Path(__file__).resolve().parent
CSV_PATH     = BASE_DIR / "Global_Flood_Records.csv"
PARQUET_PATH = BASE_DIR / "groundsource_2026.parquet"
OUTPUT_DIR   = BASE_DIR / "flood_analysis_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Rule-based cluster: duration × log(area) proxy score → 3 tiers
# Swap this out for KMeans/DBSCAN when ready (see assign_clusters docstring)
CLUSTER_BINS  = [0, 3.5, 7.0, float("inf")]
CLUSTER_NAMES = ["Short & Local", "Mid-Scale", "Large & Prolonged"]

PALETTE = {
    "Short & Local":    "#4CAF50",
    "Mid-Scale":        "#FF9800",
    "Large & Prolonged":"#F44336",
    "Unknown":          "#9E9E9E",
    # CSV impact tiers (used in CSV-only plots)
    "Low Impact":       "#4CAF50",
    "Moderate Impact":  "#FF9800",
    "High Impact":      "#F44336",
}

# ─────────────────────────── HELPERS ──────────────────────────────────────────

def _cluster_score(area_km2, duration_days):
    """
    Cheap proxy score combining log-area and duration.
    Replace this entire function + assign_clusters() with ML clustering later.
    """
    log_area = np.log1p(pd.to_numeric(area_km2, errors="coerce").fillna(0))
    dur      = pd.to_numeric(duration_days, errors="coerce").fillna(0).clip(lower=0)
    return log_area * 0.6 + dur * 0.4


def assign_clusters(df: pd.DataFrame,
                    area_col: str = "area_km2",
                    dur_col:  str = "Duration (days)") -> pd.DataFrame:
    """
    Rule-based tier assignment on a proxy score of log(area) + duration.

    ── TO REPLACE WITH ML CLUSTERING ──────────────────────────────────────────
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    feats = df[[area_col, dur_col]].fillna(0)
    feats["log_area"] = np.log1p(feats[area_col])
    X = StandardScaler().fit_transform(feats[["log_area", dur_col]])
    df["Cluster"] = KMeans(n_clusters=3, random_state=42).fit_predict(X)
    # Map integer labels → names after inspecting cluster centroids
    ────────────────────────────────────────────────────────────────────────────
    """
    if area_col not in df.columns:
        df["Cluster"] = "Unknown"
        return df

    dur = df[dur_col] if dur_col in df.columns else pd.Series(0, index=df.index)
    score = _cluster_score(df[area_col], dur)

    df["Cluster"] = pd.cut(
        score,
        bins=CLUSTER_BINS,
        labels=CLUSTER_NAMES,
        right=True,
    ).astype(str)
    return df


# ─────────────────────────── LOADERS ──────────────────────────────────────────

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    for col in ["Start Date", "End Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "Area (km²)" in df.columns:
        df["area_km2"] = (
            df["Area (km²)"].astype(str)
            .str.replace(",", "", regex=False)
        )
        df["area_km2"] = pd.to_numeric(df["area_km2"], errors="coerce")

    if "Start Date" in df.columns:
        df["Year"] = df["Start Date"].dt.year
        df["Month"] = df["Start Date"].dt.month
        # Keep only 2000–2026 for analysis
        df = df[df["Year"].between(2000, 2026)]
    if "Country" in df.columns:
        df = df[df["Country"] == "United States of America"]
    if "Start Date" in df.columns and "End Date" in df.columns:
        # Offset by 1 so the minimum duration is 1 day instead of 0.
        df["Duration (days)"] = (
            (df["End Date"] - df["Start Date"]).dt.days.fillna(0).clip(lower=0) + 1
        )

    if "Main Cause" in df.columns:
        df["Main Cause"] = df["Main Cause"].str.strip().str.title()

    print(f"[CSV]     Loaded {len(df):,} rows")
    return df


def load_parquet(path: str) -> pd.DataFrame:
    """
    Loads Groundsource parquet.
    Expected schema (paper Table 2):
        uuid, area_km2, start_date, end_date, geometry
    """
    df = pd.read_parquet(path)
    df.columns = df.columns.str.strip()

    for col in ["start_date", "end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Derive shared fields so downstream code is dataset-agnostic
    if "start_date" in df.columns:
        df["Year"]  = df["start_date"].dt.year
        df["Month"] = df["start_date"].dt.month

        # Keep only 2000–2026
        df = df[(df["Year"] >= 2000) & (df["Year"] <= 2026)]

    if "start_date" in df.columns and "end_date" in df.columns:
        # Offset by 1 so the minimum duration is 1 day instead of 0.
        df["Duration (days)"] = (
            (df["end_date"] - df["start_date"]).dt.days.fillna(0).clip(lower=0) + 1
        )

    print(f"[Parquet] Loaded {len(df):,} rows  |  cols: {list(df.columns)}")

        #debug
    print("Rows:", len(df))
    print("Zero area:", (df["area_km2"] == 0).sum())
    print("Null area:", df["area_km2"].isna().sum())

    print(df["area_km2"].describe())

    print(
        df["area_km2"]
        .value_counts(dropna=False)
        .head(20)
    )
    zero_area = df[df["area_km2"] == 0]

    print("Zero-area rows:", len(zero_area))

    print(zero_area[[
        "uuid",
        "area_km2",
        "start_date",
        "end_date"
    ]].head())
    zero_area = df[df["area_km2"] == 0]

    print(
        "Zero-area rows with geometry:",
        zero_area["geometry"].notna().sum()
    )

    print(
        "Total zero-area rows:",
        len(zero_area)
    )
    print("Zeroes:", (df["area_km2"] == 0).sum())
    print("Percent zero:",
        100 * (df["area_km2"] == 0).mean())

    return df


# ─────────────────────────── CSV PLOTS ────────────────────────────────────────

def plot_csv_overview(df: pd.DataFrame):
    fig = plt.figure(figsize=(20, 13))
    fig.suptitle("Global Flood Records (CSV) – Trend Overview",
                 fontsize=16, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.48, wspace=0.35)

    # 1. Events per year
    ax = fig.add_subplot(gs[0, :2])
    if "Year" in df.columns:
        yearly = df.groupby("Year").size().reset_index(name="Events")
        ax.bar(yearly["Year"], yearly["Events"], color="#1976D2", alpha=0.85, width=0.8)
        ax.set_title("Flood Events per Year"); ax.set_xlabel("Year"); ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=45)

    # 2. Impact-index cluster pie
    ax = fig.add_subplot(gs[0, 2])
    impact_clusters = pd.cut(
        df["Flood impact index"],
        bins=[0, 3.5, 6.0, float("inf")],
        labels=["Low Impact", "Moderate Impact", "High Impact"],
    ).value_counts()
    colors = [PALETTE.get(c, "#9E9E9E") for c in impact_clusters.index]
    ax.pie(impact_clusters, labels=impact_clusters.index, colors=colors,
           autopct="%1.1f%%", startangle=140)
    ax.set_title("Impact Tier Distribution")

    # 3. Monthly seasonality
    ax = fig.add_subplot(gs[0, 2])
    if "Month" in df.columns:
        monthly = df.groupby("Month").size()
        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ax.bar(range(1, 13), [monthly.get(m, 0) for m in range(1, 13)],
               color="#F57C00", edgecolor="white", alpha=0.9)
        ax.set_xticks(range(1, 13)); ax.set_xticklabels(month_labels, fontsize=7)
        ax.set_title("Monthly Seasonality")
        ax.set_xlabel("Month"); ax.set_ylabel("Events")

    # 4. Main causes
    ax = fig.add_subplot(gs[1, :2])
    causes = df["Main Cause"].value_counts().head(8)
    ax.barh(causes.index[::-1], causes.values[::-1], color="#7B1FA2", alpha=0.85)
    ax.set_title("Main Causes (Top 8)"); ax.set_xlabel("Events")
    ax.tick_params(axis="y", labelsize=7)

    # 5. Area vs duration
    ax = fig.add_subplot(gs[1, 2])
    area_mask = (df["area_km2"] > 0) & df["Duration (days)"].notna()
    scatter_data = df[area_mask].copy()
    ax.scatter(
        np.log1p(scatter_data["area_km2"]),
        scatter_data["Duration (days)"],
        c="#1976D2",
        alpha=0.25,
        s=10,
    )
    ax.set_title("log(Area km²) vs Duration")
    ax.set_xlabel("log(Area km²)"); ax.set_ylabel("Duration (days)")

    # 6. Fatalities by severity
    ax = fig.add_subplot(gs[2, 0])
    sub = df[df["Fatalities"] > 0]
    sns.boxplot(data=sub, x="Severity", y="Fatalities", palette="Oranges", ax=ax)
    ax.set_yscale("log"); ax.set_title("Fatalities by Severity (log)")

    # 7. Displaced by severity
    ax = fig.add_subplot(gs[2, 1])
    sub = df[df["Displaced"] > 0]
    sns.boxplot(data=sub, x="Severity", y="Displaced", palette="Blues", ax=ax)
    ax.set_yscale("log"); ax.set_title("Displaced by Severity (log)")

    # 8. Area vs impact index
    ax = fig.add_subplot(gs[2, 2])
    mask = (df["area_km2"] > 0) & df["Flood impact index"].notna()
    scatter_data = df[area_mask].copy()
    scatter_data = df[mask].copy()
    scatter_data["impact_tier"] = pd.cut(
        scatter_data["Flood impact index"],
        bins=[0, 3.5, 6.0, float("inf")],
        labels=["Low Impact", "Moderate Impact", "High Impact"],
    )
    for tier, grp in scatter_data.groupby("impact_tier"):
        ax.scatter(np.log1p(grp["area_km2"]), grp["Flood impact index"],
                   c=PALETTE.get(str(tier), "#9E9E9E"), alpha=0.25, s=8, label=tier)
    ax.set_title("log(Area) vs Impact Index")
    ax.set_xlabel("log(Area km²)"); ax.set_ylabel("Impact Index")
    ax.legend(fontsize=7, markerscale=2)

    out = OUTPUT_DIR / "csv_overview.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  → {out}")
    plt.close()


# ─────────────────────────── PARQUET PLOTS ────────────────────────────────────

def plot_parquet_overview(df: pd.DataFrame):
    """
    Groundsource has: uuid, area_km2, start_date, end_date, geometry
    (+ derived: Year, Month, Duration (days), Cluster)
    So all plots are time / area / duration / geography based.
    """
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle("Groundsource (Parquet) – Spatiotemporal Overview",
                 fontsize=16, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    # 1. Events per year
    ax = fig.add_subplot(gs[0, :2])
    if "Year" in df.columns:
        yearly = df.groupby("Year").size().reset_index(name="Events")
        ax.bar(yearly["Year"], yearly["Events"], color="#1976D2", alpha=0.85, width=0.8)
        ax.set_title("Flood Events per Year (Groundsource)")
        ax.set_xlabel("Year"); ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=45)
        # Annotate recency bias note from paper
        ax.annotate("~64% of events 2020–2025\n(reflects media growth, not flood increase)",
                    xy=(0.98, 0.92), xycoords="axes fraction",
                    ha="right", fontsize=7, color="gray",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    # 2. Cluster pie (spatiotemporal tiers)
    ax = fig.add_subplot(gs[0, 2])
    if "Cluster" in df.columns:
        cc = df["Cluster"].value_counts()
        colors = [PALETTE.get(c, "#9E9E9E") for c in cc.index]
        ax.pie(cc, labels=cc.index, colors=colors, autopct="%1.1f%%", startangle=140)
        ax.set_title("Spatiotemporal Tier Distribution")

    # 3. Area distribution (log)
    ax = fig.add_subplot(gs[1, 0])
    if "area_km2" in df.columns:
        valid = df["area_km2"].dropna()
        valid = valid[valid > 0]
        ax.hist(np.log1p(valid), bins=60, color="#0288D1", edgecolor="white", alpha=0.85)
        ax.set_title("log(Area km²) Distribution")
        ax.set_xlabel("log(Area km²)"); ax.set_ylabel("Events")

    # 4. Duration distribution
    ax = fig.add_subplot(gs[1, 1])
    if "Duration (days)" in df.columns:
        dur = df["Duration (days)"].dropna()
        dur = dur[(dur >= 0) & (dur <= 7)]   # paper filters >7 days
        ax.hist(dur, bins=8, color="#7B1FA2", edgecolor="white", alpha=0.85,
                rwidth=0.85)
        ax.set_title("Event Duration Distribution")
        ax.set_xlabel("Days"); ax.set_ylabel("Events")
        ax.set_xticks(range(0, 8))

    # 5. Monthly seasonality
    ax = fig.add_subplot(gs[1, 2])
    if "Month" in df.columns:
        monthly = df.groupby("Month").size()
        month_labels = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"]
        ax.bar(range(1,13), [monthly.get(m, 0) for m in range(1,13)],
               color="#F57C00", edgecolor="white", alpha=0.9)
        ax.set_xticks(range(1,13)); ax.set_xticklabels(month_labels, fontsize=7)
        ax.set_title("Monthly Seasonality")
        ax.set_xlabel("Month"); ax.set_ylabel("Events")

    out = OUTPUT_DIR / "parquet_overview.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  → {out}")
    plt.close()


# ─────────────────────────── COMBINED PLOT ────────────────────────────────────

def plot_combined_comparison(csv_df: pd.DataFrame, parquet_df: pd.DataFrame):
    """
    Compare the two datasets on their shared axes: time, area, duration.
    (No impact/fatalities in Groundsource — so no cross-metric plots.)
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("Dataset Comparison: CSV (Global Flood Records) vs Parquet (Groundsource)",
                 fontsize=13, fontweight="bold")

    # 1. Events per year — overlay
    ax = axes[0]
    if "Year" in csv_df.columns and "Year" in parquet_df.columns:
        csv_yr = csv_df.groupby("Year").size()
        # Keep only 2000–2026 for fair comparison 
        parquet_df = parquet_df[parquet_df["Year"].between(2000, 2026)]
        par_yr = parquet_df.groupby("Year").size()
        all_years = sorted(set(csv_yr.index) | set(par_yr.index))
        ax.plot(all_years, [csv_yr.get(y, 0) for y in all_years],
                marker="o", ms=3, label="CSV", color="#1976D2")
        ax2 = ax.twinx()
        ax2.plot(all_years, [par_yr.get(y, 0) for y in all_years],
                 marker="s", ms=3, label="Parquet", color="#F57C00", alpha=0.8)
        ax.set_title("Events per Year (dual axis)")
        ax.set_ylabel("CSV events", color="#1976D2")
        ax2.set_ylabel("Parquet events", color="#F57C00")
        ax.set_xlabel("Year"); ax.tick_params(axis="x", rotation=45)
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    # 2. Area distribution — side by side (log)
    ax = axes[1]
    csv_area = csv_df["area_km2"].dropna()
    csv_area = np.log1p(csv_area[csv_area > 0])
    if "area_km2" in parquet_df.columns:
        par_area = parquet_df["area_km2"].dropna()
        par_area = np.log1p(par_area[par_area > 0])
        ax.hist(par_area, bins=60, alpha=0.5, color="#F57C00", label="Parquet", density=True)
    ax.hist(csv_area, bins=40, alpha=0.7, color="#1976D2", label="CSV", density=True)
    ax.set_title("log(Area km²) — Normalized")
    ax.set_xlabel("log(Area km²)"); ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    ax.annotate("Groundsource filters\nevents >5,000 km²\n(per paper §2.4)",
                xy=(0.97, 0.92), xycoords="axes fraction", ha="right",
                fontsize=7, color="gray",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    # 3. Duration distribution — side by side
    ax = axes[2]
    if "Duration (days)" in csv_df.columns:
        csv_dur = csv_df["Duration (days)"].dropna().clip(0, 30)
        ax.hist(csv_dur, bins=30, alpha=0.7, color="#1976D2", label="CSV", density=True)
    if "Duration (days)" in parquet_df.columns:
        par_dur = parquet_df["Duration (days)"].dropna().clip(0, 7)
        ax.hist(par_dur, bins=7, alpha=0.5, color="#F57C00", label="Parquet", density=True)
    ax.set_title("Event Duration — Normalized")
    ax.set_xlabel("Days"); ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    ax.annotate("Groundsource caps\nevents at 7 days\n(per paper §2.4)",
                xy=(0.97, 0.92), xycoords="axes fraction", ha="right",
                fontsize=7, color="gray",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    plt.tight_layout()
    out = OUTPUT_DIR / "combined_comparison.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  → {out}")
    plt.close()


# ─────────────────────────── SUMMARY ──────────────────────────────────────────

def print_summary(df: pd.DataFrame, label: str):
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print(f"{'─'*60}")
    print(f"  Rows: {len(df):,}   Columns: {len(df.columns)}")
    if "Year" in df.columns:
        print(f"  Date range: {int(df['Year'].min())} – {int(df['Year'].max())}")
    if "Cluster" in df.columns:
        print(f"\n  Cluster counts:\n{df['Cluster'].value_counts().to_string()}")
    num_cols = [c for c in ["area_km2","Duration (days)","Fatalities","Displaced",
                             "Flood impact index","Severity"] if c in df.columns]
    if num_cols:
        print(f"\n  Numeric stats:\n{df[num_cols].describe().round(5).to_string()}")


# ─────────────────────────── MAIN ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Flood Data Analysis")
    print("=" * 60)

    # ── CSV ────────────────────────────────────────────────────────────────────
    csv_df = None
    if Path(CSV_PATH).exists():
        csv_df = load_csv(CSV_PATH)
        csv_df = assign_clusters(csv_df)
        print_summary(csv_df, "Global Flood Records (CSV)")
        print("\n  Generating CSV charts…")
        plot_csv_overview(csv_df)
    else:
        print(f"[!] CSV not found at {CSV_PATH}")

    # ── Parquet ────────────────────────────────────────────────────────────────
    parquet_df = None
    if Path(PARQUET_PATH).exists():
        parquet_df = load_parquet(PARQUET_PATH)
        parquet_df = assign_clusters(parquet_df)
        print_summary(parquet_df, "Groundsource (Parquet)")
        print("\n  Generating Parquet charts…")
        plot_parquet_overview(parquet_df)
    else:
        print(f"[!] Parquet not found at {PARQUET_PATH} – skipping.")
        print("    Download from: https://doi.org/10.5281/zenodo.18647053")

    # ── Combined ───────────────────────────────────────────────────────────────
    if csv_df is not None and parquet_df is not None:
        print("\n  Generating combined comparison chart…")
        plot_combined_comparison(csv_df, parquet_df)

    print(f"\n✓ Outputs saved to: {OUTPUT_DIR.resolve()}")
    print("=" * 60)
    print("  Schema reminder — Groundsource columns:")
    print("    uuid | area_km2 | start_date | end_date | geometry")
    print()
    print("=" * 60)
    #Next Steps- ML Clustering


if __name__ == "__main__":
    main()