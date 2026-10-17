import { afterEach, expect, it, vi } from 'vitest'
import { planTrip } from './api.js'

const OPEN_METEO = 'https://api.open-meteo.com/v1/forecast?latitude=32.7'

afterEach(() => vi.unstubAllGlobals())

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

// Answers each request by its URL, the way the three services would.
function services(answers) {
  const fetch = vi.fn(async (url) => {
    const key = Object.keys(answers).find((path) => url.endsWith(path) || url.startsWith(path))
    const answer = answers[key]
    if (answer instanceof Error) throw answer
    return answer
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

const routes = {
  hours: ['2026-10-20T12:00:00Z'],
  routes: [
    { id: 0, name: 'Fastest', coordinates: [[-96.8, 32.7]], checkpoints: [] },
    { id: 1, name: 'Via I 55', coordinates: [[-90.1, 35.1]], checkpoints: [] },
  ],
  forecast_urls: [OPEN_METEO],
  ticket: 'signed',
}
const scored = {
  recommended: 'Via I 55',
  routes: [
    { id: 1, name: 'Via I 55', recommended: true },
    { id: 0, name: 'Fastest', recommended: false },
  ],
}

it('plans the routes, fetches their forecast from the browser and returns the ranked plan with its geometry', async () => {
  const fetch = services({ '/api/trips/plan/': json(routes), [OPEN_METEO]: json([{ hourly: {} }]), '/api/trips/assess/': json(scored) })

  const result = await planTrip({ origin: 'Dallas, TX', destination: 'Chicago, IL' })

  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    expect.stringMatching(/\/api\/trips\/plan\/$/),
    OPEN_METEO,
    expect.stringMatching(/\/api\/trips\/assess\/$/),
  ])
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ origin: 'Dallas, TX', destination: 'Chicago, IL' })
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ ticket: 'signed', forecasts: [[{ hourly: {} }]] })
  expect(result).toEqual({
    ok: true,
    body: {
      hours: ['2026-10-20T12:00:00Z'],
      recommended: 'Via I 55',
      routes: [
        { id: 1, name: 'Via I 55', recommended: true, coordinates: [[-90.1, 35.1]] },
        { id: 0, name: 'Fastest', recommended: false, coordinates: [[-96.8, 32.7]] },
      ],
    },
  })
})

it('stops at the first call when the server rejects the trip', async () => {
  const fetch = services({ '/api/trips/plan/': json({ weight_lb: ['This field is required.'] }, 400) })

  expect(await planTrip({})).toEqual({ ok: false, body: { weight_lb: ['This field is required.'] } })
  expect(fetch).toHaveBeenCalledTimes(1)
})

it("reports Open-Meteo's own reason when it refuses the forecast", async () => {
  const fetch = services({
    '/api/trips/plan/': json(routes),
    [OPEN_METEO]: json({ error: true, reason: 'Daily API request limit exceeded. Please try again tomorrow.' }, 429),
  })

  expect(await planTrip({})).toEqual({
    ok: false,
    body: { detail: 'Open-Meteo: Daily API request limit exceeded. Please try again tomorrow.' },
  })
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('says so when Open-Meteo cannot be reached', async () => {
  services({ '/api/trips/plan/': json(routes), [OPEN_METEO]: new TypeError('Failed to fetch') })

  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'Open-Meteo could not be reached. Try again in a minute.' } })
})

it('passes on why the server refused the forecast, in a message the form can show', async () => {
  services({
    '/api/trips/plan/': json(routes),
    [OPEN_METEO]: json([]),
    '/api/trips/assess/': json({ detail: 'This plan has expired. Plan the trip again.' }, 400),
  })
  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'This plan has expired. Plan the trip again.' } })

  services({
    '/api/trips/plan/': json(routes),
    [OPEN_METEO]: json([]),
    '/api/trips/assess/': json({ forecasts: ['Expected forecasts for 3 checkpoints, got 0.'] }, 400),
  })
  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'The forecast could not be checked. Plan the trip again.' } })
})

it('refuses an Open-Meteo answer that is not JSON', async () => {
  services({ '/api/trips/plan/': json(routes), [OPEN_METEO]: new Response('<html>maintenance</html>', { status: 200 }) })

  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'Open-Meteo sent a forecast that could not be read.' } })
})

it('turns a server error page into a message instead of choking on the HTML', async () => {
  services({ '/api/trips/plan/': new Response('<h1>Server Error (500)</h1>', { status: 500, headers: { 'Content-Type': 'text/html' } }) })

  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'The planning service failed (HTTP 500).' } })
})
