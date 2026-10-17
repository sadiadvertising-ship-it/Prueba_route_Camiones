import { useState } from 'react'

function nextHour() {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  // The datetime-local input wants local wall time; toISOString would shift it to UTC.
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`
}

function Field({ label, error, children }) {
  return (
    <label className={error ? 'field invalid' : 'field'}>
      <span>{label}</span>
      {children}
      {error && <small>{error}</small>}
    </label>
  )
}

export default function TripForm({ onPlan, busy, errors }) {
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    departure: nextHour(),
    weight_lb: '',
    interval: '',
  })
  const edit = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  function submit(e) {
    e.preventDefault()
    onPlan({
      origin: form.origin,
      destination: form.destination,
      departure: new Date(form.departure).toISOString(),
      weight_lb: Number(form.weight_lb),
      interval: form.interval ? Number(form.interval) : null,
    })
  }

  return (
    <form onSubmit={submit}>
      <Field label="From" error={errors.origin?.[0]}>
        <input name="origin" value={form.origin} onChange={edit} placeholder="Dallas, TX" required autoFocus />
      </Field>
      <Field label="To" error={errors.destination?.[0]}>
        <input name="destination" value={form.destination} onChange={edit} placeholder="Chicago, IL" required />
      </Field>
      <Field label="Departure (your local time)" error={errors.departure?.[0]}>
        <input type="datetime-local" name="departure" value={form.departure} onChange={edit} required />
      </Field>
      <Field label="Load weight (lb)" error={errors.weight_lb?.[0]}>
        <input type="number" name="weight_lb" value={form.weight_lb} onChange={edit} placeholder="35000" min="1" required />
      </Field>
      <Field label="Checkpoint spacing" error={errors.interval?.[0]}>
        <select name="interval" value={form.interval} onChange={edit}>
          <option value="">Automatic: 10, 25 or 50 miles by trip length</option>
          <option value="10">Every 10 miles</option>
          <option value="25">Every 25 miles</option>
          <option value="50">Every 50 miles</option>
        </select>
      </Field>
      <button disabled={busy}>{busy ? 'Planning…' : 'Plan the trip'}</button>
      {errors.detail && <p className="problem">{errors.detail}</p>}
    </form>
  )
}
