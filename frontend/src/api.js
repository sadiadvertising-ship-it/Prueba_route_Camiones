const API = import.meta.env.VITE_API_URL

export async function planTrip(trip) {
  const response = await fetch(`${API}/api/trips/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trip),
  })
  // A crashed or misconfigured server answers with an HTML page, not with JSON.
  if (!response.headers.get('Content-Type')?.includes('json')) {
    return { ok: false, body: { detail: `The planning service failed (HTTP ${response.status}).` } }
  }
  return { ok: response.ok, body: await response.json() }
}
