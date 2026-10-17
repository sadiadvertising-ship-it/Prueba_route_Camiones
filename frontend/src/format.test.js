import { describe, expect, it } from 'vitest'
import { clock, day, hours, miles, pounds } from './format.js'

describe('hours', () => {
  it('writes hours and minutes like "21 h 40 min", minutes alone under an hour', () => {
    expect(hours(0)).toBe('0 min')
    expect(hours(45 * 60)).toBe('45 min')
    expect(hours(3600)).toBe('1 h')
    expect(hours(77976)).toBe('21 h 40 min')
  })

  it('rounds to the minute without ever showing 60 min', () => {
    expect(hours(3599.6)).toBe('1 h')
    expect(hours(7199)).toBe('2 h')
    expect(hours(89)).toBe('1 min')
  })
})

it('writes miles and pounds with US separators', () => {
  expect(miles(969.7)).toBe('970 mi')
  expect(miles(1028.7)).toBe('1,029 mi')
  expect(pounds(35000)).toBe('35,000 lb')
})

it('shows times in US style with the weekday, whatever the machine locale', () => {
  expect(clock('2026-10-16T22:18:16Z')).toBe('Fri 5:18 PM')
  expect(day('2026-10-16T21:00:00Z')).toBe('Fri, Oct 16, 4:00 PM CDT')
})
