import { useState } from 'react';
import { ArrowLeft, ArrowRight, CalendarDays, ShieldCheck, UsersRound } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import PasswordInput from './PasswordInput';
import { login, request } from './api';
import { Brand, Notice } from './components';

export default function Auth({ onLogin, sessionMessage }) {
  const [register, setRegister] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  async function submit(event) {
    event.preventDefault();
    setError(''); setSuccess(''); setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      if (register) {
        await request('/users/register', { method: 'POST', authenticated: false, body: JSON.stringify({
          full_name: form.get('name').trim(), email: form.get('email').trim(), password: form.get('password'), role: 'patient',
        }) });
        setRegister(false); setSuccess('Your patient account is ready. Sign in to book your first visit.');
      } else {
        const user = await login(form.get('email').trim(), form.get('password'));
        onLogin(user); navigate('/app', { replace: true });
      }
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <main className="auth-shell" id="main-content"><section className="auth-brand-panel"><Brand light /><div className="auth-message"><p className="eyebrow light">PPTH patient and staff portal</p><h1>Hospital scheduling.<br />One place to manage it.</h1><p>Access appointments, staff schedules, and hospital resources.</p></div><div className="auth-feature-list">{[
    [CalendarDays, 'A clearer view of your day', 'Keep every appointment in one place.'],
    [UsersRound, 'Care that works together', 'Coordinate the people and spaces you need.'],
    [ShieldCheck, 'Your own clinic workspace', 'Sign in for access tailored to your role.'],
  ].map(([Icon, title, copy]) => <div key={title}><span><Icon size={16} /></span><p><strong>{title}</strong><small>{copy}</small></p></div>)}</div></section>
    <section className="auth-form-panel"><Link className="back-link" to="/"><ArrowLeft size={15} /> Back to home</Link><div className="login-card"><div className="login-heading"><p className="eyebrow">Account access</p><h2>{register ? 'Create an account' : 'Welcome back.'}</h2><p>{register ? 'Create a patient account to plan your next visit.' : 'Sign in with your hospital account.'}</p></div>
      <Notice>{error || (!success && sessionMessage)}</Notice><Notice kind="success">{success}</Notice>
      <form onSubmit={submit}><fieldset disabled={busy}>{register && <label className="form-field"><span>Full name</span><input name="name" autoComplete="name" required minLength={2} maxLength={255} /></label>}
        <label className="form-field"><span>Email address</span><input name="email" type="email" autoComplete="username" placeholder="you@example.com" required /></label>
        <label className="form-field"><span>Password</span><PasswordInput name="password" autoComplete={register ? 'new-password' : 'current-password'} required minLength={register ? 12 : undefined} maxLength={128} />{register && <small>Use at least 12 characters.</small>}</label>
        <button className="button button-primary login-button" type="submit">{busy ? 'Please wait…' : register ? 'Create patient account' : 'Sign in'}{!busy && <ArrowRight size={18} />}</button>
      </fieldset></form><p className="auth-switch">{register ? 'Already have an account?' : 'New to the clinic?'} <button className="text-button" disabled={busy} onClick={() => { setRegister(!register); setError(''); setSuccess(''); }}>{register ? 'Sign in' : 'Create a patient account'}</button></p>
    </div><p className="auth-help">Need help with your account? Contact your clinic administrator.</p></section>
  </main>;
}
