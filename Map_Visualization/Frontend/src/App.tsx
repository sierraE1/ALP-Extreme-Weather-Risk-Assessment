import { useEffect, useMemo, useState } from 'react'
import {
  MapContainer,
  CircleMarker,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'

import type { MapPoint } from './types'

type DatasetPoint = MapPoint & {
  parquet_area_km2?: number | null
  csv_area_km2?: number | null
  parquet_duration_days?: number | null
  csv_duration_days?: number | null
  fatalities?: number | null
  displaced?: number | null
  fragment_count?: number | null
  parquet_clusters?: Record<string, number>
  xlsx_clusters?: Record<string, number>
}

function FlyToPoint({ point }: { point: DatasetPoint | null }) {
  const map = useMap()

  useEffect(() => {
    if (!point) return

    map.flyTo([point.lat, point.lng], 10, {
      duration: 1.25,
    })
  }, [map, point])

  return null
}

export default function App() {
  const [points, setPoints] = useState<DatasetPoint[]>([])
  const [selectedPoint, setSelectedPoint] = useState<DatasetPoint | null>(null)

  const [selectedDim, setSelectedDim] = useState<'area' | 'duration' | 'fatalities' | 'displaced'>('area')
  const center = useMemo<[number, number]>(() => [39.8283, -98.5795], [])

  useEffect(() => {
    const controller = new AbortController()

    async function loadPoints() {
      const response = await fetch(`${import.meta.env.BASE_URL}data/events_clustered.json`, {
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`Failed to load points data: ${response.status}`)
      }

      const data = (await response.json()) as DatasetPoint[]
      console.log('Loaded points:', data.length, data[0])
      setPoints(data)
    }

    loadPoints().catch((error) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      console.error(error)
    })

    return () => controller.abort()
  }, [])

  const clusterColors = ['#4CAF50', '#FF9800', '#F44336', '#9C27B0', '#3F51B5']

  const getMarkerStyle = (point: MapPoint) => {
    const isOverlap = point.source_flags?.in_parquet && point.source_flags?.in_csv

    const parquetClusterId = point.parquet_clusters?.[`${selectedDim}_kmeans_cluster`]
    const xlsxClusterId = point.xlsx_clusters?.[`${selectedDim}_kmeans_cluster`]
    const clusterId = parquetClusterId ?? xlsxClusterId

    const fill = clusterId !== undefined && clusterId !== -1
      ? clusterColors[clusterId % clusterColors.length]
      : '#9E9E9E' // gray: no data for this dimension on this point

    return {
      fillColor: fill,
      color: '#ffffff',
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8,
      radius: isOverlap ? 10 : 5,
    }
  }

  const getClusterValue = (point: DatasetPoint, dataset: 'parquet' | 'xlsx') => {
    switch (selectedDim) {
      case 'area':
        return dataset === 'parquet'
          ? Number(point.parquet_area_km2 ?? 0)
          : Number(point.csv_area_km2 ?? point.parquet_area_km2 ?? 0)
      case 'duration':
        return dataset === 'parquet'
          ? Number(point.parquet_duration_days ?? 0)
          : Number(point.csv_duration_days ?? point.parquet_duration_days ?? 0)
      case 'fatalities':
        return Number(point.fatalities ?? 0)
      case 'displaced':
        return Number(point.displaced ?? 0)
      default:
        return 0
    }
  }

  const buildClusterLegend = (dataset: 'parquet' | 'xlsx') => {
    const groups: Record<number, number[]> = {}

    points.forEach((point) => {
      const clusterId =
        dataset === 'parquet'
          ? point.parquet_clusters?.[`${selectedDim}_kmeans_cluster`]
          : point.xlsx_clusters?.[`${selectedDim}_kmeans_cluster`]

      if (clusterId === undefined || clusterId === -1) return

      const value = getClusterValue(point, dataset)

      if (!groups[clusterId]) groups[clusterId] = []
      groups[clusterId].push(value)
    })

    return Object.entries(groups)
      .map(([id, values]) => ({
        id: Number(id),
        min: Math.min(...values),
        max: Math.max(...values),
        count: values.length,
      }))
      .sort((a, b) => a.min - b.min)
  }

  // Sorting logic
const filteredAndSortedPoints = useMemo(() => {
  const result = [...points]

  const fieldMap: Record<typeof selectedDim, keyof DatasetPoint> = {
    area: 'parquet_area_km2',
    duration: 'parquet_duration_days',
    fatalities: 'fatalities',
    displaced: 'displaced',
  }
  const field = fieldMap[selectedDim]

  result.sort((a, b) => (Number(b[field]) || 0) - (Number(a[field]) || 0))

  return result
}, [points, selectedDim])

const parquetLegend = useMemo(() => buildClusterLegend('parquet'), [points, selectedDim])
const xlsxLegend = useMemo(() => buildClusterLegend('xlsx'), [points, selectedDim])

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Interactive Map</p>
          <h1>United States Points Viewer</h1>
          <p className="subtitle">
            Plot locations across the U.S. and click a marker or list item to
            inspect details.
          </p>
        </div>
      </header>

      <main className="layout">
        <section className="map-panel" aria-label="Map panel">
          <MapContainer
            center={center}
            zoom={4}
            minZoom={3}
            maxZoom={12}
            scrollWheelZoom
            className="map"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <FlyToPoint point={selectedPoint} />

            {filteredAndSortedPoints.map((point: DatasetPoint) => (
              <CircleMarker
                key={point.event_id}
                center={[point.lat, point.lng]}
                pathOptions={getMarkerStyle(point)}
                eventHandlers={{
                  click: () => setSelectedPoint(point),
                }}
              >
                <Popup>
                  <div className="popup-content">
                    <strong>Event {point.event_id}</strong>
                    <hr style={{ margin: '8px 0', borderColor: '#eee' }} />

                    <div>
                      <strong>Duration:</strong> {point.parquet_duration_days} days
                      {point.csv_duration_days && ` (CSV: ${point.csv_duration_days} days)`}
                    </div>
                    <div>
                      <strong>Impact Profile:</strong> {point.fatalities ?? 'No records'} Fatalities | {point.displaced ?? '0'} Displaced
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </section>

        <aside className="sidebar" aria-label="Point list">
          <div className="sidebar-card">
            <h2>Locations</h2>
            <p className="sidebar-text">
              Select a location to zoom the map.
            </p>

            <div className="control-panel">
              <select
                className="sort-select"
                value={selectedDim}
                onChange={(e) => setSelectedDim(e.target.value as any)}
              >
                <option value="area">Area</option>
                <option value="duration">Duration</option>
                <option value="fatalities">Fatalities (XLSX only)</option>
                <option value="displaced">Displaced (XLSX only)</option>
              </select>
            </div>

            <ul className="point-list">
              {filteredAndSortedPoints.map((point: DatasetPoint) => {
                const isActive = selectedPoint?.event_id === point.event_id

                return (
                  <li key={point.event_id}>
                    <button
                      className={`point-button ${isActive ? 'active' : ''}`}
                      onClick={() => setSelectedPoint(point)}
                    >
                      <span className="point-name">Event {point.event_id}</span>
                      <span className="point-meta">
                        {point.fragment_count ?? 0} fragments
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </aside>

        <aside className="legend-column" aria-label="Dataset legends">
          {[
            { label: 'Parquet dataset', legend: parquetLegend },
            { label: 'XLSX dataset', legend: xlsxLegend },
          ].map(({ label, legend }) => (
            <div
              key={label}
              className="legend-card"
            >
              <p className="legend-title">
                {label} - Clusters by {selectedDim}
              </p>

              {legend.length > 0 ? (
                legend.map((group) => (
                  <div
                    key={group.id}
                    className="legend-row"
                  >
                    <span
                      className="legend-dot"
                      style={{ backgroundColor: clusterColors[group.id % clusterColors.length] }}
                    />
                    <span>
                      {group.min.toFixed(1)}–{group.max.toFixed(1)} ({group.count} events)
                    </span>
                  </div>
                ))
              ) : (
                <div className="legend-row legend-row-empty">
                  <span className="legend-dot legend-dot-empty" />
                  <span>No clustered points for this dataset</span>
                </div>
              )}
            </div>
          ))}
        </aside>
      </main>
    </div>
  )
}