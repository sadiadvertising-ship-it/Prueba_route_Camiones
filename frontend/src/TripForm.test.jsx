import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import TripForm from './TripForm.jsx'

function fill(container, values) {
  for (const [name, value] of Object.entries(values)) {
    fireEvent.change(container.querySelector(`[name=${name}]`), { target: { value } })
  }
}

afterEach(() => vi.useRealTimers())

it('starts at the next full hour, in local time', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-20T11:20:00Z'))
  const { container } = render(<TripForm onPlan={() => {}} busy={false} errors={{}} />)

  expect(container.querySelector('[name=departure]').value).toBe('2026-10-20T07:00')
})

it('sends the trip with the departure as an instant and no interval unless chosen', () => {
  const onPlan = vi.fn()
  const { container } = render(<TripForm onPlan={onPlan} busy={false} errors={{}} />)

  fill(container, { origin: 'Dallas, TX', destination: 'Chicago, IL', departure: '2026-10-20T12:00', weight_lb: '35000' })
  fireEvent.submit(container.querySelector('form'))
  expect(onPlan).toHaveBeenCalledWith({
    origin: 'Dallas, TX',
    destination: 'Chicago, IL',
    departure: '2026-10-20T17:00:00.000Z',
    weight_lb: 35000,
    interval: null,
  })

  fill(container, { interval: '25' })
  fireEvent.submit(container.querySelector('form'))
  expect(onPlan).toHaveBeenLastCalledWith(expect.objectContaining({ interval: 25 }))
})

it('shows each error under its field and the service error under the button', () => {
  const errors = { destination: ["Could not find a place called 'Nowhere'"], weight_lb: ['Ensure this value is greater than or equal to 1.'], detail: 'Open-Meteo did not answer. Try again in a minute.' }
  const { container } = render(<TripForm onPlan={() => {}} busy={false} errors={errors} />)

  expect(container.querySelector('[name=destination]').closest('.field').textContent).toContain("Could not find a place called 'Nowhere'")
  expect(container.querySelectorAll('.field.invalid')).toHaveLength(2)
  expect(screen.getByText('Open-Meteo did not answer. Try again in a minute.')).toBeTruthy()
})

it('holds the button while a plan is on its way', () => {
  render(<TripForm onPlan={() => {}} busy={true} errors={{}} />)

  const button = screen.getByRole('button')
  expect(button.disabled).toBe(true)
  expect(button.textContent).toBe('Planning…')
})
