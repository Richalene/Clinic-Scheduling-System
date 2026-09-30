import { useState } from 'react';
import { DoorOpen, HeartPulse, Stethoscope, UsersRound } from 'lucide-react';
import { Empty, PageHeading, Status } from './components';
import { useCatalogs } from './data';
import { initials } from './format';

export default function Resources() {
  const data = useCatalogs();
  const [tab, setTab] = useState('services');
  const tabs = [['services', 'Services', HeartPulse], ['rooms', 'Rooms', DoorOpen], ['equipment', 'Equipment', Stethoscope], ['staff', 'Care team', UsersRound]];
  return <><PageHeading eyebrow="Directory" title="Clinic resources">A shared directory of your services, rooms, equipment, and care team.</PageHeading>
    <div className="resource-tabs" role="tablist" aria-label="Resource type">{tabs.map(([value, title, Icon]) => <button id={`tab-${value}`} role="tab" aria-controls={`panel-${value}`} aria-selected={tab === value} key={value} onClick={() => setTab(value)}><Icon size={18} />{title}<span>{data[value].length}</span></button>)}</div>
    <section role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="resource-grid grid grid-cols-3 gap-[18px] max-[1180px]:grid-cols-2 max-[600px]:grid-cols-1">{!data[tab].length ? <Empty title="Nothing listed yet.">Your clinic’s resources will appear here when they are added.</Empty> : data[tab].map((item) => {
      if (tab === 'services') return <article className="dash-panel resource-card" key={item.service_id}><span className="service-icon sage"><HeartPulse size={24} /></span><h3>{item.service_name}</h3><p>{item.duration_minutes} minutes · {item.room_type}</p><div className="resource-footer">Doctor{item.requires_nurse ? ' + nurse' : ''} required</div></article>;
      if (tab === 'staff') return <article className="dash-panel resource-card" key={item.staff_id}><span className="large-avatar">{initials(item.user.full_name)}</span><h3>{item.user.full_name}</h3><p className="capitalize">{item.profession} · {item.department.department_name}</p><div className="resource-footer">{item.qualification || 'Qualification not listed'}</div></article>;
      return <article className="dash-panel resource-card" key={item.room_id || item.equipment_id}><span className={`service-icon ${tab === 'rooms' ? 'blue' : 'peach'}`}>{tab === 'rooms' ? <DoorOpen size={24} /> : <Stethoscope size={24} />}</span><h3>{item.room_name || item.equipment_name}</h3><p>{item.room_type || item.equipment_type}</p><div className="resource-footer"><Status value={item.status} /></div></article>;
    })}</section><p className="panel-footnote">An available resource can still be reserved at a particular time. Search appointment availability to check a time slot.</p>
  </>;
}
