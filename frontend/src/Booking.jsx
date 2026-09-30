import { useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Clock3, Search, UserPlus } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { post, request } from './api';
import { Empty, Modal, Notice, PageHeading } from './components';
import { useCatalogs } from './data';
import { dateLabel, localDate, searchWindow, timeLabel, timeZone } from './format';

export default function Booking({ user }) {
  const { services, patients, equipment, staff, addPatient } = useCatalogs();
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
  const [form, setForm] = useState({ patient: String(user.patient_id || ''), service: '', doctor: '', date: localDate(tomorrow), from: '09:00', to: '17:00', priority: 'normal', equipment: [] });
  const [slots, setSlots] = useState(null);
  const [selected, setSelected] = useState(null);
  const [searching, setSearching] = useState(false);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');
  const [walkIn, setWalkIn] = useState(false);
  const navigate = useNavigate();
  const service = services.find((s) => s.service_id === Number(form.service));
  const canCreatePatient = ['administrator', 'receptionist'].includes(user.role);
  const blocked = user.role === 'patient' && !user.patient_id;
  function update(key, value) { setForm((old) => ({ ...old, [key]: value })); setSlots(null); setSelected(null); setError(''); setHint(''); }
  async function findSlots(event) {
    event?.preventDefault(); setError(''); setHint(''); setSlots(null); setSelected(null);
    setSearching(true);
    try {
      const window = searchWindow(form.date, form.from, form.to);
      const params = new URLSearchParams({ service_id: form.service, ...window });
      if (form.doctor) params.set('doctor_id', form.doctor);
      form.equipment.forEach((id) => params.append('equipment_ids', id));
      const rows = await request(`/appointments/availability?${params}`);
      // The API books by start time and automatically chooses the resources.
      // Show each time once; the optional doctor choice is enforced by the API.
      setSlots([...new Map(rows.map((slot) => [slot.candidate_start, slot])).values()]);
    } catch (err) { setError(err.message); } finally { setSearching(false); }
  }
  async function book() {
    setError(''); setBooking(true);
    let appointment;
    try {
      appointment = await post('/appointments/', {
        ...(form.doctor ? { doctor_id: Number(form.doctor) } : {}),
        patient_id: Number(form.patient), service_id: Number(form.service),
        start_at: selected.candidate_start, priority: form.priority, equipment_ids: form.equipment,
      });
    } catch (err) {
      if (err.status === 409) {
        setSelected(null); setSlots(null);
        setHint('That time is no longer available. Search again to see the latest openings.');
      } else setError(err.message);
    } finally { setBooking(false); }
    if (appointment) navigate('/app/appointments', { state: { message: appointment.status === 'requested' ? 'Appointment requested. Your clinic will review it.' : `Appointment confirmed for ${dateLabel(appointment.start_at)} at ${timeLabel(appointment.start_at)}.` } });
  }
  return <><Link className="back-inline" to="/app/appointments"><ArrowLeft size={15} /> All appointments</Link><PageHeading eyebrow="Appointments" title="Book an appointment">A few details. A time that works. We’ll bring the rest together.</PageHeading>
    <div className="booking-layout grid grid-cols-[minmax(290px,1fr)_minmax(330px,1.2fr)] items-start gap-[22px] max-[1180px]:grid-cols-1"><section className="dash-panel"><div className="panel-heading"><div><p className="eyebrow">Step 01</p><h2>Visit details</h2></div><span className="step-number">01</span></div>
      <Notice>{blocked ? 'Your account needs a patient profile before booking. Please contact your clinic administrator.' : ''}</Notice>
      <form onSubmit={findSlots}><fieldset className="compact-form" disabled={searching || booking || blocked}>
        {user.role === 'patient' ? <div className="patient-summary"><span className="metric-icon sage"><Check size={19} /></span><div><small>Booking for</small><strong>{user.full_name}</strong></div></div> : <label><span>Patient</span><select required value={form.patient} onChange={(e) => update('patient', e.target.value)}><option value="">Choose a patient</option>{patients.map((p) => <option value={p.patient_id} key={p.patient_id}>{p.patient_name}</option>)}</select></label>}
        {canCreatePatient && <button className="text-button walkin-link" type="button" onClick={() => setWalkIn(true)}><UserPlus size={15} /> Add a walk-in patient</button>}
        <label><span>Service</span><select required value={form.service} onChange={(e) => update('service', e.target.value)}><option value="">Choose a service</option>{services.map((s) => <option value={s.service_id} key={s.service_id}>{s.service_name} · {s.duration_minutes} min</option>)}</select></label>
        {service && <p className="field-help">{service.duration_minutes} minutes · Doctor{service.requires_nurse ? ' and nurse' : ''} · {service.room_type}</p>}
        <label><span>Doctor</span><select value={form.doctor} onChange={(e) => update('doctor', e.target.value)}><option value="">Any available doctor</option>{staff.filter((person) => person.profession === 'doctor').map((person) => <option key={person.staff_id} value={person.staff_id}>{person.user.full_name}</option>)}</select></label>
        <label><span>Preferred date</span><input type="date" required min={localDate()} value={form.date} onChange={(e) => update('date', e.target.value)} /></label>
        <div className="form-split grid grid-cols-2 gap-3"><label><span>From</span><input type="time" required value={form.from} onChange={(e) => update('from', e.target.value)} /></label><label><span>Until</span><input type="time" required value={form.to} onChange={(e) => update('to', e.target.value)} /></label></div><p className="field-help">Times are in {timeZone}. Allow enough time for the full visit.</p>
        {user.role !== 'patient' && <label><span>Priority</span><select value={form.priority} onChange={(e) => update('priority', e.target.value)}><option value="normal">Normal appointment</option><option value="urgent">Urgent request for review</option></select></label>}
        <details className="equipment-picker"><summary>Equipment for this visit <small>{form.equipment.length ? `${form.equipment.length} selected` : 'Optional'}</small></summary><p className="field-help">Select equipment requested by your care team.</p>{equipment.length ? equipment.map((item) => <label className="check-label" key={item.equipment_id}><input type="checkbox" disabled={item.status !== 'available'} checked={form.equipment.includes(item.equipment_id)} onChange={(e) => update('equipment', e.target.checked ? [...form.equipment, item.equipment_id] : form.equipment.filter((id) => id !== item.equipment_id))} /><span>{item.equipment_name}{item.status !== 'available' && <small> · {item.status.replaceAll('_', ' ')}</small>}</span></label>) : <p className="field-help">No equipment is listed.</p>}</details>
        <button className="button button-primary full-button" type="submit"><Search size={17} />{searching ? 'Finding available times…' : 'Find available times'}</button>
      </fieldset></form>
    </section><section className="dash-panel slot-panel"><div className="panel-heading"><div><p className="eyebrow">Step 02</p><h2>Available times</h2></div><span className="step-number">02</span></div><Notice>{error}</Notice><Notice kind="info">{hint}</Notice>
      {searching ? <Empty title="Finding the right fit…">Checking the room, care team, and selected equipment.</Empty> : slots === null ? <Empty title="Search for an appointment">Choose a service and date, then search for an available time.</Empty> : slots.length === 0 ? <Empty title="No openings in this window.">Try another date or a wider time range. Your clinic can help if you need a different arrangement.</Empty> : <><p className="slot-date">{dateLabel(form.date + 'T12:00:00', { weekday: 'long' })}<span>{slots.length} available {slots.length === 1 ? 'time' : 'times'}</span></p><div className="slot-grid grid grid-cols-3 gap-2.5 max-[600px]:grid-cols-2">{slots.map((slot) => <button type="button" disabled={booking} aria-pressed={selected?.candidate_start === slot.candidate_start} className={`slot ${selected?.candidate_start === slot.candidate_start ? 'selected' : ''}`} key={slot.candidate_start} onClick={() => setSelected(slot)}><Clock3 size={15} />{timeLabel(slot.candidate_start)}</button>)}</div>
        {selected && <div className="booking-summary"><h3>Appointment summary</h3><dl><div><dt>Service</dt><dd>{service.service_name}</dd></div><div><dt>Time</dt><dd>{timeLabel(selected.candidate_start)} – {timeLabel(selected.candidate_end)}</dd></div><div><dt>Patient</dt><dd>{patients.find((p) => p.patient_id === Number(form.patient))?.patient_name || user.full_name}</dd></div><div><dt>Doctor</dt><dd>{form.doctor ? staff.find((person) => person.staff_id === Number(form.doctor))?.user.full_name : 'Any available doctor'}</dd></div><div><dt>Equipment</dt><dd>{form.equipment.length ? equipment.filter((item) => form.equipment.includes(item.equipment_id)).map((item) => item.equipment_name).join(', ') : 'None selected'}</dd></div></dl><p className="field-help">Your selected doctor is kept when you book; room and nurse assignments are automatic. Availability is checked again before your visit is saved.</p><button className="button button-primary full-button" disabled={booking} onClick={book}>{booking ? 'Booking your visit…' : 'Request appointment'}<ArrowRight size={17} /></button></div>}
      </>}
    </section></div>{walkIn && <WalkIn onClose={() => setWalkIn(false)} onCreated={(patient) => { addPatient(patient); update('patient', String(patient.patient_id)); setWalkIn(false); }} />}
  </>;
}

function WalkIn({ onClose, onCreated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError('');
    try { onCreated(await post('/patients/', { patient_name: data.get('name').trim(), phone_number: data.get('phone').trim() || null })); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <Modal title="Welcome a walk-in patient" onClose={onClose} busy={busy}><Notice>{error}</Notice><form className="compact-form" onSubmit={submit}><fieldset disabled={busy}><label className="form-field"><span>Patient name</span><input required minLength={2} maxLength={255} name="name" autoComplete="name" /></label><label className="form-field"><span>Phone number (optional)</span><input type="tel" name="phone" maxLength={50} autoComplete="tel" /></label><button className="button button-primary full-button">{busy ? 'Adding patient…' : 'Add patient'}</button></fieldset></form></Modal>;
}
