import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import Level from './Level.jsx'
import { clock } from './format.js'
import { LEVELS, slug } from './levels.js'

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const US = { center: [39, -97], zoom: 4 }
const METERS_PER_MILE = 1609.34

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

// Between checkpoints the truck is placed on the straight line between them; the roads
// bend less than the checkpoint spacing at the zoom levels where the whole trip is visible.
function truckAt(route, when) {
  const cps = route.checkpoints
  const t = Date.parse(when)
  for (let k = 0; k + 1 < cps.length; k++) {
    const a = Date.parse(cps[k].eta)
    const b = Date.parse(cps[k + 1].eta)
    if (t < a) break
    if (t <= b) {
      const f = (t - a) / (b - a || 1)
      const mix = (key) => cps[k][key] + (cps[k + 1][key] - cps[k][key]) * f
      return { lat: mix('lat'), lon: mix('lon'), mile: mix('mile') }
    }
  }
  const cp = t < Date.parse(cps[0].eta) ? cps[0] : cps[cps.length - 1]
  return { lat: cp.lat, lon: cp.lon, mile: cp.mile }
}

function Slider({ trip, route, hour, onChange }) {
  const [playing, setPlaying] = useState(false)
  const last = trip.hours.length - 1
  const running = playing && hour < last
  const when = trip.hours[hour]
  const arrival = route.checkpoints[route.checkpoints.length - 1].eta
  const arrived = Date.parse(when) >= Date.parse(arrival)

  useEffect(() => {
    if (!running) return
    const id = setTimeout(() => onChange(hour + 1), 450)
    return () => clearTimeout(id)
  }, [running, hour, onChange])

  function toggle() {
    if (running) {
      setPlaying(false)
      return
    }
    if (hour >= last) onChange(0)
    setPlaying(true)
  }

  return (
    <div className="slider">
      <div className="slider-head">
        <span>
          Corridor forecast for <b>{clock(when)}</b> (+{hour} h)
          {arrived ? `, the truck arrived at ${clock(arrival)}` : `, truck at mile ${Math.round(truckAt(route, when).mile)}`}
        </span>
        <button type="button" onClick={toggle}>
          {running ? 'Pause' : 'Play'}
        </button>
      </div>
      <label className="track">
        <input
          type="range"
          min="0"
          max={last}
          value={hour}
          aria-valuetext={clock(when)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <i
          className="arrival"
          title={`Arrival, ${clock(arrival)}`}
          style={{ left: `${Math.min(100, ((Date.parse(arrival) - Date.parse(trip.hours[0])) / 36e5 / last) * 100)}%` }}
        />
      </label>
      <span className="ticks">
        <i>{clock(trip.hours[0])}</i>
        <i>{clock(trip.hours[Math.floor(last / 2)])}</i>
        <i>{clock(trip.hours[last])}</i>
      </span>
      <small>
        The haze shows every checkpoint of every route at this hour. The route colors keep showing what the truck meets
        at its own arrival time.
      </small>
    </div>
  )
}

function popup(cp) {
  const w = cp.weather
  const readings = `wind ${w.wind_mph ?? '–'} mph, rain ${w.rain_in ?? '–'} in/h, snow ${w.snow_in ?? '–'} in/h, ${w.temp_f ?? '–'} °F`
  return `<b>Mile ${cp.mile.toLocaleString('en-US')}</b>, ${clock(cp.eta)}<br>${cp.level || 'No data'}: ${readings}`
}

export default function RouteMap({ trip, selected, hour, onSelect, onHour }) {
  const box = useRef(null)
  const map = useRef(null)
  const drawn = useRef(null)
  const heat = useRef(null)
  const canvas = useRef(null)

  useEffect(() => {
    // Thin lines on canvas are a 1.5 px target without a tolerance; 8 px makes them tappable.
    map.current = L.map(box.current, { renderer: L.canvas({ tolerance: 8 }) }).setView(US.center, US.zoom)
    L.tileLayer(TILES, { maxZoom: 18, attribution: CREDIT }).addTo(map.current)
    // The heatmap sits in its own pane under the routes, so the roads stay readable through it.
    // Leaflet never drops a renderer once added, so the pane gets one for the life of the map.
    map.current.createPane('heat').style.zIndex = 350
    canvas.current = L.canvas({ pane: 'heat' })
    heat.current = L.layerGroup().addTo(map.current)
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

  useEffect(() => {
    heat.current.clearLayers()
    if (!trip) return
    const tint = Object.fromEntries(LEVELS.map((level) => [level, css(slug(level))]))
    // Discs sized in miles tile the corridor at every zoom, where pixel sizes would gap or pile up.
    const radius = trip.interval_miles * METERS_PER_MILE * 0.55
    for (const route of trip.routes) {
      for (const cp of route.checkpoints) {
        const level = cp.hourly[hour] ?? 'No data'
        L.circle([cp.lat, cp.lon], {
          renderer: canvas.current,
          radius,
          stroke: false,
          fillColor: tint[level],
          // Calm weather should not shout: Low stays a faint tint and the real risks stand out.
          fillOpacity: level === 'Low' ? 0.12 : 0.4,
          interactive: false,
        }).addTo(heat.current)
      }
    }
    const truck = truckAt(trip.routes[selected], trip.hours[hour])
    // A ring, so the checkpoint under the truck keeps its color and its click.
    L.circleMarker([truck.lat, truck.lon], { radius: 11, color: css('ink'), weight: 3, fill: false, interactive: false }).addTo(heat.current)
  }, [trip, selected, hour])

  return (
    <>
      <div className="map" ref={box} />
      {trip && <Slider trip={trip} route={trip.routes[selected]} hour={hour} onChange={onHour} />}
      {trip && (
        <ul className="legend">
          {LEVELS.map((level) => (
            <li key={level}>
              <Level level={level} />
            </li>
          ))}
          <li>
            <i className="line thick" />
            Selected route; click a checkpoint for its forecast
          </li>
          <li>
            <i className="line" />
            Other routes, click to select
          </li>
          <li>
            <i className="heat" />
            Haze: the corridor at the slider's hour, same colors
          </li>
          <li>
            <i className="truck" />
            Ring: the truck at that hour
          </li>
        </ul>
      )}
    </>
  )
}
