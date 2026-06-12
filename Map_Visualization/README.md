# Map Visualization

This folder contains a Vite + React dashboard for GitHub Pages.

## Frontend

The frontend loads grouped GeoJSON from `Frontend/public/data/groundsource-us.json` and renders:

- a United States map
- clickable dots for grouped flood locations
- a details panel that shows every overlapping record in the clicked group

## Local run

```bash
cd Map_Visualization/Frontend
npm install
npm run dev
```

## GitHub Pages build

```bash
cd Map_Visualization/Frontend
npm run build
```

The Vite config uses a relative base path so the app works on GitHub Pages.

## Parquet export

To convert the parquet file into the grouped JSON format used by the dashboard:

```bash
python Map_Visualization/Backend/export_parquet_to_geojson.py
```

The exporter reads `Data_Cleaning/groundsource_2026.parquet` and writes the output to `Frontend/public/data/groundsource-us.json`.
