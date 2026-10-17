import { describe, expect, it } from 'vitest'
import { pieces, truckAt } from './geometry.js'
import { checkpoint, iso } from './fixtures.js'

// A straight road along latitude 30 with a vertex every tenth of a degree, 10 miles apart.
const coords = Array.from({ length: 11 }, (_, i) => [-100 + i / 10, 30])

function straight(miles) {
  return {
    distance_miles: 100,
    coordinates: coords,
    checkpoints: miles.map((mile) => checkpoint(mile, 'Low', mile / 50)),
  }
}

describe('pieces', () => {
  it('cuts the road at every checkpoint and keeps every vertex once', () => {
    const cut = pieces(straight([0, 25, 50, 75, 100]))

    expect(cut.map((piece) => piece.latlngs[0][1])).toEqual([-100, -99.75, -99.5, -99.25])
    expect(cut.map((piece) => piece.latlngs.at(-1)[1])).toEqual([-99.75, -99.5, -99.25, -99])
    const inner = cut.flatMap((piece) => piece.latlngs.slice(1, -1).map((p) => p[1]))
    expect(inner).toEqual(coords.slice(1, -1).map((c) => c[0]))
  })

  it('gives each piece the level read at its start', () => {
    const route = straight([0, 50, 100])
    route.checkpoints[0].level = 'Severe'
    route.checkpoints[1].level = 'Low'
    route.checkpoints[2].level = 'High'

    expect(pieces(route).map((piece) => piece.level)).toEqual(['Severe', 'Low'])
  })

  it('makes one piece out of a route with only its two ends', () => {
    const [only] = pieces(straight([0, 100]))

    expect(only.latlngs).toHaveLength(11)
    expect(only.latlngs[0]).toEqual([30, -100])
    expect(only.latlngs.at(-1)).toEqual([30, -99])
  })
})

describe('truckAt', () => {
  const route = straight([0, 50, 100])

  it('waits at the origin before departure and stays at the destination after arrival', () => {
    expect(truckAt(route, iso(-3))).toEqual({ lat: 30, lon: -100, mile: 0 })
    expect(truckAt(route, iso(5))).toEqual({ lat: 30, lon: -99, mile: 100 })
  })

  it('sits on a checkpoint at its ETA and halfway between two in between', () => {
    expect(truckAt(route, iso(1))).toEqual({ lat: 30, lon: -99.5, mile: 50 })
    expect(truckAt(route, iso(1.5))).toEqual({ lat: 30, lon: -99.25, mile: 75 })
  })
})
