import { afterEach, expect, it, vi } from 'vitest'
import { planTrip } from './api.js'

afterEach(() => vi.unstubAllGlobals())

it('posts the trip as JSON to the plan endpoint and hands back the body with its status', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ weight_lb: ['This field is required.'] }), { status: 400, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)

  const result = await planTrip({ origin: 'Dallas, TX', destination: 'Chicago, IL' })

  expect(result).toEqual({ ok: false, body: { weight_lb: ['This field is required.'] } })
  const [url, init] = fetch.mock.calls[0]
  expect(url.endsWith('/api/trips/plan/')).toBe(true)
  expect(init.method).toBe('POST')
  expect(JSON.parse(init.body)).toEqual({ origin: 'Dallas, TX', destination: 'Chicago, IL' })
})

it('turns a server error page into a message instead of choking on the HTML', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<h1>Server Error (500)</h1>', { status: 500, headers: { 'Content-Type': 'text/html' } })))

  expect(await planTrip({})).toEqual({ ok: false, body: { detail: 'The planning service failed (HTTP 500).' } })
})
