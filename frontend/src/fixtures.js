export const DEPARTURE = '2026-10-20T12:00:00Z'

export function iso(hoursAfterDeparture) {
  return new Date(Date.parse(DEPARTURE) + hoursAfterDeparture * 36e5).toISOString().replace('.000Z', 'Z')
}

export function checkpoint(mile, level, hour, extra = {}) {
  const reading = (n) => (level === null ? null : n)
  return {
    mile,
    lat: 30,
    lon: -100 + mile / 100,
    eta: iso(hour),
    level,
    weather: { time: iso(Math.round(hour)), wind_mph: reading(10), rain_in: reading(0), snow_in: reading(0), temp_f: reading(58), weather_code: reading(1) },
    hourly: Array(49).fill(level),
    ...extra,
  }
}

function route(id, name, miles, seconds, levels, summary) {
  const step = miles / (levels.length - 1)
  const checkpoints = levels.map((level, i) => checkpoint(Math.round(step * i), level, (seconds / 3600) * (i / (levels.length - 1))))
  return {
    id,
    name,
    distance_miles: miles,
    duration_seconds: seconds,
    coordinates: checkpoints.map((cp) => [cp.lon, cp.lat]),
    checkpoints,
    miles: { Low: 0, Moderate: 0, High: 0, Severe: 0, 'No Travel': 0, 'No data': 0, ...summary.miles },
    average_risk: summary.average_risk,
    no_travel: summary.no_travel ?? false,
    recommended: summary.recommended ?? false,
  }
}

// Three routes with a storm on the fastest one, ranked the way the backend would rank them.
export function storm() {
  return {
    origin: { label: 'Dallas, TX, USA', lat: 32.78, lon: -96.8 },
    destination: { label: 'Chicago, IL, USA', lat: 41.88, lon: -87.63 },
    departure: DEPARTURE,
    weight_lb: 35000,
    interval_miles: 25,
    hours: Array.from({ length: 49 }, (_, i) => iso(i)),
    recommended: 'Via US 278',
    routes: [
      route(2, 'Via US 278', 100, 7200, ['Low', 'Moderate', 'Low', 'Low', 'Low'], { miles: { Low: 75, Moderate: 25 }, average_risk: 0.2, recommended: true }),
      route(1, 'Via I 55', 95, 6600, ['Low', 'High', 'Low', 'Low', 'Low'], { miles: { Low: 71, High: 24 }, average_risk: 0.4 }),
      route(0, 'Fastest', 90, 6000, ['Low', 'No Travel', 'Severe', 'Low', 'Low'], { miles: { Low: 40, Severe: 22, 'No Travel': 23 }, average_risk: 1.4, no_travel: true }),
    ],
  }
}
