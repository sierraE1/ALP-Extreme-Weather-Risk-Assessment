export type MapPoint = {
  id: string
  name: string
  city: string
  state: string
  lat: number
  lng: number
  description?: string
  source_flags?: {
      in_parquet: boolean;
      in_csv: boolean;
      warnings: string[];
    };
    metrics?: {
      parquet_area_km2: number;
      csv_area_km2: number | null;
      parquet_duration_days: number;
      csv_duration_days: number | null;
      fatalities: number | null;
      displaced: number | null;
      cluster_tier: string;
      severity?: number | null;
    };
  }