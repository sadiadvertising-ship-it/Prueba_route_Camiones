const API = import.meta.env.VITE_API_URL

async function post(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  // A crashed or misconfigured server answers with an HTML page, not with JSON.
  if (!response.headers.get('Content-Type')?.includes('json')) {
    return { ok: false, body: { detail: `The planning service failed (HTTP ${response.status}).` } }
  }
  return { ok: response.ok, body: await response.json() }
}

async function forecast(url) {
  let response
  try {
    response = await fetch(url)
  } catch {
    throw new Error('Open-Meteo could not be reached. Try again in a minute.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(`Open-Meteo: ${body?.reason || `HTTP ${response.status}`}`)
  return body
}

export async function planTrip(trip) {
  const routes = await post('/api/trips/plan/', trip)
  if (!routes.ok) return routes
  const { forecast_urls, ticket, ...plan } = routes.body
  // Open-Meteo's free tier is limited per IP and cloud servers share theirs, so the
  // forecast is fetched from here, on the visitor's own quota, and the server scores it.
  let forecasts
  try {
    forecasts = await Promise.all(forecast_urls.map(forecast))
  } catch (error) {
    return { ok: false, body: { detail: error.message } }
  }
  const scored = await post('/api/trips/assess/', { ticket, forecasts })
  if (!scored.ok) return scored
  const geometry = Object.fromEntries(plan.routes.map((route) => [route.id, route.coordinates]))
  return {
    ok: true,
    body: {
      ...plan,
      recommended: scored.body.recommended,
      routes: scored.body.routes.map((route) => ({ ...route, coordinates: geometry[route.id] })),
    },
  }
}
