import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CalendarDays, LoaderCircle, X } from 'lucide-react';
import { label } from './format';

export function Brand({ light = false }) {
  return <Link to="/" className={`brand ${light ? 'auth-brand' : ''}`} aria-label="Princeton-Plainsboro Teaching Hospital (PPTH) home">
    <span className={`brand-mark ${light ? 'brand-mark-light' : ''}`} aria-hidden="true"><i /><i /></span>
    <span><strong>PPTH</strong><small>Princeton-Plainsboro<br />Teaching Hospital</small></span>
  </Link>;
}

export function Notice({ children, kind = 'error' }) {
  if (!children) return null;
  return <div className={`notice ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <AlertCircle size={18} aria-hidden="true" /><span>{children}</span>
  </div>;
}

export function Loading({ children = 'Loading your clinic…' }) {
  return <div className="loading flex items-center justify-center gap-3 px-5 py-[70px] text-sm text-muted" role="status"><LoaderCircle className="spin" size={22} /><span>{children}</span></div>;
}

export function Empty({ title, children, action }) {
  return <div className="empty"><CalendarDays size={30} strokeWidth={1.4} aria-hidden="true" />
    <h3>{title}</h3><p>{children}</p>{action}</div>;
}

export function Status({ value }) {
  return <span className={`status ${value}`}>{value === 'requested' ? 'Awaiting review' : label(value)}</span>;
}

export function PageHeading({ eyebrow, title, children, action }) {
  return <header className="dashboard-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{children && <p>{children}</p>}</div>{action}</header>;
}

export function Modal({ title, children, onClose, busy = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="modal" aria-labelledby="modal-title" onCancel={(event) => {
    event.preventDefault();
    if (!busy) onClose();
  }}><div className="panel-heading"><h2 id="modal-title">{title}</h2>
    <button type="button" className="icon-button" aria-label="Close dialog" disabled={busy} onClick={onClose}><X size={20} /></button>
  </div>{children}</dialog>;
}
