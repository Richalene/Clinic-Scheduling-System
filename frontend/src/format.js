export const label = (value = '') => value.replaceAll('_', ' ');
export const dateLabel = (value, options = {}) => new Date(value).toLocaleDateString(undefined, {
  month: 'short', day: 'numeric', year: 'numeric', ...options,
});
export const timeLabel = (value) => new Date(value).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
export const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
export function localDate(value = new Date()) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
export function searchWindow(day, from, to) {
  const start = new Date(`${day}T${from}`);
  const end = new Date(`${day}T${to}`);
  if (!Number.isFinite(+start) || !Number.isFinite(+end) || start >= end) throw new Error('Choose an end time after the start time.');
  if (start <= new Date()) throw new Error('Choose a start time in the future.');
  return { from_time: start.toISOString(), to_time: end.toISOString() };
}
export const initials = (name = '') => name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase();
