import { useEffect, useState } from 'react';
import { ArrowUpRight, CalendarDays, ClipboardList, LayoutDashboard, LogOut, Package, Plus, UsersRound, UserRound, ShieldCheck } from 'lucide-react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { clearSession, logout, refreshSession, request } from './api';
import { Brand, Loading } from './components';
import { CatalogProvider } from './data';
import { initials, label } from './format';
import Auth from './Auth';
import Landing from './Landing';
import Dashboard from './Dashboard';
import Appointments from './Appointments';
import Booking from './Booking';
import Schedule from './Schedule';
import Resources from './Resources';
import Profile from './Profile';
import Accounts from './Accounts';
import PatientAccounts from './CreateAccount';

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [message, setMessage] = useState('');
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    refreshSession().then(() => request('/users/me')).then((profile) => { if (active) setUser(profile); })
      .catch(() => { /* A missing refresh cookie is normal before the first sign-in. */ })
      .finally(() => { if (active) setBooting(false); });
    const expired = () => { setUser(null); setMessage('Your session has expired. Please sign in again.'); };
    window.addEventListener('clinic:session-expired', expired);
    return () => { active = false; window.removeEventListener('clinic:session-expired', expired); };
  }, []);
  async function signOut() {
    let warning = '';
    try { await logout(); } catch { warning = 'Signed out on this screen. We could not end the server session; close this browser if you are on a shared device.'; }
    clearSession(); setUser(null); setMessage(warning); navigate('/login', { replace: true });
  }
  if (booting) return <div className="boot-screen flex min-h-screen flex-col items-center justify-center"><Brand /><Loading>Getting your workspace ready…</Loading></div>;
  return <><a className="skip-link" href="#main-content">Skip to content</a><Routes>
    <Route path="/" element={<Landing user={user} />} />
    <Route path="/login" element={user ? <Navigate to="/app" replace /> : <Auth sessionMessage={message} onLogin={(profile) => { setUser(profile); setMessage(''); }} />} />
    <Route path="/app/*" element={user ? <Workspace user={user} onLogout={signOut} onUpdated={setUser} onPasswordChanged={() => { clearSession(); setUser(null); setMessage('Password updated. Please sign in with your new password.'); navigate('/login', { replace: true }); }} /> : <Navigate to="/login" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></>;
}

function Workspace({ user, onLogout, onUpdated, onPasswordChanged }) {
  const [loggingOut, setLoggingOut] = useState(false);
  const staff = user.role !== 'patient';
  return <div className="dashboard-body"><aside className="sidebar"><div className="sidebar-scroll"><div className="sidebar-brand"><Brand /></div><p className="nav-label">Your workspace</p><nav className="side-nav" aria-label="Workspace navigation">
    {[[LayoutDashboard, 'Overview', '/app'], [ClipboardList, 'Appointments', '/app/appointments'], [UserRound, 'My profile', '/app/profile'], ...(user.role === 'administrator' ? [[ShieldCheck, 'Accounts', '/app/accounts']] : []), ...(user.role === 'receptionist' ? [[UsersRound, 'Add patient account', '/app/patient-accounts']] : []), ...(staff ? [[CalendarDays, 'Team schedule', '/app/schedule'], [Package, 'Resources', '/app/resources']] : [])].map(([Icon, title, to]) => <NavLink end={to === '/app'} key={to} to={to}><Icon size={19} /><span>{title}</span></NavLink>)}
  </nav></div><div className="sidebar-footer"><div className="mini-profile"><span>{user.profile_picture ? <img className="h-full w-full rounded-full object-cover" src={user.profile_picture} alt="Your profile" /> : initials(user.full_name)}</span><p><strong>{user.full_name}</strong><small>{label(user.role)}</small></p></div><button className="logout-button" disabled={loggingOut} onClick={async () => { setLoggingOut(true); await onLogout(); }}><LogOut size={16} />{loggingOut ? 'Signing out…' : 'Sign out'}</button></div></aside>
    <main className="dashboard-main" id="main-content"><CatalogProvider><Routes>
      <Route path="patient-accounts" element={user.role === 'receptionist' ? <PatientAccounts /> : <Navigate to="/app" replace />} /><Route path="profile" element={<Profile user={user} onUpdated={onUpdated} onPasswordChanged={onPasswordChanged} />} /><Route path="accounts" element={user.role === 'administrator' ? <Accounts user={user} onUpdated={onUpdated} /> : <Navigate to="/app" replace />} /><Route index element={<Dashboard user={user} />} /><Route path="appointments" element={<Appointments user={user} />} />
      <Route path="book" element={<Booking user={user} />} /><Route path="schedule" element={staff ? <Schedule user={user} /> : <Navigate to="/app" replace />} />
      <Route path="resources" element={staff ? <Resources /> : <Navigate to="/app" replace />} /><Route path="*" element={<Navigate to="/app" replace />} />
    </Routes></CatalogProvider><footer className="workspace-footer"><span>PPTH · A little more time for care.</span><Link to="/app/book"><Plus size={13} /> New appointment</Link></footer></main>
  </div>;
}
