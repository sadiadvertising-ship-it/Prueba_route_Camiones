/* global process */
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// The tests pin times in one US zone, so they pass on every machine and a value sent as
// wall time instead of an instant cannot slip through unnoticed, as it would in UTC.
process.env.TZ = 'America/Chicago'
// jsdom has no media queries; the app only asks whether the screen is narrow.
window.matchMedia = () => ({ matches: false })
afterEach(cleanup)
