import Level from './Level.jsx'
import { clock } from './format.js'

function Reading({ value, unit }) {
  if (value == null) return <td>–</td>
  return <td className={value ? undefined : 'zero'}>{`${value} ${unit}`}</td>
}

export default function Checkpoints({ route, now }) {
  const cps = route.checkpoints
  const t = Date.parse(now)
  return (
    <>
      <p className="caption">{route.name}: forecast at each checkpoint for the hour the truck gets there.</p>
      <div className="scroll">
        <table className="checkpoints">
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th>Wind</th>
              <th>Rain</th>
              <th>Snow</th>
              <th>Temp</th>
            </tr>
          </thead>
          <tbody>
            {cps.map((cp, i) => (
              <tr key={i} className={Date.parse(cp.eta) <= t && (i === cps.length - 1 || t < Date.parse(cps[i + 1].eta)) ? 'now' : undefined}>
                <td>{cp.mile.toLocaleString('en-US')}</td>
                <td>{clock(cp.eta)}</td>
                <td>
                  <Level level={cp.level} />
                </td>
                <Reading value={cp.weather.wind_mph} unit="mph" />
                <Reading value={cp.weather.rain_in} unit="in/h" />
                <Reading value={cp.weather.snow_in} unit="in/h" />
                <td>{cp.weather.temp_f == null ? '–' : `${cp.weather.temp_f} °F`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
