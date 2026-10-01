import { useState } from 'react';
import { Check, X, Plus, RefreshCw, Search } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { request } from './api';
import { Empty, Loading, Modal, Notice, PageHeading, Status } from './components';
import { useCatalogs, useList } from './data';
import { dateLabel, localDate, timeLabel, timeZone } from './format';

export default function Appointments({ user }) {
  const { rows, loading, error, reload, setRows } = useList('/appointments/');
  const { staff } = useCatalogs();
  const doctorName = (appointment) => staff.filter((person) => person.profession === 'doctor' && appointment.assigned_staff?.some((assigned) => assigned.staff_id === person.staff_id)).map((person) => person.user.full_name).join(', ') || 'Unassigned';
  const location = useLocation();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(() => new URLSearchParams(location.search).get('status') === 'requested' ? 'requested' : 'all');
  const [review, setReview] = useState(null);
  const canReview = (a) => a.status === 'requested' && (['administrator', 'receptionist'].includes(user.role) || (user.role === 'doctor' && a.assigned_staff?.some((item) => item.staff_id === user.staff_id)));
  const [day, setDay] = useState('');
  const [selected, setSelected] = useState(null);
  const [completeTarget, setCompleteTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState(location.state?.message || '');
  const [page, setPage] = useState(0);
  const filtered = rows.filter((a) => (status === 'all' || a.status === status) && (!day || localDate(a.start_at) === day) &&
    `${a.patient?.patient_name} ${a.service?.service_name} ${a.room?.room_name} ${doctorName(a)} ${a.appointment_id}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => new Date(b.start_at) - new Date(a.start_at));
  const safePage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 10) - 1));
  async function cancel() {
    setBusy(true); setActionError('');
    try {
      const updated = await request(`/appointments/${selected.appointment_id}/cancel`, { method: 'POST' });
      setRows((old) => old.map((row) => row.appointment_id === updated.appointment_id ? updated : row));
      setSelected(null); setSuccess('Appointment cancelled. Its reserved resources are now available again.');
    } catch (err) { setActionError(err.message); } finally { setBusy(false); }
  }
  async function submitReview() {
    setBusy(true); setActionError('');
    try {
      const updated = await request(`/appointments/${review.appointment.appointment_id}/${review.action}`, { method: 'POST' });
      setRows((old) => old.map((row) => row.appointment_id === updated.appointment_id ? updated : row));
      setSuccess(review.action === 'approve' ? 'Appointment accepted and confirmed.' : 'Appointment rejected. Reservations released.');
      setReview(null);
    } catch (err) { setActionError(err.message); } finally { setBusy(false); }
  }
  async function complete() {
    setBusy(true); setActionError('');
    try {
      const updated = await request(`/appointments/${completeTarget.appointment_id}/complete`, { method: 'POST' });
      setRows((old) => old.map((row) => row.appointment_id === updated.appointment_id ? updated : row));
      setCompleteTarget(null); setSuccess('Appointment marked as completed.');
    } catch (err) { setActionError(err.message); } finally { setBusy(false); }
  }
  return <><PageHeading title="Appointments" action={<Link className="button button-primary" to="/app/book"><Plus size={18} /> New appointment</Link>} />
    <Notice kind="success">{success}</Notice><section className="dash-panel appointment-list-panel"><div className="appointment-list-heading"><div><h2>{status === 'requested' ? 'Appointment requests' : 'Appointment list'}</h2></div><span className="appointment-count">{loading ? 'Loading...' : `${filtered.length} ${filtered.length === 1 ? 'appointment' : 'appointments'}`}</span></div><div className="toolbar appointment-toolbar"><label className="search-field"><Search size={17} aria-hidden="true" /><input aria-label="Search appointments" placeholder="Search patient, doctor, or service…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} /></label>
      <label className="appointment-filter"><span>Status</span><select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>{['all', 'requested', 'confirmed', 'cancelled', 'completed', 'no_show'].map((value) => <option key={value} value={value}>{value === 'all' ? 'All statuses' : value === 'requested' ? 'Awaiting review' : value.replace('_', ' ')}</option>)}</select></label><label className="appointment-filter"><span>Date</span><input type="date" aria-label="Filter by date" value={day} onChange={(e) => { setDay(e.target.value); setPage(0); }} /></label><button className="icon-button" aria-label="Refresh appointments" disabled={loading} onClick={reload}><RefreshCw size={17} /></button></div>
      {(search || day || status !== 'all') && <button className="text-button mb-5" onClick={() => { setSearch(''); setDay(''); setStatus('all'); setPage(0); }}>Clear filters</button>}
      {loading ? <Loading /> : error ? <Notice>{error}</Notice> : !filtered.length ? <Empty title="No appointments to show.">{rows.length ? 'Try a different search or filter.' : 'Your appointments will appear here once a visit is booked.'}</Empty> : <><div className="appointment-table-wrap"><table className="appointment-table"><thead><tr><th>Patient</th><th>Service</th><th>Date & time</th><th>Care team & room</th><th>Status</th><th className="appointment-actions-heading">Actions</th></tr></thead><tbody>
        {filtered.slice(safePage * 10, safePage * 10 + 10).map((a) => <tr key={a.appointment_id}><td><strong>{a.patient?.patient_name || `Patient ${a.patient_id}`}</strong><small>Appointment #{a.appointment_id}</small></td><td>{a.service?.service_name || `Service ${a.service_id}`}{a.priority === 'urgent' && <small className="urgent-text">Urgent request</small>}</td><td><strong>{dateLabel(a.start_at)}</strong><small>{timeLabel(a.start_at)} – {timeLabel(a.end_at)}</small></td><td><strong>{doctorName(a)}</strong><small>{a.room?.room_name || 'Room unassigned'}</small></td><td><Status value={a.status} />{a.status === 'requested' && new Date(a.start_at) <= new Date() && <small className="review-expired">Past appointment - cannot accept</small>}</td><td>{canReview(a) ? <div className="review-actions"><button className="button button-primary button-small" disabled={new Date(a.start_at) <= new Date()} title={new Date(a.start_at) <= new Date() ? 'Past appointments cannot be accepted' : 'Accept this request'} aria-label={`Accept appointment ${a.appointment_id}`} onClick={() => { setReview({ appointment: a, action: 'approve' }); setActionError(''); }}><Check size={16} aria-hidden="true" />Accept</button><button className="button button-small review-reject" aria-label={`Reject appointment ${a.appointment_id}`} onClick={() => { setReview({ appointment: a, action: 'reject' }); setActionError(''); }}><X size={16} aria-hidden="true" />Reject</button></div> : ['requested', 'confirmed'].includes(a.status) && <div className="flex gap-2">{a.status === 'confirmed' && user.role !== 'patient' && <button aria-label={`Complete appointment ${a.appointment_id}`} className="text-button" style={{color: '#4a7c59'}} onClick={() => { setCompleteTarget(a); setActionError(''); }}>Complete<span className="sr-only"> appointment {a.appointment_id}</span></button>}<button aria-label={`Cancel appointment ${a.appointment_id}`} className="text-button cancel-link" onClick={() => { setSelected(a); setActionError(''); }}>Cancel<span className="sr-only"> appointment {a.appointment_id}</span></button></div>}</td></tr>)}
      </tbody></table></div><div className="table-footer"><span>Showing {safePage * 10 + 1}–{Math.min(safePage * 10 + 10, filtered.length)} of {filtered.length} appointments · {timeZone}</span><div><button aria-label="Previous page" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>←</button><span>Page {safePage + 1}</span><button aria-label="Next page" disabled={(safePage + 1) * 10 >= filtered.length} onClick={() => setPage(safePage + 1)}>→</button></div></div></>}
    </section>{review && <Modal title={review.action === 'approve' ? 'Accept appointment?' : 'Reject appointment?'} busy={busy} onClose={() => setReview(null)}><p>{review.appointment.patient?.patient_name}: {review.appointment.service?.service_name} on {dateLabel(review.appointment.start_at)} at {timeLabel(review.appointment.start_at)}.</p><p>{review.action === 'approve' ? 'Confirm this appointment with its assigned doctor and reserved resources.' : 'This will cancel the request and release its doctor, room, and equipment.'}</p><Notice>{actionError}</Notice><div className="modal-actions"><button className="button button-secondary" disabled={busy} onClick={() => setReview(null)}>Go back</button><button className="button button-primary" disabled={busy} onClick={submitReview}>{busy ? 'Saving...' : review.action === 'approve' ? 'Confirm acceptance' : 'Confirm rejection'}</button></div></Modal>}{selected && <Modal title="Cancel this appointment?" busy={busy} onClose={() => setSelected(null)}><p>{selected.service?.service_name} on {dateLabel(selected.start_at)} at {timeLabel(selected.start_at)}.</p><p>The reserved time will become available to other patients.</p><Notice>{actionError}</Notice><div className="modal-actions"><button className="button button-secondary" disabled={busy} onClick={() => setSelected(null)}>Keep appointment</button><button className="button button-danger" disabled={busy} onClick={cancel}>{busy ? 'Cancelling…' : 'Confirm cancellation'}</button></div></Modal>}{completeTarget && <Modal title="Complete this appointment?" busy={busy} onClose={() => setCompleteTarget(null)}><p>Mark {completeTarget.service?.service_name} on {dateLabel(completeTarget.start_at)} for {completeTarget.patient?.patient_name} as completed?</p><Notice>{actionError}</Notice><div className="modal-actions"><button className="button button-secondary" disabled={busy} onClick={() => setCompleteTarget(null)}>Cancel</button><button className="button button-primary" disabled={busy} onClick={complete}>{busy ? 'Saving...' : 'Confirm completion'}</button></div></Modal>}</>;
}
