import { useMemo, useState } from 'react'
import {
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import type { MapPoint } from './types'
import { points } from './data/points'

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

  const center = useMemo<[number, number]>(() => [39.8283, -98.5795], [])

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

            {points.map((point) => (
              <Marker
                key={point.id}
                position={[point.lat, point.lng]}
                eventHandlers={{
                  click: () => setSelectedPoint(point),
                }}
              >
                <Popup>
                  <div className="popup">
                    <strong>{point.name}</strong>
                    <br />
                    {point.city}, {point.state}
                    {point.description ? (
                      <>
                        <br />
                        <span>{point.description}</span>
                      </>
                    ) : null}
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </section>

        <aside className="sidebar" aria-label="Point list">
          <div className="sidebar-card">
            <h2>Locations</h2>
            <p className="sidebar-text">
              Select a location to zoom the map.
            </p>

            <ul className="point-list">
              {points.map((point) => {
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