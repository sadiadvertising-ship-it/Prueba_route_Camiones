// US trips, US conventions: "1,234 mi" and 12-hour clocks whatever the browser's locale.
// Times stay in the browser's zone, the same zone the departure was typed in.
export function hours(seconds) {
  const total = Math.round(seconds / 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

export function miles(n) {
  return `${Math.round(n).toLocaleString('en-US')} mi`
}

export function pounds(n) {
  return `${n.toLocaleString('en-US')} lb`
}

export function clock(iso) {
  return new Date(iso).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

export function day(iso) {
  return new Date(iso).toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}
