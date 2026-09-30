import { useState } from 'react';
import { Pencil, Search, Trash2 } from 'lucide-react';
import { CreateAccountForm } from './CreateAccount';
import PasswordInput from './PasswordInput';
import { request } from './api';
import { Empty, Loading, Modal, Notice, PageHeading } from './components';
import { useCatalogs, useList } from './data';
import { label } from './format';

const roles = ['administrator', 'receptionist', 'doctor', 'nurse', 'patient'];

export default function Accounts({ user, onUpdated }) {
  const { rows, loading, error, reload, setRows } = useList('/users/');
  const { staff, patients, refresh } = useCatalogs();
  const [createBusy, setCreateBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [details, setDetails] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState('');
  const [statusTarget, setStatusTarget] = useState(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState('');
  const filtered = rows.filter((account) => (roleFilter === 'all' || account.role === roleFilter) && (statusFilter === 'all' || account.is_active === (statusFilter === 'active')) && `${account.full_name} ${account.email} ${account.role}`.toLowerCase().includes(search.trim().toLowerCase()));
  async function updated(account) {
    setRows((old) => old.map((row) => row.user_id === account.user_id ? account : row));
    setSelected(null); setMessage(`Changes saved for ${account.full_name}.`); refresh();
    if (account.user_id === user.user_id) onUpdated({ ...user, ...account });
  }
  async function changeStatus(account) {
    if (statusBusy || account.user_id === user.user_id) return;
    setStatusBusy(true); setStatusError(''); setMessage('');
    try {
      const result = await request(`/users/${account.user_id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !account.is_active }) });
      setRows((old) => old.map((row) => row.user_id === result.user_id ? result : row));
      setStatusTarget(null); setDetails(result);
      setMessage(`${result.full_name} is now ${result.is_active ? 'active' : 'inactive'}.`);
    } catch (err) { setStatusError(err.message); } finally { setStatusBusy(false); }
  }
  return <><PageHeading eyebrow="Administrator workspace" title="Account management" action={<button className="button button-primary" onClick={() => setCreating(true)}>Add staff account</button>}>Manage account details, roles, and access to your clinic.</PageHeading><Notice kind="success">{message}</Notice>{!statusTarget && !details && <Notice>{statusError}</Notice>}
    <section className="dash-panel"><div className="toolbar"><label className="search-field"><Search size={17} /><input aria-label="Search accounts" placeholder="Search name, email, or role…" value={search} onChange={(e) => setSearch(e.target.value)} /></label><select aria-label="Filter by role" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}><option value="all">All roles</option>{roles.map((role) => <option key={role} value={role}>{label(role)}</option>)}</select><select aria-label="Filter by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div>
      {!loading && !error && <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-xs text-muted"><span>{filtered.length} of {rows.length} accounts</span>{(search || roleFilter !== 'all' || statusFilter !== 'all') && <button className="text-button" onClick={() => { setSearch(''); setRoleFilter('all'); setStatusFilter('all'); }}>Clear filters</button>}</div>}
      {loading ? <Loading /> : error ? <><Notice>{error}</Notice><button className="button button-secondary" onClick={reload}>Try again</button></> : !filtered.length ? <Empty title="No matching accounts.">Try another search or clear your filters.</Empty> : <div className="appointment-table-wrap"><table className="appointment-table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Access</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{filtered.map((account) => <tr key={account.user_id}><td><strong>{account.full_name}</strong>{account.user_id === user.user_id && <small>Your account</small>}</td><td>{account.email}</td><td className="capitalize">{label(account.role)}</td><td><div className="flex items-center gap-2"><span className={`status ${account.is_active ? 'confirmed' : 'cancelled'}`}>{account.is_active ? 'Active' : 'Inactive'}</span></div></td><td><button className="text-button" aria-label={`Manage ${account.full_name}`} onClick={() => { setStatusError(''); setDetails(account); }}><Pencil size={14} /> Manage</button></td></tr>)}</tbody></table></div>}
      <p className="panel-footnote">Deactivating an account blocks access without deleting its appointment history.</p>
    </section>{creating && <Modal title="Add staff account" busy={createBusy} onClose={() => setCreating(false)}><CreateAccountForm staff onBusyChange={setCreateBusy} onCreated={(account) => { setRows((old) => [...old, account]); setCreating(false); setMessage(`Staff account created for ${account.full_name}.`); refresh(); }} /></Modal>}{deleteTarget && <DeleteAccount account={deleteTarget} onClose={() => setDeleteTarget(null)} onDeleted={() => { setRows((old) => old.filter((row) => row.user_id !== deleteTarget.user_id)); setMessage(`Account deleted for ${deleteTarget.full_name}.`); setDeleteTarget(null); refresh(); }} />}{statusTarget && <Modal title="Deactivate account?" busy={statusBusy} onClose={() => { setDetails(statusTarget); setStatusTarget(null); setStatusError(''); }}><Notice>{statusError}</Notice><p>Deactivate <strong>{statusTarget.full_name}</strong> ({statusTarget.email})?</p><p className="text-sm text-muted">This blocks account access. Existing appointments, shifts, and patient records remain unchanged. You can reactivate the account using the same toggle.</p><div className="flex flex-wrap gap-3"><button className="button button-primary" disabled={statusBusy} onClick={() => changeStatus(statusTarget)}>{statusBusy ? 'Saving...' : 'Confirm deactivation'}</button><button className="button button-secondary" disabled={statusBusy} onClick={() => { setDetails(statusTarget); setStatusTarget(null); setStatusError(''); }}>Cancel</button></div></Modal>}{details && <AccountDetails account={details} patient={patients.find((p) => p.user_id === details.user_id)} staff={staff.find((p) => p.user_id === details.user_id)} self={details.user_id === user.user_id} busy={statusBusy} error={statusError} onStatus={() => { setStatusError(''); if (details.is_active) { setStatusTarget(details); setDetails(null); } else changeStatus(details); }} onEdit={() => { setSelected(details); setDetails(null); }} onDelete={() => { setDeleteTarget(details); setDetails(null); }} onClose={() => setDetails(null)} />}{selected && <AccountEditor account={selected} self={selected.user_id === user.user_id} clinical={staff.some((person) => person.user_id === selected.user_id)} onClose={() => setSelected(null)} onSaved={updated} />}
  </>;
}

function AccountEditor({ account, self, clinical, onClose, onSaved }) {
  const [form, setForm] = useState({ full_name: account.full_name, email: account.email, role: account.role, is_active: account.is_active });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  async function save(event) {
    event.preventDefault();
    if (account.is_active && !form.is_active) { setConfirming(true); return; }
    await commit();
  }
  async function commit() {
    setBusy(true); setError('');
    try {
      const result = await request(`/users/${account.user_id}`, { method: 'PATCH', body: JSON.stringify({ ...form, full_name: form.full_name.trim(), email: form.email.trim() }) });
      onSaved(result);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  if (confirming) return <Modal title="Deactivate account?" onClose={() => setConfirming(false)} busy={busy}><Notice>{error}</Notice><p>Deactivate <strong>{account.full_name}</strong> ({account.email})?</p><p className="text-sm text-muted">This blocks sign-in and authenticated access. Patient records, appointments, and staff shifts remain in place. Deactivation does not cancel or reassign scheduled work. You can reactivate this account later.</p><p className="text-xs text-muted">Any other edits in this form will also be saved.</p><div className="flex flex-wrap gap-3"><button className="button button-primary" disabled={busy} onClick={commit}>{busy ? 'Saving...' : 'Confirm deactivation'}</button><button className="button button-secondary" disabled={busy} onClick={() => setConfirming(false)}>Back to editing</button></div></Modal>;
  return <Modal title="Edit account" onClose={onClose} busy={busy}><Notice>{error}</Notice><form onSubmit={save}><fieldset disabled={busy} className="compact-form">
    <label><span>Full name</span><input required minLength={2} maxLength={255} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
    <label><span>Email address</span><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
    <label><span>Account role</span><select disabled={self || clinical} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{roles.map((role) => <option key={role} value={role}>{label(role)}</option>)}</select></label>
    {clinical && <p className="text-xs text-muted">This role is linked to a clinical staff profile and cannot be changed here.</p>}
    {!clinical && ['doctor', 'nurse'].includes(form.role) && <p className="text-xs text-muted">A matching staff profile and department must also be configured before assigning shifts.</p>}
    <label className="flex items-center gap-3 text-sm"><input type="checkbox" disabled={self} checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Account is active</label>
    {self && <p className="text-xs text-muted">Your own administrator role and active status are protected to keep you from losing access.</p>}
    {!form.is_active && <Notice kind="info">Saving will block this user’s access. Their records will be retained.</Notice>}
    <button className="button button-primary" type="submit">{busy ? 'Saving…' : 'Save account'}</button>
  </fieldset></form></Modal>;
}

function AccountDetails({ account, patient, staff, self, busy, error, onStatus, onEdit, onDelete, onClose }) {
  const fields = [
    ['Account ID', account.user_id], ['Full name', account.full_name],
    ['Email address', account.email], ['Role', label(account.role)],
    ['Access', account.is_active ? 'Active' : 'Inactive'],
    ['Created', account.created_at ? new Date(account.created_at).toLocaleString() : 'Not available'],
    ['Patient profile', patient ? `Patient #${patient.patient_id}` : 'Not linked'],
    ['Phone number', patient?.phone_number || 'Not provided'],
    ['Staff profile', staff ? `Staff #${staff.staff_id}` : 'Not linked'],
    ...(staff ? [['Profession', label(staff.profession)], ['Department', staff.department?.department_name || `Department #${staff.department_id}`], ['Qualification', staff.qualification || 'Not provided']] : []),
  ];
  return <Modal title="Manage account" onClose={onClose} busy={busy}><Notice>{error}</Notice><dl className="grid grid-cols-2 gap-x-6 gap-y-4 max-[480px]:grid-cols-1">{fields.map(([name, value]) => <div key={name} className="min-w-0"><dt className="mb-1 text-xs text-muted">{name}</dt><dd className="m-0 break-words text-sm font-medium text-ink">{value}</dd></div>)}</dl><div className="my-6 flex items-center justify-between gap-4 rounded-xl shadow-clinic bg-ivory p-4"><div><strong className="text-sm">Account access</strong><p className="mb-0 mt-1 text-xs text-muted">{self ? 'Your own access is protected.' : busy ? 'Saving status...' : account.is_active ? 'Active - this user can sign in.' : 'Inactive - sign-in is blocked.'}</p></div><button type="button" role="switch" aria-checked={account.is_active} aria-label={`Account access for ${account.full_name}`} disabled={busy || self} title={self ? 'You cannot deactivate your own account' : account.is_active ? 'Deactivate account' : 'Reactivate account'} className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-not-allowed disabled:opacity-50 ${account.is_active ? 'bg-teal' : 'bg-muted'}`} onClick={onStatus}><span className={`h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${account.is_active ? 'translate-x-6' : 'translate-x-1'}`} /></button></div><div className="flex flex-wrap items-center justify-between gap-3 pt-4"><button className="button button-primary button-small" disabled={busy} onClick={onEdit}><Pencil size={14} /> Edit details</button><button className="text-button text-red-700 disabled:opacity-40" disabled={self || busy} aria-label={`Delete ${account.full_name}`} onClick={onDelete}><Trash2 size={14} /> Delete account</button></div></Modal>;
}


function DeleteAccount({ account, onClose, onDeleted }) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    if (!password || busy) return;
    setBusy(true); setError('');
    try { await request(`/users/${account.user_id}`, { method: 'DELETE', body: JSON.stringify({ admin_password: password }) }); onDeleted(); }
    catch (err) { setError(err.message); } finally { setPassword(''); setBusy(false); }
  }
  return <Modal title="Delete unused account?" onClose={onClose} busy={busy}><Notice>{error}</Notice><p>Permanently delete <strong>{account.full_name}</strong> ({account.email})?</p><p className="text-sm text-muted">This cannot be undone. Only unused accounts can be deleted. Accounts with staff profiles, appointment or waitlist history, or recorded actions must be deactivated instead.</p><form onSubmit={submit}><fieldset disabled={busy} className="compact-form"><label><span>Your administrator password</span><PasswordInput autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} maxLength={128} required /></label><div className="flex flex-wrap gap-3"><button type="submit" className="button bg-red-700 text-white hover:bg-red-800 disabled:opacity-40" disabled={!password}>{busy ? 'Deleting...' : 'Permanently delete'}</button><button type="button" className="button button-secondary" onClick={onClose}>Cancel</button></div></fieldset></form></Modal>;
}
