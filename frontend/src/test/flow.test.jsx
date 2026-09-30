import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import * as api from '../api';

vi.mock('../api', () => ({
  all: vi.fn(), request: vi.fn(), login: vi.fn(), logout: vi.fn(),
  post: vi.fn(), refreshSession: vi.fn(), clearSession: vi.fn(),
}));

const patient = { user_id: 3, full_name: 'Mary Santos', email: 'mary@example.com', phone_number: '09171234567', role: 'patient', patient_id: 1, staff_id: null };
const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); tomorrow.setHours(10, 0, 0, 0);
const slot = { candidate_start: tomorrow.toISOString(), candidate_end: new Date(+tomorrow + 1800000).toISOString(), room_id: 1, doctor_id: 1, nurse_id: null, equipment_ids: [] };
const appointment = {
  appointment_id: 7, patient_id: 1, service_id: 1, room_id: 1,
  start_at: slot.candidate_start, end_at: slot.candidate_end, status: 'confirmed', priority: 'normal',
  patient: { patient_name: 'Mary Santos' }, service: { service_name: 'Consultation' },
  room: { room_name: 'Room 101' }, assigned_staff: [{ staff_id: 1 }], assigned_equipment: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.refreshSession.mockRejectedValue(new Error('No cookie'));
  api.login.mockResolvedValue(patient);
  api.all.mockImplementation(async (path) => ({
    '/services/': [{ service_id: 1, service_name: 'Consultation', duration_minutes: 30, requires_nurse: false, room_type: 'Consultation room' }],
    '/patients/': [{ patient_id: 1, patient_name: 'Mary Santos' }],
    '/rooms/': [{ room_id: 1, room_name: 'Room 101' }], '/equipment/': [], '/staff/': [],
    '/appointments/': [], '/shifts/': [],
  }[path] || []));
  api.request.mockImplementation(async (path) => path.startsWith('/appointments/availability') ? [slot] : null);
  api.post.mockResolvedValue(appointment);
});

async function signIn() {
  const user = userEvent.setup();
  render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>);
  await user.type(await screen.findByLabelText('Email address'), 'mary@example.com');
  await user.type(screen.getByLabelText('Password'), 'a-long-password');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await screen.findByRole('heading', { name: 'Hello, Mary.' });
  return user;
}

it('signs in a patient and books a real returned slot', async () => {
  const user = await signIn();
  expect(screen.queryByRole('link', { name: 'Team schedule' })).not.toBeInTheDocument();
  await user.click(screen.getAllByRole('link', { name: 'New appointment', exact: true })[0]);
  await user.selectOptions(screen.getByLabelText('Service', { selector: 'select' }), '1');
  await user.click(screen.getByRole('button', { name: 'Find available times' }));
  const time = await screen.findByRole('button', { pressed: false });
  await user.click(time);
  await user.click(screen.getByRole('button', { name: 'Request appointment' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/appointments/', expect.objectContaining({
    patient_id: 1, service_id: 1, start_at: slot.candidate_start, equipment_ids: [], priority: 'normal',
  })));
  expect(await screen.findByText(/Appointment confirmed for/)).toBeInTheDocument();
});

it('invalidates a selected slot when the date changes', async () => {
  const user = await signIn();
  await user.click(screen.getAllByRole('link', { name: 'New appointment', exact: true })[0]);
  await user.selectOptions(screen.getByLabelText('Service', { selector: 'select' }), '1');
  await user.click(screen.getByRole('button', { name: 'Find available times' }));
  await user.click(await screen.findByRole('button', { pressed: false }));
  expect(screen.getByRole('button', { name: 'Request appointment' })).toBeInTheDocument();
  await user.clear(screen.getByLabelText('Preferred date'));
  expect(screen.queryByRole('button', { name: 'Request appointment' })).not.toBeInTheDocument();
});

it('shows conflicts and requires a fresh search before booking again', async () => {
  api.post.mockRejectedValue(Object.assign(new Error('Resource conflict'), { status: 409 }));
  const user = await signIn();
  await user.click(screen.getAllByRole('link', { name: 'New appointment', exact: true })[0]);
  await user.selectOptions(screen.getByLabelText('Service', { selector: 'select' }), '1');
  await user.click(screen.getByRole('button', { name: 'Find available times' }));
  await user.click(await screen.findByRole('button', { pressed: false }));
  await user.click(screen.getByRole('button', { name: 'Request appointment' }));
  expect(await screen.findByText(/That time is no longer available/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Request appointment' })).not.toBeInTheDocument();
});

it('requires confirmation before cancelling an appointment', async () => {
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/appointments/' ? Promise.resolve([appointment]) : original(path));
  api.request.mockResolvedValue({ ...appointment, status: 'cancelled' });
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Appointments', exact: true }));
  await user.click(await screen.findByRole('button', { name: 'Cancel appointment 7' }));
  const dialog = screen.getByRole('dialog');
  expect(api.request).not.toHaveBeenCalledWith('/appointments/7/cancel', expect.anything());
  await user.click(within(dialog).getByRole('button', { name: 'Confirm cancellation' }));
  await waitFor(() => expect(api.request).toHaveBeenCalledWith('/appointments/7/cancel', { method: 'POST' }));
  expect(await screen.findByText('cancelled', { selector: '.status' })).toBeInTheDocument();
});


it('saves a profile and updates the signed-in user display', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'My profile' }));
  const name = screen.getByLabelText('Full name');
  await user.clear(name);
  await user.type(name, 'Maria Santos');
  api.request.mockResolvedValue({ ...patient, full_name: 'Maria Santos' });
  await user.click(screen.getByRole('button', { name: 'Save profile' }));
  await waitFor(() => expect(api.request).toHaveBeenCalledWith('/users/me', {
    method: 'PATCH', body: JSON.stringify({ full_name: 'Maria Santos', email: 'mary@example.com', phone_number: '09171234567' }),
  }));
  expect(await screen.findByText('Your profile has been saved.')).toBeInTheDocument();
  expect(screen.getByText('Maria Santos', { selector: '.mini-profile strong' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Accounts' })).not.toBeInTheDocument();
});

it('requires matching passwords and returns to sign-in after changing one', async () => {
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'My profile' }));
  await user.type(screen.getByLabelText('Current password'), 'OriginalPassword123!');
  await user.type(screen.getByLabelText('New password', { exact: true }), 'ReplacementPassword123!');
  await user.type(screen.getByLabelText('Confirm new password'), 'DifferentPassword123!');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(await screen.findByText('The new passwords do not match.')).toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalled();
  await user.clear(screen.getByLabelText('Confirm new password'));
  await user.type(screen.getByLabelText('Confirm new password'), 'ReplacementPassword123!');
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith('/auth/change-password', { old_password: 'OriginalPassword123!', new_password: 'ReplacementPassword123!' });
});

it('lets an administrator deactivate another account', async () => {
  api.login.mockResolvedValue({ ...patient, user_id: 7, role: 'administrator', patient_id: null });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/users/' ? Promise.resolve([{ ...patient, is_active: true }]) : original(path));
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Accounts', exact: true }));
  await user.click(await screen.findByRole('button', { name: 'Manage Mary Santos' }));
  await user.click(screen.getByRole('button', { name: 'Edit details' }));
  const dialog = screen.getByRole('dialog');
  await user.click(within(dialog).getByLabelText('Account is active'));
  api.request.mockResolvedValue({ ...patient, is_active: false });
  await user.click(within(dialog).getByRole('button', { name: 'Save account' }));
  expect(api.request).not.toHaveBeenCalledWith('/users/3', expect.anything());
  await user.click(screen.getByRole('button', { name: 'Back to editing' }));
  expect(screen.getByLabelText('Account is active')).not.toBeChecked();
  await user.click(screen.getByRole('button', { name: 'Save account' }));
  await user.click(screen.getByRole('button', { name: 'Confirm deactivation' }));
  expect(await screen.findByText('Inactive', { selector: '.status' })).toBeInTheDocument();
  expect(api.request).toHaveBeenCalledWith('/users/3', expect.objectContaining({ method: 'PATCH' }));
});


it('combines account filters and shows linked profile details', async () => {
  api.login.mockResolvedValue({ ...patient, user_id: 7, role: 'administrator' });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => {
    if (path === '/users/') return Promise.resolve([{ ...patient, is_active: true }, { user_id: 9, full_name: 'Doctor Lee', email: 'lee@example.com', role: 'doctor', is_active: false }]);
    if (path === '/patients/') return Promise.resolve([{ user_id: 3, patient_id: 1, patient_name: 'Mary Santos', phone_number: '09171234567' }]);
    return original(path);
  });
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Accounts' }));
  await screen.findByRole('button', { name: 'Manage Doctor Lee' });
  await user.selectOptions(screen.getByLabelText('Filter by role'), 'doctor');
  await user.selectOptions(screen.getByLabelText('Filter by status'), 'inactive');
  expect(screen.getByText('1 of 2 accounts')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Manage Mary Santos' })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText('Search accounts'), 'Mary');
  expect(screen.getByText('No matching accounts.')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Clear filters' }));
  await user.click(screen.getByRole('button', { name: 'Manage Mary Santos' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('Patient #1')).toBeInTheDocument();
  expect(within(dialog).getByText('09171234567')).toBeInTheDocument();
  await user.click(within(dialog).getByRole('button', { name: 'Close dialog' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});


it('keeps controls inside Manage and confirms status changes', async () => {
  const admin = { ...patient, user_id: 7, full_name: 'Mary Admin', role: 'administrator', is_active: true };
  api.login.mockResolvedValue(admin);
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/users/' ? Promise.resolve([admin, { ...patient, is_active: true }]) : original(path));
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Accounts' }));
  await screen.findByRole('button', { name: 'Manage Mary Santos' });
  expect(screen.queryByRole('switch')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Delete Mary Santos' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Manage Mary Admin' }));
  expect(screen.getByRole('switch')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Delete Mary Admin' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Close dialog' }));
  await user.click(screen.getByRole('button', { name: 'Manage Mary Santos' }));
  await user.click(screen.getByRole('switch'));
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.getByRole('switch')).toBeChecked();
  await user.click(screen.getByRole('switch'));
  api.request.mockRejectedValueOnce(new Error('Could not save status'));
  await user.click(screen.getByRole('button', { name: 'Confirm deactivation' }));
  expect(await screen.findByText('Could not save status')).toBeInTheDocument();
  api.request.mockResolvedValueOnce({ ...patient, is_active: false });
  await user.click(screen.getByRole('button', { name: 'Confirm deactivation' }));
  await waitFor(() => expect(screen.getByRole('switch')).not.toBeChecked());
  api.request.mockResolvedValueOnce({ ...patient, is_active: true });
  await user.click(screen.getByRole('switch'));
  await waitFor(() => expect(screen.getByRole('switch')).toBeChecked());
});

it('requires administrator password for deletion inside Manage and displays blocked errors', async () => {
  api.login.mockResolvedValue({ ...patient, user_id: 7, role: 'administrator' });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/users/' ? Promise.resolve([{ ...patient, is_active: true }]) : original(path));
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Accounts' }));
  await user.click(await screen.findByRole('button', { name: 'Manage Mary Santos' }));
  await user.click(screen.getByRole('button', { name: 'Delete Mary Santos' }));
  expect(screen.getByRole('button', { name: 'Permanently delete' })).toBeDisabled();
  await user.type(screen.getByLabelText('Your administrator password'), 'AdminPassword123!');
  api.request.mockRejectedValueOnce(new Error('Account has history'));
  await user.click(screen.getByRole('button', { name: 'Permanently delete' }));
  expect(await screen.findByText('Account has history')).toBeInTheDocument();
  expect(screen.getByLabelText('Your administrator password')).toHaveValue('');
  await user.type(screen.getByLabelText('Your administrator password'), 'AdminPassword123!');
  api.request.mockResolvedValueOnce({ detail: 'Unused account deleted' });
  await user.click(screen.getByRole('button', { name: 'Permanently delete' }));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Manage Mary Santos' })).not.toBeInTheDocument());
});


it('lets reception create a patient login without administrator controls', async () => {
  api.login.mockResolvedValue({ ...patient, role: 'receptionist' });
  api.post.mockResolvedValue({ user_id: 10, full_name: 'New Patient' });
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Add patient account' }));
  expect(screen.queryByRole('link', { name: 'Accounts' })).not.toBeInTheDocument();
  await user.type(screen.getByLabelText('Full name'), 'New Patient');
  await user.type(screen.getByLabelText('Email address'), 'new@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'PatientPassword123!');
  await user.click(screen.getByRole('button', { name: 'Create patient account' }));
  expect(await screen.findByText(/Account created for New Patient/)).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith('/users/patient-accounts', { full_name: 'New Patient', email: 'new@example.com', password: 'PatientPassword123!', phone_number: null });
});

it('creates a doctor with a linked department from administrator Accounts', async () => {
  api.login.mockResolvedValue({ ...patient, role: 'administrator' });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/staff/departments' ? Promise.resolve([{ department_id: 1, department_name: 'General' }]) : original(path));
  api.post.mockResolvedValue({ user_id: 10, full_name: 'Dr. Alex', email: 'alex@example.com', role: 'doctor', is_active: true });
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Accounts' }));
  await user.click(screen.getByRole('button', { name: 'Add staff account' }));
  await user.type(screen.getByLabelText('Full name'), 'Dr. Alex');
  await user.type(screen.getByLabelText('Email address'), 'alex@example.com');
  await user.type(screen.getByLabelText('Initial password'), 'DoctorPassword123!');
  await user.selectOptions(screen.getByLabelText('Department'), '1');
  await user.click(screen.getByRole('button', { name: 'Create staff account' }));
  expect(await screen.findByText('Staff account created for Dr. Alex.')).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith('/users/staff-accounts', expect.objectContaining({ role: 'doctor', department_id: 1 }));
});


it('sends the chosen doctor for both slot search and booking and clears stale slots', async () => {
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/staff/' ? Promise.resolve([{ staff_id: 1, profession: 'doctor', user: { full_name: 'Dr. Charlie' } }]) : original(path));
  const user = await signIn();
  await user.click(screen.getAllByRole('link', { name: 'New appointment', exact: true })[0]);
  await user.selectOptions(screen.getByLabelText('Service', { selector: 'select' }), '1');
  await user.selectOptions(screen.getByLabelText('Doctor', { selector: 'select' }), '1');
  await user.click(screen.getByRole('button', { name: 'Find available times' }));
  await user.click(await screen.findByRole('button', { pressed: false }));
  expect(api.request).toHaveBeenCalledWith(expect.stringContaining('doctor_id=1'));
  await user.selectOptions(screen.getByLabelText('Doctor', { selector: 'select' }), '');
  expect(screen.queryByRole('button', { name: 'Request appointment' })).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Doctor', { selector: 'select' }), '1');
  await user.click(screen.getByRole('button', { name: 'Find available times' }));
  await user.click(await screen.findByRole('button', { pressed: false }));
  await user.click(screen.getByRole('button', { name: 'Request appointment' }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/appointments/', expect.objectContaining({ doctor_id: 1 })));
});


it('lets the assigned doctor accept a pending request after confirmation', async () => {
  api.login.mockResolvedValue({ ...patient, role: 'doctor', staff_id: 1 });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/appointments/' ? Promise.resolve([{ ...appointment, status: 'requested' }]) : original(path));
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Appointments', exact: true }));
  await user.click(await screen.findByRole('button', { name: 'Accept appointment 7' }));
  expect(api.request).not.toHaveBeenCalledWith('/appointments/7/approve', expect.anything());
  api.request.mockResolvedValueOnce(appointment);
  await user.click(screen.getByRole('button', { name: 'Confirm acceptance' }));
  expect(await screen.findByText('Appointment accepted and confirmed.')).toBeInTheDocument();
  expect(api.request).toHaveBeenCalledWith('/appointments/7/approve', { method: 'POST' });
  expect(screen.queryByRole('button', { name: 'Accept appointment 7' })).not.toBeInTheDocument();
});

it('lets reception reject a pending appointment', async () => {
  api.login.mockResolvedValue({ ...patient, role: 'receptionist' });
  const original = api.all.getMockImplementation();
  api.all.mockImplementation((path) => path === '/appointments/' ? Promise.resolve([{ ...appointment, status: 'requested' }]) : original(path));
  const user = await signIn();
  await user.click(screen.getByRole('link', { name: 'Appointments', exact: true }));
  await user.click(await screen.findByRole('button', { name: 'Reject appointment 7' }));
  api.request.mockResolvedValueOnce({ ...appointment, status: 'cancelled' });
  await user.click(screen.getByRole('button', { name: 'Confirm rejection' }));
  expect(await screen.findByText('Appointment rejected. Reservations released.')).toBeInTheDocument();
});
