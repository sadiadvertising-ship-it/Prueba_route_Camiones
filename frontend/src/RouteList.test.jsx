import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import RouteList from './RouteList.jsx'
import { storm } from './fixtures.js'

function names() {
  return screen.getAllByRole('button').map((button) => button.querySelector('strong').textContent)
}

it('lists the routes in the order they came, naming why the first one won', () => {
  render(<RouteList routes={storm().routes} selected={0} onSelect={() => {}} />)

  expect(names()).toEqual(['Via US 278', 'Via I 55', 'Fastest'])
  expect(screen.getByText('Recommended, fewest High miles')).toBeTruthy()
  expect(screen.getByText('Hits No Travel conditions')).toBeTruthy()
})

it('says the time cost against the fastest route and the miles per level in words', () => {
  render(<RouteList routes={storm().routes} selected={0} onSelect={() => {}} />)

  expect(screen.getByText('100 mi, 2 h (20 min longer than the fastest)')).toBeTruthy()
  expect(screen.getByText('90 mi, 1 h 40 min')).toBeTruthy()
  expect(screen.getByText('Moderate for 25 mi, Low for 75 mi. Average risk 0.2 of 4.')).toBeTruthy()
  expect(screen.getByText('No Travel for 23 mi, Severe for 22 mi, Low for 40 mi. Average risk 1.4 of 4.')).toBeTruthy()
})

it('names the first criterion that separates the winner from the runner-up', () => {
  const { routes } = storm()
  const { unmount } = render(<RouteList routes={[routes[0], routes[2]]} selected={0} onSelect={() => {}} />)
  expect(screen.getByText('Recommended, the others hit No Travel')).toBeTruthy()
  unmount()

  routes[1].miles = { ...routes[1].miles, Severe: 24, High: 24 }
  const second = render(<RouteList routes={routes} selected={0} onSelect={() => {}} />)
  expect(screen.getByText('Recommended, fewest Severe miles')).toBeTruthy()
  second.unmount()

  routes[1].miles = { ...routes[1].miles, Severe: 0, High: 0, Low: 95 }
  render(<RouteList routes={routes} selected={0} onSelect={() => {}} />)
  expect(screen.getByText('Recommended, lowest average risk')).toBeTruthy()
})

it('keeps a calm route short', () => {
  const [route] = storm().routes
  route.miles = { ...route.miles, Moderate: 0, Low: 100 }
  route.average_risk = 0
  render(<RouteList routes={[route]} selected={0} onSelect={() => {}} />)

  expect(screen.getByText('Low the whole way.')).toBeTruthy()
})

it('marks the selected route and reports a click on another one', () => {
  const onSelect = vi.fn()
  render(<RouteList routes={storm().routes} selected={0} onSelect={onSelect} />)

  const buttons = screen.getAllByRole('button')
  expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false'])
  fireEvent.click(buttons[2])
  expect(onSelect).toHaveBeenCalledWith(2)
})
