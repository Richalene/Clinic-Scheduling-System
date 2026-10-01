import { ArrowRight, CalendarCheck2, CalendarDays, Clock3, Plus, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Empty, Loading, Notice, PageHeading, Status } from './components';
import { useCatalogs, useList } from './data';
import { dateLabel, localDate, timeLabel, timeZone } from './format';

export default function Dashboard({ user }) {
  const { rows, loading, error, reload } = useList('/appointments/');
  const { services, staff } = useCatalogs();
  const names = user.full_name.trim().split(/\s+/);
  const greeting = /^(dr|mr|mrs|ms|prof)\.?$/i.test(names[0]) ? names.slice(0, 2).join(' ') : names[0];
  const today = localDate();
  const active = rows.filter((a) => ['requested', 'confirmed'].includes(a.status));
  const upcoming = active.filter((a) => new Date(a.end_at) > new Date()).sort((a, b) => new Date(a.start_at) - new Date(b.start_at));
  const todays = active.filter((a) => localDate(a.start_at) === today);
  const metrics = [
    [CalendarDays, 'Today’s appointments', todays.length, 'Scheduled for today', 'sage'],
    [CalendarCheck2, 'Upcoming visits', upcoming.length, 'On your appointment list', 'blue'],
    [Clock3, 'Awaiting review', active.filter((a) => a.status === 'requested').length, 'Requested appointments', 'peach'],
    [UsersRound, user.role === 'patient' ? 'Clinic services' : 'Care team', user.role === 'patient' ? services.length : staff.length, user.role === 'patient' ? 'Explore when booking' : 'Doctors and nurses', 'sage'],
  ];
  return <><PageHeading eyebrow={dateLabel(new Date(), { weekday: 'long' })} title={`Hello, ${greeting.replace(/[.!]+$/, '')}.`} action={<Link className="button button-primary" to="/app/book"><Plus size={18} /> New appointment</Link>} />
    {['administrator', 'receptionist', 'doctor'].includes(user.role) && <Link className="button button-secondary mb-6" to="/app/appointments?status=requested">Review requests ({rows.filter((a) => a.status === 'requested').length})</Link>}
    {loading ? <Loading /> : error ? <><Notice>{error}</Notice><button className="button button-secondary" onClick={reload}>Try again</button></> : <>
      <section className="metric-grid mb-6 grid grid-cols-4 gap-[14px] max-[1180px]:grid-cols-2 max-[600px]:gap-2.5" aria-label="Appointment summary">{metrics.map(([Icon, title, count, note, color]) => <article className="metric-card" key={title}><span className={`metric-icon ${color}`}><Icon size={21} strokeWidth={1.6} /></span><div><p>{title}</p><strong>{count}</strong></div></article>)}</section>
      <div className="dashboard-grid"><section className="dash-panel"><div className="panel-heading"><div><h2>Upcoming appointments</h2></div><Link className="text-link" to="/app/appointments">View all <ArrowRight size={15} /></Link></div>
        {upcoming.length ? <div className="schedule-list">{upcoming.slice(0, 6).map((a) => <article key={a.appointment_id}><time dateTime={a.start_at}>{timeLabel(a.start_at)}<small>{dateLabel(a.start_at, { year: undefined })}</small></time><span className="schedule-line teal" /><div><strong>{a.service?.service_name || 'Appointment'}</strong><p>{a.patient?.patient_name || `Patient ${a.patient_id}`}</p></div><span className="room-tag">{a.room?.room_name || 'Room pending'}</span><Status value={a.status} /></article>)}</div> : <Empty title="No upcoming appointments">Booked appointments will appear here.</Empty>}
        <p className="panel-footnote">Times shown in {timeZone}.</p></section>

      </div></>}
  </>;
}
