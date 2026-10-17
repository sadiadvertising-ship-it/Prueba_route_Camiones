import { LEVELS, slug } from './levels.js'
import { hours, miles } from './format.js'

function Strip({ checkpoints }) {
  const total = checkpoints[checkpoints.length - 1].mile
  return (
    <div className="strip" title="Risk along the route, from origin to destination">
      {checkpoints.slice(0, -1).map((cp, i) => (
        <i key={cp.mile} className={slug(cp.level)} style={{ width: `${((checkpoints[i + 1].mile - cp.mile) / total) * 100}%` }} />
      ))}
    </div>
  )
}

function timing(route, fastest) {
  const text = `${miles(route.distance_miles)}, ${hours(route.duration_seconds)}`
  const extra = route.duration_seconds - fastest
  return extra >= 60 ? `${text} (${hours(extra)} longer than the fastest)` : text
}

function describe(route) {
  const spans = LEVELS.filter((level) => route.miles[level] > 0)
  const risk = spans.length === 1 ? `${spans[0]} the whole way` : spans.map((level) => `${level} for ${miles(route.miles[level])}`).join(', ')
  return route.average_risk ? `${risk}. Average risk ${route.average_risk} of 4.` : `${risk}.`
}

// The backend ranks; this only names the first criterion that set the winner apart from the runner-up.
function reason(best, next) {
  if (!next) return ''
  if (next.no_travel) return ', the others hit No Travel'
  if (best.miles.Severe !== next.miles.Severe) return ', fewest Severe miles'
  if (best.miles.High !== next.miles.High) return ', fewest High miles'
  if (best.average_risk !== next.average_risk) return ', lowest average risk'
  return ', shortest time'
}

export default function RouteList({ routes, selected, onSelect }) {
  const fastest = Math.min(...routes.map((route) => route.duration_seconds))
  return (
    <ol className="routes">
      {routes.map((route, i) => (
        <li key={route.name}>
          <button type="button" className="route" aria-pressed={i === selected} onClick={() => onSelect(i)}>
            <span className="route-name">
              <strong>{route.name}</strong>
              {route.recommended && <em className="good">Recommended{reason(route, routes[1])}</em>}
              {route.no_travel && <em className="bad">Hits No Travel conditions</em>}
            </span>
            <span>{timing(route, fastest)}</span>
            <Strip checkpoints={route.checkpoints} />
            <small>{describe(route)}</small>
          </button>
        </li>
      ))}
    </ol>
  )
}
