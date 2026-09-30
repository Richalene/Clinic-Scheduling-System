import { test, expect } from '@playwright/test';

// Browser tests intercept the API; they never write into the real clinic DB.
async function clinicApi(page) {
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); tomorrow.setHours(10, 0, 0, 0);
  const user = { user_id: 3, full_name: 'Mary Santos', role: 'patient', patient_id: 1, staff_id: null };
  const slot = { candidate_start: tomorrow.toISOString(), candidate_end: new Date(+tomorrow + 1800000).toISOString(), room_id: 1, doctor_id: 1, nurse_id: null, equipment_ids: [] };
  let appointments = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    let result;
    if (path === '/auth/refresh') return route.fulfill({ status: 401, json: { detail: 'Refresh token missing' } });
    if (path === '/auth/login') result = { access_token: 'test-access-token', token_type: 'bearer' };
    else if (path === '/auth/logout') result = { detail: 'Successfully logged out' };
    else if (path === '/users/me') result = user;
    else if (path === '/services/') result = [{ service_id: 1, service_name: 'Consultation', duration_minutes: 30, requires_nurse: false, room_type: 'Consultation room' }];
    else if (path === '/patients/') result = [{ patient_id: 1, patient_name: user.full_name }];
    else if (path === '/rooms/') result = [{ room_id: 1, room_name: 'Room 101', room_type: 'Consultation room', status: 'available' }];
    else if (path === '/equipment/') result = [];
    else if (path === '/staff/') result = [];
    else if (path === '/appointments/availability') result = [slot];
    else if (path === '/appointments/' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      expect(body).toMatchObject({ patient_id: 1, service_id: 1, equipment_ids: [] });
      result = { ...body, appointment_id: 7, status: 'confirmed', room_id: 1, end_at: slot.candidate_end,
        patient: { patient_name: user.full_name }, service: { service_name: 'Consultation' }, room: { room_name: 'Room 101' }, assigned_staff: [{ staff_id: 1 }], assigned_equipment: [] };
      appointments.push(result);
    } else if (path === '/appointments/7/cancel') {
      appointments = appointments.map((appointment) => ({ ...appointment, status: 'cancelled' }));
      result = appointments[0];
    } else if (path === '/appointments/') result = appointments;
    else return route.fulfill({ status: 404, json: { detail: `Unexpected test endpoint ${path}` } });
    return route.fulfill({ json: result });
  });
}

test('landing, sign-in, booking, cancellation and logout', async ({ page }) => {
  await clinicApi(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Good care. Better connected.' })).toBeVisible();
  await page.screenshot({ path: 'test-results/landing-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Sign in', exact: true }).click();
  await page.screenshot({ path: 'test-results/login-desktop.png', fullPage: true });
  await page.getByLabel('Email address').fill('mary@example.com');
  await page.getByLabel('Password', { exact: true }).fill('test-long-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Hello, Mary.' })).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'New appointment', exact: true }).first().click();
  await page.getByLabel('Service', { exact: true }).selectOption('1');
  await page.getByRole('button', { name: 'Find available times' }).click();
  await page.locator('.slot').first().click();
  await page.screenshot({ path: 'test-results/booking-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Confirm appointment' }).click();
  await expect(page.getByText(/Appointment confirmed for/)).toBeVisible();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByRole('button', { name: 'Cancel appointment 7' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Confirm cancellation' }).click();
  await expect(page.locator('tbody .status')).toHaveText('cancelled');
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible();
});

test('mobile pages fit the viewport and keep navigation accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await clinicApi(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Good care. Better connected.' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/landing-mobile.png', fullPage: true });
  await page.getByRole('link', { name: 'Book a visit' }).click();
  await page.getByLabel('Email address').fill('mary@example.com');
  await page.getByLabel('Password', { exact: true }).fill('test-long-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Hello, Mary.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/dashboard-mobile.png', fullPage: true });
});
