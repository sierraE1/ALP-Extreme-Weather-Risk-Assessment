import { useMemo, useState } from 'react'
import {
  MapContainer,
  CircleMarker,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'

import type { MapPoint } from './types'
import rawPoints from './data/points_2011.json'
const points = rawPoints as unknown as MapPoint[]

function FlyToPoint({ point }: { point: MapPoint | null }) {
  const map = useMap()

  if (point) {
    map.flyTo([point.lat, point.lng], 7, {
      duration: 1.25,
    })
  }

  return null
}

export default function App() {
  const [selectedPoint, setSelectedPoint] = useState<MapPoint | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<'none' | 'severity' | 'duration' | 'area'>('none')

  const center = useMemo<[number, number]>(() => [39.8283, -98.5795], [])

  // Dynamic Marker Colors based on severity
  const getMarkerStyle = (point: MapPoint) => {
    const severity = point.metrics?.severity ?? 0
    let fill = '#3b82f6' // Default Blue

    if (severity >= 3) fill = '#dc2626'      // High Risk - Red
    else if (severity >= 2) fill = '#ea580c' // Moderate Risk - Orange
    else if (severity >= 1) fill = '#eab308' // Low Risk - Yellow

    return {
      fillColor: fill,
      color: '#ffffff',
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8,
      radius: 8,
    }
  }

  // Sorting and Filtering Logic
  const filteredAndSortedPoints = useMemo(() => {
    let result = [...points]

    if (searchTerm) {
      const term = searchTerm.toLowerCase()
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(term) ||
          p.city.toLowerCase().includes(term) ||
          p.state.toLowerCase().includes(term)
      )
    }

    if (sortBy === 'severity') {
      result.sort((a, b) => (b.metrics?.severity ?? 0) - (a.metrics?.severity ?? 0))
    } else if (sortBy === 'duration') {
      result.sort((a, b) => (b.metrics?.parquet_duration_days ?? 0) - (a.metrics?.parquet_duration_days ?? 0))
    } else if (sortBy === 'area') {
      result.sort((a, b) => (b.metrics?.parquet_area_km2 ?? 0) - (a.metrics?.parquet_area_km2 ?? 0))
    }

    return result
  }, [searchTerm, sortBy])

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

            {filteredAndSortedPoints.map((point: MapPoint) => (
              <CircleMarker
                key={point.id}
                center={[point.lat, point.lng]}
                pathOptions={getMarkerStyle(point)}
                eventHandlers={{
                  click: () => setSelectedPoint(point),
                }}
              >
                <Popup>
                  <div className="popup-content">
                    <strong>{point.name}</strong>
                    <br />
                    {point.city}, {point.state}
                    <hr style={{ margin: '8px 0', borderColor: '#eee' }} />
                    
                    {/* Render Unified Metrics */}
                    <div>
                      <strong>Duration:</strong> {point.metrics?.parquet_duration_days} days 
                      {point.metrics?.csv_duration_days && ` (CSV: ${point.metrics.csv_duration_days} days)`}
                    </div>
                    <div>
                      <strong>Impact Profile:</strong> {point.metrics?.fatalities ?? 'No records'} Fatalities | {point.metrics?.displaced ?? '0'} Displaced
                    </div>
                    
                    {/* Render Warnings Box if discrepancies exist */}
                    {point.source_flags?.warnings && point.source_flags.warnings.length > 0 ? (
                      <div style={{
                        backgroundColor: '#fff3cd',
                        color: '#856404',
                        border: '1px solid #ffeeba',
                        padding: '6px',
                        borderRadius: '4px',
                        marginTop: '8px',
                        fontSize: '11px'
                      }}>
                        ⚠️ <strong>Dataset Conflict:</strong>
                        <ul style={{ margin: '4px 0 0 0', paddingLeft: '16px' }}>
                          {point.source_flags.warnings.map((warn: string, i: number) => (
                            <li key={i}>{warn}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {/* Fallback to original layout description fallback if needed */}
                    {!point.metrics && point.description && (
                      <>
                        <br />
                        <span>{point.description}</span>
                      </>
                    )}
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

            {/* NEW: Filter & Sort Controls */}
            <div className="control-panel">
              <input
                type="text"
                className="search-input"
                placeholder="Search by cause, city, state..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <select
                className="sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
              >
                <option value="none">No Sorting</option>
                <option value="severity">Sort by Severity</option>
                <option value="duration">Sort by Duration</option>
                <option value="area">Sort by Footprint Area</option>
              </select>
            </div>

            <ul className="point-list">
              {filteredAndSortedPoints.map((point: MapPoint) => {
                const isActive = selectedPoint?.id === point.id

                return (
                  <li key={point.id}>
                    <button
                      className={`point-button ${isActive ? 'active' : ''}`}
                      onClick={() => setSelectedPoint(point)}
                    >
                      <span className="point-name">{point.name}</span>
                      <span className="point-meta">
                        {point.city}, {point.state}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </aside>
      </main>
    </div>
  )
}