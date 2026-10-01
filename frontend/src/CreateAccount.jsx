import { useState } from 'react';
import { post } from './api';
import PasswordInput from './PasswordInput';
import { Notice, PageHeading } from './components';
import { useCatalogs, useList } from './data';
import { label } from './format';

export function CreateAccountForm({ staff = false, onCreated, onBusyChange }) {
  const [role, setRole] = useState('doctor');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const clinical = staff && ['doctor', 'nurse'].includes(role);
  async function submit(event) {
    event.preventDefault(); setBusy(true); onBusyChange?.(true); setError('');
    const data = new FormData(event.currentTarget);
    const payload = { full_name: data.get('full_name').trim(), email: data.get('email').trim(), password: data.get('password') };
    if (staff) { payload.role = role; if (clinical) { payload.department_id = Number(data.get('department_id')); payload.qualification = data.get('qualification').trim() || null; } }
    else payload.phone_number = data.get('phone_number').trim() || null;
    try { const created = await post(staff ? '/users/staff-accounts' : '/users/patient-accounts', payload); onCreated(created); }
    catch (err) { setError(err.message); } finally { setBusy(false); onBusyChange?.(false); }
  }
  return <><Notice>{error}</Notice><form onSubmit={submit}><fieldset disabled={busy} className="compact-form">
    <label><span>Full name</span><input name="full_name" required minLength={2} maxLength={255} autoComplete="off" /></label>
    <label><span>Email address</span><input name="email" type="email" required autoComplete="off" /></label>
    <label><span>Initial password</span><PasswordInput name="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
    <p className="text-xs text-muted">Use 12?128 characters and share privately with the account owner. They can change it in My profile.</p>
    {staff ? <label><span>Staff role</span><select value={role} onChange={(e) => setRole(e.target.value)}>{['doctor','nurse','receptionist','administrator'].map((r) => <option key={r} value={r}>{label(r)}</option>)}</select></label> : <label><span>Phone number (optional)</span><input name="phone_number" type="tel" maxLength={50} /></label>}
    {clinical && <ClinicalFields />}
    <button type="submit" className="button button-primary">{busy ? 'Creating...' : staff ? 'Create staff account' : 'Create patient account'}</button>
  </fieldset></form></>;
}

function ClinicalFields() {
  const { rows, loading, error, reload } = useList('/staff/departments');
  return <><Notice>{error}</Notice>{error && <button type="button" className="text-button" onClick={reload}>Retry departments</button>}<label><span>Department</span><select name="department_id" required defaultValue=""><option value="">{loading ? 'Loading departments...' : 'Choose a department'}</option>{rows.map((d) => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}</select></label>{!loading && !error && !rows.length && <Notice kind="info">A department must be configured before creating a doctor or nurse account.</Notice>}<label><span>Qualification (optional)</span><input name="qualification" maxLength={255} /></label></>;
}

export default function PatientAccounts() {
  const { refresh } = useCatalogs();
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState('');
  return <><PageHeading title="Add a patient account" /><section className="dash-panel max-w-xl"><Notice kind="success">{message}</Notice><CreateAccountForm key={revision} onCreated={(account) => { setMessage(`Account created for ${account.full_name}. They can now sign in.`); setRevision((n) => n + 1); refresh(); }} /></section></>;
}
