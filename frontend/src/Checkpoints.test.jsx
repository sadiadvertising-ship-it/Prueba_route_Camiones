import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import Checkpoints from './Checkpoints.jsx'
import { checkpoint, iso } from './fixtures.js'

const route = {
  name: 'Fastest',
  checkpoints: [checkpoint(0, 'Low', 0), checkpoint(25, null, 0.5), checkpoint(50, 'Severe', 1, { weather: { time: iso(1), wind_mph: 47.3, rain_in: 0.25, snow_in: 0, temp_f: 41, weather_code: 61 } })],
}

it('lists every checkpoint with its ETA, risk and readings', () => {
  render(<Checkpoints route={route} now={iso(-1)} />)

  expect(screen.getByText('Fastest: forecast at each checkpoint for the hour the truck gets there.')).toBeTruthy()
  const rows = screen.getAllByRole('row').slice(1)
  expect(rows.map((row) => [...row.cells].map((td) => td.textContent))).toEqual([
    ['0', 'Tue 7:00 AM', 'Low', '10 mph', '0 in/h', '0 in/h', '58 °F'],
    ['25', 'Tue 7:30 AM', 'No data', '–', '–', '–', '–'],
    ['50', 'Tue 8:00 AM', 'Severe', '47.3 mph', '0.25 in/h', '0 in/h', '41 °F'],
  ])
})

it('mutes the readings that are zero', () => {
  const { container } = render(<Checkpoints route={route} now={iso(-1)} />)

  const zeros = [...container.querySelectorAll('td.zero')].map((td) => td.textContent)
  expect(zeros).toEqual(['0 in/h', '0 in/h', '0 in/h'])
})

it('highlights the row the truck is on at the slider hour', () => {
  const { container } = render(<Checkpoints route={route} now={iso(0.75)} />)

  expect([...container.querySelectorAll('tr.now td')][0].textContent).toBe('25')
})
