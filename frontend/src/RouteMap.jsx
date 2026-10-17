import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import Level from './Level.jsx'
import { clock } from './format.js'
import { LEVELS, slug } from './levels.js'

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const US = { center: [39, -97], zoom: 4 }

// Canvas paths need literal colors, so they are read from the stylesheet's variables.
function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
}

function span(a, b) {
  const c = Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180)
  return Math.hypot((b[0] - a[0]) * c, b[1] - a[1])
}

// Cuts the geometry at every checkpoint so each piece of road carries the level read at
// its start, the same rule the ranking and the strips use.
function pieces(route) {
  const coords = route.coordinates
  const along = [0]
  for (let i = 1; i < coords.length; i++) along.push(along[i - 1] + span(coords[i - 1], coords[i]))
  const scale = along[along.length - 1] / route.distance_miles
  const cps = route.checkpoints
  const out = []
  let j = 0
  for (let k = 0; k + 1 < cps.length; k++) {
    const latlngs = [[cps[k].lat, cps[k].lon]]
    while (j + 1 < coords.length && along[j + 1] < cps[k + 1].mile * scale) {
      j++
      latlngs.push([coords[j][1], coords[j][0]])
    }
    latlngs.push([cps[k + 1].lat, cps[k + 1].lon])
    out.push({ level: cps[k].level, latlngs })
  }
  return out
}

function label(route) {
  return route.recommended ? `${route.name}<br>Recommended` : route.name
}

function popup(cp) {
  const w = cp.weather
  const readings = `wind ${w.wind_mph ?? '–'} mph, rain ${w.rain_in ?? '–'} in/h, snow ${w.snow_in ?? '–'} in/h, ${w.temp_f ?? '–'} °F`
  return `<b>Mile ${cp.mile.toLocaleString('en-US')}</b>, ${clock(cp.eta)}<br>${cp.level || 'No data'}: ${readings}`
}

export default function RouteMap({ trip, selected, onSelect }) {
  const box = useRef(null)
  const map = useRef(null)
  const drawn = useRef(null)

  useEffect(() => {
    // Thin lines on canvas are a 1.5 px target without a tolerance; 8 px makes them tappable.
    map.current = L.map(box.current, { renderer: L.canvas({ tolerance: 8 }) }).setView(US.center, US.zoom)
    L.tileLayer(TILES, { maxZoom: 18, attribution: CREDIT }).addTo(map.current)
    drawn.current = L.layerGroup().addTo(map.current)
    return () => map.current.remove()
  }, [])

  useEffect(() => {
    if (!trip) return
    const points = trip.routes.flatMap((route) => route.coordinates.map(([lon, lat]) => [lat, lon]))
    map.current.fitBounds(L.latLngBounds(points), { padding: [24, 24] })
  }, [trip])

  useEffect(() => {
    drawn.current.clearLayers()
    if (!trip) return
    // The selected route is drawn last so it sits on top where routes share a road.
    const order = trip.routes.map((_, i) => i).filter((i) => i !== selected).concat(selected)
    for (const i of order) {
      const route = trip.routes[i]
      const active = i === selected
      const cut = pieces(route)
      // A white casing keeps every route's colors readable over the tiles; fading the
      // other routes with opacity would mix their colors with whatever lies under them.
      L.polyline(route.coordinates.map(([lon, lat]) => [lat, lon]), { color: '#fff', weight: active ? 10 : 6, interactive: false })
        .addTo(drawn.current)
      const lines = L.featureGroup(cut.map((piece) => L.polyline(piece.latlngs, { color: css(slug(piece.level)), weight: active ? 6 : 3 })))
      lines.on('click', () => onSelect(i)).addTo(drawn.current)
      if (!active) lines.on('mouseover', () => lines.setStyle({ weight: 5 })).on('mouseout', () => lines.setStyle({ weight: 3 }))
      // Routes share long stretches of road, so each label sits at a different point of its route.
      lines.getLayers()[Math.floor((cut.length * (i + 1)) / 4)].bindTooltip(label(route), {
        permanent: true,
        direction: 'top',
        className: route.recommended ? 'route-label good' : 'route-label',
      })
      if (!active) continue
      route.checkpoints.forEach((cp, k) => {
        const last = k === route.checkpoints.length - 1
        const end = k === 0 || last
        const marker = L.circleMarker([cp.lat, cp.lon], {
          radius: end ? 7 : 5,
          color: end ? css('ink') : '#fff',
          weight: 1.5,
          fillColor: css(slug(cp.level)),
          fillOpacity: 1,
        })
          .bindPopup(popup(cp))
          .addTo(drawn.current)
        if (end) {
          const place = (last ? trip.destination : trip.origin).label.split(',')[0]
          marker.bindTooltip(`${place}, ${last ? 'arrives' : 'leaves'} ${clock(cp.eta)}`, { permanent: true, direction: 'auto', offset: [10, 0] })
        }
      })
    }
  }, [trip, selected, onSelect])

  return (
    <>
      <div className="map" ref={box} />
      {trip && (
        <ul className="legend">
          {LEVELS.map((level) => (
            <li key={level}>
              <Level level={level} />
            </li>
          ))}
          <li>
            <i className="line thick" />
            Selected route; click a dot for its forecast
          </li>
          <li>
            <i className="line" />
            Other routes, click to select
          </li>
        </ul>
      )}
    </>
  )
}
