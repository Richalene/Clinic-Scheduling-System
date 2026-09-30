import { ArrowRight, CalendarCheck2, Clock3, UsersRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Brand } from './components';

export default function Landing({ user }) {
  const destination = user ? '/app/book' : '/login';
  return <>
    <header className="site-header"><Brand /><nav className="main-nav" aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#for-teams">For your team</a></nav>
      <div className="header-actions"><Link className="text-link" to={user ? '/app' : '/login'}>{user ? 'Your dashboard' : 'Sign in'}</Link><Link className="button button-primary button-small" to={destination}>Book a visit <ArrowRight size={16} /></Link></div>
    </header>
    <main id="main-content"><section className="hero">
      <div className="hero-copy"><p className="eyebrow">Princeton-Plainsboro Teaching Hospital</p><h1>Your next visit<br />starts here.</h1><p className="hero-text">Choose your doctor, find an available time, and manage your appointments with PPTH.</p>
        <div className="hero-actions"><Link className="button button-primary" to={destination}>Find your appointment <ArrowRight size={18} /></Link><a className="button button-secondary" href="#how-it-works">See how it works</a></div>

      </div>
      <div className="hero-visual" aria-hidden="true">
        <div className="hero-photo" style={{ backgroundImage: `url("${import.meta.env.BASE_URL}images/ppth-hero.jpg")` }} />
        <div className="hero-photo-fade" />
      </div>
    </section>
    <section className="booking-wrap"><div><p className="eyebrow">Appointments</p><h2>Schedule a hospital visit</h2><p>Choose a service and explore times that work for you.</p></div><Link className="button button-primary" to={destination}>Explore available times <ArrowRight size={18} /></Link></section>
    <section className="section" id="how-it-works"><div className="section-heading"><div><p className="eyebrow">Patient guide</p><h2>How to book</h2></div><p>Book online and view your appointment details in your account.</p></div>
      <div className="service-grid mx-auto grid max-w-[1280px] grid-cols-3 gap-[18px] max-[980px]:grid-cols-1">{[
        [Clock3, '01', 'Find your time', 'Choose your service and see available appointments that fit your day.', 'sage'],
        [CalendarCheck2, '02', 'Book with confidence', 'Your clinic checks the room and care team before confirming your visit.', 'blue'],
        [UsersRound, '03', 'Stay connected', 'See upcoming visits and cancel an appointment when your plans change.', 'peach'],
      ].map(([Icon, number, title, copy, color]) => <article className={`service-card service-card-${color}`} key={number}><span className="service-number">{number}</span><span className={`service-icon ${color}`}><Icon size={25} strokeWidth={1.5} /></span><h3>{title}</h3><p>{copy}</p></article>)}</div>
    </section>
    <section className="cta-section" id="for-teams"><div><p className="eyebrow light">Staff access</p><h2>Manage the hospital schedule</h2><p>Bring appointments, staff shifts, rooms, and equipment together in one coordinated workspace.</p></div><Link className="button button-light" to={user ? '/app' : '/login'}>Open your workspace <ArrowRight size={18} /></Link></section>
    </main><footer className="site-footer"><Brand /><p>Patient appointments and staff scheduling.</p><Link className="text-link" to={destination}>Plan your next visit →</Link><small>© {new Date().getFullYear()} Princeton-Plainsboro Teaching Hospital (PPTH) · Clinic Workforce Scheduling System</small></footer>
  </>;
}
