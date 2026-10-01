import { useState } from 'react';
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { post } from './api';
import { Empty, Loading, Modal, Notice, PageHeading } from './components';
import { useCatalogs, useList } from './data';
import { dateLabel, initials, localDate, timeLabel, timeZone } from './format';

function monday(value) {
  const date = new Date(value); date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - (date.getDay() + 6) % 7);
  return date;
}

export default function Schedule({ user }) {
  const { staff } = useCatalogs();
  const shifts = useList('/shifts/');
  const appointments = useList('/appointments/');
  const [week, setWeek] = useState(() => monday(new Date()));
  const [staffFilter, setStaffFilter] = useState('');
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState('');
  const days = Array.from({ length: 7 }, (_, i) => { const day = new Date(week); day.setDate(day.getDate() + i); return day; });
  const team = staff.filter((person) => (!['doctor', 'nurse'].includes(user.role) || person.staff_id === user.staff_id) && (!staffFilter || person.staff_id === Number(staffFilter)));
  function moveWeek(amount) { const date = new Date(week); date.setDate(date.getDate() + amount * 7); setWeek(date); }
  function overlapsDay(item, day) { const next = new Date(day); next.setDate(next.getDate() + 1); return new Date(item.start_at) < next && new Date(item.end_at) > day; }
  return <><PageHeading eyebrow="Staff scheduling" title={['doctor', 'nurse'].includes(user.role) ? 'Your weekly schedule' : 'Team schedule'} action={user.role === 'administrator' && <button className="button button-primary" onClick={() => setAdding(true)}><Plus size={18} /> Add shift</button>}>View appointments and shifts. Times are shown in {timeZone}.</PageHeading>
    <Notice kind="success">{notice}</Notice><div className="schedule-controls"><div className="week-switch"><button className="icon-button" aria-label="Previous week" onClick={() => moveWeek(-1)}><ChevronLeft size={18} /></button><strong>{dateLabel(days[0], { year: undefined })} – {dateLabel(days[6])}</strong><button className="icon-button" aria-label="Next week" onClick={() => moveWeek(1)}><ChevronRight size={18} /></button></div><div className="filter-row"><select aria-label="Filter staff" value={staffFilter} onChange={(e) => setStaffFilter(e.target.value)}><option value="">All visible staff</option>{staff.filter((person) => !['doctor', 'nurse'].includes(user.role) || person.staff_id === user.staff_id).map((person) => <option key={person.staff_id} value={person.staff_id}>{person.user.full_name}</option>)}</select><span className="legend-item"><i className="legend-dot shift-dot" /> Shift</span><span className="legend-item"><i className="legend-dot appointment-dot" /> Appointment</span></div></div>
    {shifts.loading || appointments.loading ? <Loading /> : shifts.error || appointments.error ? <><Notice>{shifts.error || appointments.error}</Notice><button className="button button-secondary" onClick={() => { shifts.reload(); appointments.reload(); }}>Try again</button></> : !team.length ? <Empty title="No staff to show.">Staff profiles will appear here once they are added to the clinic.</Empty> : <section className="dash-panel calendar-shell" aria-label="Weekly staff schedule"><div className="calendar-grid"><div className="calendar-corner">Care team</div>{days.map((day) => <div className={`day-heading ${localDate(day) === localDate() ? 'today' : ''}`} key={localDate(day)}><strong>{day.toLocaleDateString(undefined, { weekday: 'short' })}</strong><span>{day.getDate()}</span></div>)}
      {team.map((person) => <StaffWeek key={person.staff_id} person={person} days={days} shifts={shifts.rows} appointments={appointments.rows} overlapsDay={overlapsDay} />)}
    </div></section>}
    <p className="panel-footnote">Empty cells mean no shifts or active appointments are listed for that day.</p>
    {adding && <ShiftForm staff={staff} onClose={() => setAdding(false)} onCreated={(shift) => { setAdding(false); setWeek(monday(shift.start_at)); shifts.reload(); setNotice('Shift added. This time is now available for matching appointments.'); }} />}
  </>;
}

function StaffWeek({ person, days, shifts, appointments, overlapsDay }) {
  return <><div className="staff-label"><span>{initials(person.user.full_name)}</span><p><strong>{person.user.full_name}</strong><small>{person.profession}</small></p></div>{days.map((day) => {
    const dailyShifts = shifts.filter((shift) => shift.staff_id === person.staff_id && overlapsDay(shift, day));
    const dailyVisits = appointments.filter((a) => ['confirmed', 'requested'].includes(a.status) && a.assigned_staff.some((s) => s.staff_id === person.staff_id) && overlapsDay(a, day));
    return <div className={`calendar-cell ${localDate(day) === localDate() ? 'today-cell' : ''}`} key={localDate(day)}>{dailyShifts.map((shift) => <div className={`shift-block ${person.profession === 'nurse' ? 'blue-shift' : ''}`} key={shift.shift_id}>{timeLabel(shift.start_at)} – {timeLabel(shift.end_at)}<small>On shift</small></div>)}{dailyVisits.map((a) => <div className="event-block" key={a.appointment_id}>{timeLabel(a.start_at)} · {a.service?.service_name || 'Appointment'}<small>{a.patient?.patient_name} · {a.room?.room_name || 'Unassigned room'}</small></div>)}{!dailyShifts.length && !dailyVisits.length && <span className="no-shift">—</span>}</div>;
  })}</>;
}

function ShiftForm({ staff, onClose, onCreated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const data = new FormData(event.currentTarget);
    try {
      const person = staff.find((s) => s.staff_id === Number(data.get('staff')));
      const start = new Date(data.get('start')); const end = new Date(data.get('end'));
      if (end <= start) throw new Error('The shift must end after it starts.');
      const shift = await post('/shifts/', { staff_id: person.staff_id, department_id: person.department_id, start_at: start.toISOString(), end_at: end.toISOString() });
      onCreated(shift);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <Modal title="Add a staff shift" onClose={onClose} busy={busy}><p>Choose a person and their working hours. Times use {timeZone}.</p><Notice>{error}</Notice><form onSubmit={submit}><fieldset disabled={busy} className="compact-form"><label><span>Staff member</span><select name="staff" required defaultValue=""><option value="" disabled>Choose a team member</option>{staff.map((person) => <option key={person.staff_id} value={person.staff_id}>{person.user.full_name} · {person.department.department_name}</option>)}</select></label><label><span>Shift starts</span><input type="datetime-local" name="start" required /></label><label><span>Shift ends</span><input type="datetime-local" name="end" required /></label><button className="button button-primary">{busy ? 'Saving shift…' : 'Save shift'}</button></fieldset></form></Modal>;
}
