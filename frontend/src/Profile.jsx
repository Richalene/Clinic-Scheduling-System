import { useRef, useState } from 'react';
import { Camera, LoaderCircle, LockKeyhole, Save, Trash2, Upload, UserRound } from 'lucide-react';
import PasswordInput from './PasswordInput';
import { post, request } from './api';
import { Notice, PageHeading } from './components';
import { useCatalogs } from './data';
import { initials, label } from './format';

export default function Profile({ user, onUpdated, onPasswordChanged }) {
  const { refresh } = useCatalogs();
  const pictureInput = useRef(null);
  const [form, setForm] = useState({ full_name: user.full_name, email: user.email, phone_number: user.phone_number || '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);
  const [pictureBusy, setPictureBusy] = useState(false);
  async function updatePicture(file, remove = false) {
    setError(''); setSuccess('');
    if (!remove && !file) return;
    if (file && file.size > 2 * 1024 * 1024) { setError('Choose a picture smaller than 2 MB.'); return; }
    setPictureBusy(true);
    try {
      const body = new FormData();
      if (file) body.append('file', file);
      const updated = await request('/users/me/picture', { method: remove ? 'DELETE' : 'PUT', ...(remove ? {} : { body }) });
      onUpdated(updated); setSuccess(remove ? 'Profile picture removed.' : 'Profile picture saved.');
    } catch (err) { setError(err.message); } finally { setPictureBusy(false); }
  }
  async function save(event) {
    event.preventDefault(); setSaving(true); setError(''); setSuccess('');
    try {
      const payload = { full_name: form.full_name.trim(), email: form.email.trim() };
      if (user.patient_id) payload.phone_number = form.phone_number.trim() || null;
      const updated = await request('/users/me', { method: 'PATCH', body: JSON.stringify(payload) });
      onUpdated(updated); refresh(); setSuccess('Your profile has been saved.');
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  }
  async function changePassword(event) {
    event.preventDefault(); setPasswordError('');
    const formData = new FormData(event.currentTarget);
    if (formData.get('new_password') !== formData.get('confirm_password')) {
      setPasswordError('The new passwords do not match.'); return;
    }
    setChangingPassword(true);
    try {
      await post('/auth/change-password', { old_password: formData.get('old_password'), new_password: formData.get('new_password') });
      onPasswordChanged();
    } catch (err) { setPasswordError(err.message); } finally { setChangingPassword(false); }
  }
  return <><PageHeading eyebrow="Your account" title="My profile">Keep your details up to date and manage your password.</PageHeading>
    <Notice>{error}</Notice><Notice kind="success">{success}</Notice><fieldset disabled={pictureBusy || saving} aria-label="Profile picture" aria-busy={pictureBusy} className="mb-6 min-w-0 rounded-2xl shadow-clinic bg-paper p-6 disabled:opacity-70">
          <div className="flex items-center gap-5 max-[480px]:flex-col max-[480px]:items-start">
            <div className="relative shrink-0">
              <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full bg-sage font-serif text-3xl text-teal ring-4 ring-paper shadow-sm">{user.profile_picture ? <img className="h-full w-full object-cover" src={user.profile_picture} alt="Your profile picture" /> : initials(user.full_name)}</div>
              <span aria-hidden="true" className="absolute -right-1 bottom-0 grid h-8 w-8 place-items-center rounded-full border-[3px] border-paper bg-teal text-white"><Camera size={14} /></span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-sm font-semibold text-ink">Profile picture</p>
              <p className="mb-3 text-xs leading-relaxed text-muted">Update your profile photo.</p>
              <input ref={pictureInput} className="hidden" aria-label="Choose profile picture" aria-describedby="picture-help" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { updatePicture(event.target.files?.[0]); event.target.value = ''; }} />
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" className="button button-primary button-small focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal" onClick={() => pictureInput.current?.click()}>{pictureBusy ? <LoaderCircle size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <Upload size={16} aria-hidden="true" />}{pictureBusy ? 'Saving...' : user.profile_picture ? 'Change photo' : 'Upload photo'}</button>
                {user.profile_picture && <button type="button" className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-muted transition-colors hover:bg-peach/50 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal" aria-label="Remove picture" onClick={() => updatePicture(null, true)}><Trash2 size={14} aria-hidden="true" />Remove</button>}
              </div>
            </div>
          </div>
          <p id="picture-help" className="mb-0 mt-4 pt-3 text-xs leading-relaxed text-muted">JPG, PNG or WebP. Up to 2 MB. Photos are cropped to a square and saved automatically.</p>
          <span className="sr-only" role="status">{pictureBusy ? 'Saving profile picture' : ''}</span>
        </fieldset>
    <div className="grid grid-cols-2 items-stretch gap-6 max-[1100px]:grid-cols-1">
      <section className="dash-panel flex flex-col"><div className="panel-heading"><h2 className="flex items-center gap-2"><UserRound size={21} className="mr-2" /> Profile details</h2><span className="status confirmed">{label(user.role)}</span></div>
<form onSubmit={save} className="flex flex-1 flex-col"><fieldset disabled={saving || pictureBusy} className="flex min-w-0 flex-1 flex-col gap-[15px] compact-form">
          <label><span>Full name</span><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} maxLength={255} autoComplete="name" /></label>
          <label><span>Email address</span><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required autoComplete="email" /></label>
          {user.patient_id && <label><span>Phone number (optional)</span><input type="tel" value={form.phone_number} onChange={(e) => setForm({ ...form, phone_number: e.target.value })} maxLength={50} autoComplete="tel" /></label>}
          <p className="text-xs text-muted">Use your updated email the next time you sign in. Your clinic administrator manages your role and account access.</p>
          <button className="button button-primary mt-auto" type="submit"><Save size={17} />{saving ? 'Saving…' : 'Save profile'}</button>
        </fieldset></form>
      </section>
      <section className="dash-panel flex flex-col"><div className="panel-heading"><h2 className="flex items-center gap-2"><LockKeyhole size={21} className="mr-2" /> Change password</h2></div><Notice>{passwordError}</Notice><form onSubmit={changePassword} className="flex flex-1 flex-col"><fieldset disabled={changingPassword} className="flex min-w-0 flex-1 flex-col gap-[15px] compact-form">
        <label><span>Current password</span><PasswordInput name="old_password" required maxLength={128} autoComplete="current-password" /></label>
        <label><span>New password</span><PasswordInput name="new_password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
        <label><span>Confirm new password</span><PasswordInput name="confirm_password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
        <p className="text-xs text-muted">Use 12–128 characters. You’ll sign in again after saving. Other sessions cannot renew access; existing access tokens expire normally.</p>
        <button className="button button-secondary mt-auto" type="submit">{changingPassword ? 'Updating password…' : 'Update password'}</button>
      </fieldset></form></section>
    </div>
  </>;
}
