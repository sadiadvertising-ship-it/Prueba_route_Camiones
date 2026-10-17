function span(a, b) {
  const c = Math.cos(((a[1] + b[1]) / 2) * Math.PI / 180)
  return Math.hypot((b[0] - a[0]) * c, b[1] - a[1])
}

// Cuts the geometry at every checkpoint so each piece of road carries the level read at
// its start, the same rule the ranking and the strips use.
export function pieces(route) {
  const coords = route.coordinates
  const along = [0]
  for (let i = 1; i < coords.length; i++) along.push(along[i - 1] + span(coords[i - 1], coords[i]))
  const scale = along[along.length - 1] / route.distance_miles
  const cps = route.checkpoints
  const out = []
  let j = 0
  for (let k = 0; k + 1 < cps.length; k++) {
    const latlngs = [[cps[k].lat, cps[k].lon]]
    while (j + 1 < coords.length && along[j + 1] < cps[k + 1].mile * scale) {
      j++
      latlngs.push([coords[j][1], coords[j][0]])
    }
    latlngs.push([cps[k + 1].lat, cps[k + 1].lon])
    out.push({ level: cps[k].level, latlngs })
  }
  return out
}

// Between checkpoints the truck is placed on the straight line between them; the roads
// bend less than the checkpoint spacing at the zoom levels where the whole trip is visible.
export function truckAt(route, when) {
  const cps = route.checkpoints
  const t = Date.parse(when)
  for (let k = 0; k + 1 < cps.length; k++) {
    const a = Date.parse(cps[k].eta)
    const b = Date.parse(cps[k + 1].eta)
    if (t < a) break
    if (t <= b) {
      const f = (t - a) / (b - a || 1)
      const mix = (key) => cps[k][key] + (cps[k + 1][key] - cps[k][key]) * f
      return { lat: mix('lat'), lon: mix('lon'), mile: mix('mile') }
    }
  }
  const cp = t < Date.parse(cps[0].eta) ? cps[0] : cps[cps.length - 1]
  return { lat: cp.lat, lon: cp.lon, mile: cp.mile }
}
