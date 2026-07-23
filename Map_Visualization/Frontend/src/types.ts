export interface MapPoint {
  event_id: string
  lat: number
  lng: number
  source_flags: {
    in_parquet: boolean
    in_csv: boolean
  }
  metrics: {
    parquet_area_km2: number | null
    parquet_duration_days: number | null
    csv_area_km2: number | null
    csv_duration_days: number | null
    fatalities: number | null
    displaced: number | null
    fragment_count: number
  }
  xlsx_clusters?: Record<string, number>
  parquet_clusters?: Record<string, number>
}