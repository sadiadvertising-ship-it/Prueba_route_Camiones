import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import App from './App.jsx'
import { planTrip } from './api.js'
import { storm } from './fixtures.js'

vi.mock('./api.js', () => ({ planTrip: vi.fn() }))
// Leaflet needs a real canvas; the map has its own tests through its geometry.
vi.mock('./RouteMap.jsx', () => ({ default: () => <div data-testid="map" /> }))

function plan(container) {
  for (const [name, value] of Object.entries({ origin: 'Dallas, TX', destination: 'Chicago, IL', weight_lb: '35000' })) {
    fireEvent.change(container.querySelector(`[name=${name}]`), { target: { value } })
  }
  fireEvent.submit(container.querySelector('form'))
}

it('tells a new user what to do and what they will get', () => {
  render(<App />)

  expect(screen.getByText(/Type where the truck leaves from/)).toBeTruthy()
  expect(screen.queryByRole('table')).toBeNull()
})

it('plans a trip and shows the ranked routes, the summary and the checkpoints', async () => {
  planTrip.mockResolvedValue({ ok: true, body: storm() })
  const { container } = render(<App />)

  plan(container)
  expect(screen.getByText(/Finding truck routes/)).toBeTruthy()
  expect(planTrip).toHaveBeenCalledWith(expect.objectContaining({ origin: 'Dallas, TX', weight_lb: 35000 }))

  await screen.findByText(/Dallas, TX, USA to Chicago, IL, USA/)
  expect(screen.getByText(/With this load, wind of 45 mph or more means No Travel/)).toBeTruthy()
  expect(screen.getByText('Recommended, fewest High miles')).toBeTruthy()
  expect(screen.getByText(/Routes that hit No Travel conditions go last/)).toBeTruthy()
  expect(screen.getByText(/^Via US 278: forecast at each checkpoint/)).toBeTruthy()
  expect(screen.getAllByRole('row')).toHaveLength(6)
})

it('switches the table to the route the user picks', async () => {
  planTrip.mockResolvedValue({ ok: true, body: storm() })
  const { container } = render(<App />)

  plan(container)
  await screen.findByText(/^Via US 278: forecast/)
  fireEvent.click(screen.getByText('Fastest').closest('button'))

  expect(screen.getByText(/^Fastest: forecast/)).toBeTruthy()
})

it('shows a field error without losing the last plan, and clears it on the next success', async () => {
  planTrip.mockResolvedValueOnce({ ok: true, body: storm() })
  const { container } = render(<App />)
  plan(container)
  await screen.findByRole('table')

  planTrip.mockResolvedValueOnce({ ok: false, body: { destination: ["Could not find a place called 'Chicago, IL'"] } })
  plan(container)
  await screen.findByText("Could not find a place called 'Chicago, IL'")
  expect(container.querySelector('.field.invalid [name=destination]')).toBeTruthy()
  expect(screen.getByRole('table')).toBeTruthy()

  planTrip.mockResolvedValueOnce({ ok: true, body: storm() })
  plan(container)
  await screen.findByRole('table')
  expect(screen.queryByText("Could not find a place called 'Chicago, IL'")).toBeNull()
})

it('reports a service outage in the words the backend chose', async () => {
  planTrip.mockResolvedValue({ ok: false, body: { detail: 'Open-Meteo did not answer. Try again in a minute.' } })
  const { container } = render(<App />)

  plan(container)

  expect(await screen.findByText('Open-Meteo did not answer. Try again in a minute.')).toBeTruthy()
})

it('says so when the backend cannot be reached at all', async () => {
  planTrip.mockRejectedValue(new TypeError('Failed to fetch'))
  const { container } = render(<App />)

  plan(container)

  expect(await screen.findByText('The planning service could not be reached.')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Plan the trip' }).disabled).toBe(false)
})

it('warns when no route is advisable', async () => {
  const trip = storm()
  trip.recommended = null
  trip.routes.forEach((route) => {
    route.recommended = false
    route.no_travel = true
  })
  planTrip.mockResolvedValue({ ok: true, body: trip })
  const { container } = render(<App />)

  plan(container)

  expect(await screen.findByText(/No route is advisable/)).toBeTruthy()
  expect(screen.queryByText(/Recommended/)).toBeNull()
})
