# Flood Map Dashboard

This folder contains a Vite + React dashboard for GitHub Pages.

## Local development

1. Install dependencies:

   ```bash
   npm install
   ```

2. Build the parquet data for the app:

   ```bash
   python ..\Backend\export_parquet_to_json.py --input ..\..\Data_Cleaning\groundsource_2026.parquet --output public\data\events.geojson --us-only --limit 5000
   ```

3. Start the app:

   ```bash
   npm run dev
   ```

## GitHub Pages

The repository includes a GitHub Actions workflow that exports the parquet file and deploys the built site to Pages.
