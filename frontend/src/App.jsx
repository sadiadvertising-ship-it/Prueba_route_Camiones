import { useEffect, useRef, useState } from 'react'
import { planTrip } from './api.js'
import Checkpoints from './Checkpoints.jsx'
import RouteList from './RouteList.jsx'
import RouteMap from './RouteMap.jsx'
import TripForm from './TripForm.jsx'
import { day, pounds } from './format.js'

// The brief's load rules, spelled out so the dispatcher sees which one applies to this truck.
function loadRule(lb) {
  if (lb > 40000) return 'With this load, wind of 35 mph or more counts as Severe and 45 mph or more means No Travel.'
  if (lb > 30000) return 'With this load, wind of 45 mph or more means No Travel.'
  return 'This load is light enough for the standard wind limits.'
}

function Status({ trip, busy }) {
  if (busy) {
    return <p className="status">Finding truck routes and checking the hourly forecast along each one. This takes a few seconds.</p>
  }
  if (!trip) {
    return (
      <p className="status">
        Type where the truck leaves from and where it is going, then press Plan the trip. You get up to three routes, the
        forecast at each checkpoint for the hour the truck gets there, and which route to take.
      </p>
    )
  }
  return (
    <>
      <p className="summary">
        {trip.origin.label} to {trip.destination.label}, leaving {day(trip.departure)} with a {pounds(trip.weight_lb)} load.
        Weather checked every {trip.interval_miles} miles along each route. {loadRule(trip.weight_lb)}
      </p>
      {!trip.recommended && (
        <p className="problem">No route is advisable: every option runs into No Travel conditions. Try a later departure.</p>
      )}
    </>
  )
}

export default function App() {
  const [trip, setTrip] = useState(null)
  const [selected, setSelected] = useState(0)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const main = useRef(null)

  useEffect(() => {
    // On a phone the form and the route list push the result below the fold.
    if (trip && matchMedia('(max-width: 860px)').matches) main.current.scrollIntoView({ behavior: 'smooth' })
  }, [trip, selected])

  async function plan(values) {
    setBusy(true)
    setErrors({})
    try {
      const { ok, body } = await planTrip(values)
      if (ok) {
        setTrip(body)
        setSelected(0)
      } else {
        setErrors(body)
      }
    } catch {
      setErrors({ detail: 'The planning service could not be reached.' })
    }
    setBusy(false)
  }

  return (
    <div className="app">
      <aside>
        <h1>Truck Route Planner</h1>
        <TripForm onPlan={plan} busy={busy} errors={errors} />
        {trip && (
          <div className={busy ? 'stale' : undefined}>
            <RouteList routes={trip.routes} selected={selected} onSelect={setSelected} />
            <p className="note">
              Routes that hit No Travel conditions go last. The rest are ranked by fewest Severe miles, then fewest High
              miles, lowest average risk and shortest time.
            </p>
          </div>
        )}
      </aside>
      <main ref={main}>
        <Status trip={trip} busy={busy} />
        <div className={busy ? 'stale' : undefined}>
          <RouteMap trip={trip} selected={selected} onSelect={setSelected} />
          {trip && <Checkpoints route={trip.routes[selected]} />}
        </div>
      </main>
    </div>
  )
}
