# ClinicFlow frontend

React + Vite + Tailwind CSS v4 frontend for the existing FastAPI scheduling backend. The styling
follows the supplied ivory/teal reference, using locally bundled Playfair
Display and DM Sans fonts. All authenticated screens use the API; sample data
exists only inside tests.

## Styling with Tailwind

Tailwind runs through `@tailwindcss/vite` in `vite.config.js`; no separate
PostCSS or JavaScript Tailwind config is needed. `src/styles.css` imports
Tailwind and defines the reference palette and fonts using `@theme inline`.
Use utilities such as `bg-paper`, `text-ink`, `text-muted`, `bg-teal`,
`font-serif`, `font-sans`, and `shadow-clinic` in JSX.

Page grids use responsive utility classes directly. Shared buttons, form
controls, cards, and other repeated patterns use `@apply` inside
`@layer components`, so JSX utilities can override them normally. The
decorative clinician illustration and complex visual effects remain custom
CSS. The ivory/teal appearance and responsive breakpoints follow the reference.

## Run locally

Use Node.js 24 (the version used to build and test this app).

```powershell
cd frontend
npm ci
npm run dev
```

Once dependencies are installed, normal startup is just `npm run dev`.
**Stop all Vite/build/test processes for this frontend before running `npm ci`**
(Ctrl+C in their terminals). On Windows, a running process can lock Tailwind
or Rolldown native files. `npm ci` then fails with `EPERM` after partially
removing dependencies; a later startup may report a missing React plugin.
If that happens, stop those processes and run `npm ci --include=dev` once,
then `npm run dev`. Do not reinstall while another frontend server is running.

Open **http://localhost:5173**. Keep the FastAPI server running on port 8000:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

The frontend proxies `/api/*` to `http://127.0.0.1:8000/*`. No frontend `.env`
file is needed for these defaults. To change the backend target, copy
`.env.example` to `.env`, edit `API_PROXY_TARGET`, and restart Vite. Never copy
backend secrets into frontend environment variables.

Sign in with an existing clinic account, or use **Create a patient account**.
Staff accounts are created by the clinic administrator through the existing
backend. There are no built-in demo credentials or fabricated appointments.

## Screens and supported actions

| Route | Behavior |
| --- | --- |
| `/` | Public landing page based on the design reference |
| `/login` | Sign in and patient self-registration |
| `/app` | Live appointment counts and upcoming visits |
| `/app/appointments` | Search/filter appointments, page through results, confirm cancellations |
| `/app/book` | Select patient/service/date/equipment, search slots, book, handle conflicts |
| `/app/schedule` | Staff weekly view; administrators can add individual shifts |
| `/app/resources` | Staff directory of services, rooms, equipment, and care team |
| `/app/profile` | Edit your name, email, patient phone number, or password |
| `/app/accounts` | Administrators search/filter accounts, inspect linked profiles, and edit roles and active status |

Profile and account changes save to PostgreSQL immediately. Patient names stay
in sync with their login accounts. Phone editing is available for patient
profiles because that is where the existing database stores phone numbers.
Password changes require the current password and a new password of 12–128
characters, then return you to sign-in. Refresh sessions are revoked; existing access tokens expire normally.

Administrators cannot deactivate or demote themselves. Accounts linked to a
clinical staff profile retain its matching doctor/nurse role. Assigning a
doctor/nurse role to an unlinked account does not create a staff profile;
that profile still needs to be set up through the backend. Deactivation blocks
account access and preserves clinical records and scheduled assignments.

Patients book for themselves. Staff can choose a patient; receptionists and
administrators can add a walk-in patient. Doctors and nurses see their own
shifts as enforced by the API. The schedule shows seven days, including weekends.

All new bookings wait for review. Staff can also submit urgent
requests for review. Room selection is automatic; choose a doctor or let the system assign one. Search
results are grouped by starting time for the selected doctor, or any doctor if no preference is supplied.
Changing the form clears the previous search and selection. A booking conflict
requires a new search. All dates/times use the browser's timezone, labeled on
the relevant screens; requests send ISO timestamps with offsets.

Appointments need matching staff shifts. The repository's historical seed
dates will not produce future availability; an administrator can add future
shifts through **Team schedule → Add shift**. This is manual entry, not automatic
shift generation.

Equipment is selected explicitly, matching the current backend contract.
There is no automatic service-equipment mapping. Resource statuses shown in
the directory are operating statuses, not proof of availability at every time.

## Authentication and deployment

Access tokens stay in memory, never localStorage/sessionStorage. Requests send
credentials for the backend's HttpOnly refresh cookie. A shared refresh request
prevents simultaneous token rotations; expired sessions return to sign-in.
Login uses form encoding as required by the API. Logout clears local access
even when the network fails and reports that the server session may remain.

Use **localhost** consistently in development. The backend uses Secure,
SameSite=Strict refresh cookies. For production, serve the app over HTTPS and
reverse-proxy `/api` to FastAPI on the same site. Configure SPA fallback to
`index.html` for routes such as `/app/book`. Alternatively set
`VITE_API_BASE_URL` at build time and configure backend CORS/cookie deployment
accordingly. Vite's development proxy is not a production server.

## Checks

```powershell
npm test
npm run build
```

The Vitest suite covers form login, memory-only tokens, refresh/retry behavior,
pagination, validation messages, booking, stale slot selection, conflict
handling, cancellation confirmation, profile updates, password changes, and
administrator account editing.

Optional desktop/mobile browser checks:

```powershell
npx playwright install chromium
npm run test:browser
```

Browser tests start Vite if it is not running and intercept API responses;
they never create real clinic records. They save screenshots under ignored
`test-results/`. They require downloading Chromium successfully first.

## File guide

- `src/App.jsx`: session bootstrap, protected routes, role-aware navigation.
- `src/api.js`: fetch client, tokens, refresh, errors, catalog pagination.
- `src/data.jsx`: catalog provider and cancellable list loading.
- `src/format.js`: timezone-aware display and search window conversion.
- `src/components.jsx`: shared branding, feedback, headings, native dialogs.
- `src/Landing.jsx`, `src/Auth.jsx`: public and authentication pages.
- `src/Dashboard.jsx`, `src/Appointments.jsx`, `src/Booking.jsx`: appointment flow.
- `src/Schedule.jsx`, `src/Resources.jsx`: team and resource screens.
- `src/Profile.jsx`, `src/Accounts.jsx`: self-service and administrator account editing.
- `src/styles.css`: Tailwind theme, reusable component utilities, and decorative CSS.
- `src/test/`: component/API regression tests.
- `e2e/clinic.spec.js`: desktop/mobile browser journey.
- `vite.config.js`, `playwright.config.js`: Tailwind integration, development proxy, and test setup.
- `package.json`, `package-lock.json`: commands and reproducible dependencies.

This flow adds no reminders, forecasts, or automatic shifts. Account editing uses the existing database schema without an additional migration.

## Profile pictures

My profile supports uploading, replacing, and removing your own picture. JPEG,
PNG, and WebP files up to 2 MB and 16 megapixels are accepted, cropped to a
256px square, and re-encoded without original metadata. The sidebar displays
the saved picture; initials are the fallback.

Install updated backend requirements (Pillow is required). Profile pictures themselves need no additional migration. Photos are private files under `backend/uploads/profiles`, excluded
from Git. Back up this directory with the database; use a persistent shared
`PROFILE_PICTURE_DIR` for deployments with multiple backend instances. Photos
are linked by user ID, so keep their storage separate for each database.

`PUT /users/me/picture` accepts multipart field `file`; `DELETE /users/me/picture`
removes it. Both require authentication and return the updated current profile.
`GET /users/me` includes nullable `profile_picture` as a JPEG data URL. Pictures
are currently displayed only for the signed-in user, not in the admin directory.

## Account management

Accounts can be filtered by role and active/inactive status alongside name/email
search. Details shows account creation time and linked patient/staff information
from the existing catalogs. Saving a change from active to inactive requires
confirmation; returning to editing preserves the unsaved form. Deactivation
blocks account access but does not cancel appointments or reassign shifts.
Reactivate an account by checking its active status and saving. Administrators
cannot deactivate themselves. No administrator password reset is
included, and no additional database migration is needed.

Each row has one Manage action. The Manage dialog contains account details,
the status toggle, Edit details, and Delete account. Turning access off requires confirmation;
turning it on reactivates the account. The toggle updates after the API saves
successfully and is disabled for your own administrator account.

## Delete unused accounts

Administrators can choose Manage, then Delete account in Accounts and enter their own administrator password to
confirm. `DELETE /users/{user_id}` rejects self-deletion, all linked staff
profiles, patient appointment/waitlist history, and recorded status changes.
Use deactivation for those accounts. Unused linked patient profiles and refresh
sessions are deleted with the account; its picture is removed after commit.
The API locks the user and patient rows before checking history to protect
against concurrent bookings. No migration is required.

Account deletion requires JSON `{ "admin_password": "..." }` in the DELETE
request body. The server verifies the signed-in administrator's password and
limits deletion requests to five per minute per client IP. The dialog clears
the entered password after each attempt and when closed.

## Hospital branding and landing image

The app uses Princeton-Plainsboro Teaching Hospital (PPTH) branding.
Add your photo as `frontend/public/images/ppth-hero.jpg` and refresh the page.
The hero displays it with a soft ivory edge fade and a brief fade-in (disabled
for reduced motion). The floating message cards and illustrated doctor have
been removed. A sage background is shown until you provide the image.

## Assisted account creation

Receptionists use **Add patient account** to create a login and linked patient
profile (`POST /users/patient-accounts`: full_name, email, password, optional
phone_number). The server fixes the role to patient and rejects extra role fields.
Administrators can also use this endpoint.

Admins use **Accounts > Add staff account** (`POST /users/staff-accounts`). Choose
doctor, nurse, receptionist, or administrator. Doctor/nurse accounts require an
existing department and optionally a qualification; the matching staff profile
is created in the same transaction. Both endpoints require a 12?128 character
initial password, return UserRead, and roll back duplicate-email failures.
Share the initial password privately; owners can change it in My profile.
No migration is needed. Existing walk-in patient creation remains separate:
these forms create new records, not links to existing walk-in profiles.

## Doctor selection

Booking supports an optional doctor dropdown. `doctor_id` is the doctor's
**staff_id**, accepted by both GET `/appointments/availability` and POST
`/appointments/`. Omit it for automatic assignment. When supplied, availability
and the transactional booking recheck use only that doctor; no substitution
occurs when they are unavailable. Rooms, nurse requirements, shifts, equipment,
and overlap checks still apply. Appointments displays assigned doctor names.
No database migration is required.


The PPTH theme uses restrained teal accents, borderless panels with soft shadows, compact tables,
and straightforward page labels. The landing photo and its fade remain customizable.

Booking-guide cards use solid sage, pale blue, and peach surfaces. Card edges
are defined by subtle shadows rather than frames; fields use inset shadows and tables use alternating row backgrounds.

Shared borderless styling covers navigation, dialogs, notices, tabs, buttons,
forms, appointment tables, and schedule cells. Selected states retain color
contrast; forced-colors mode restores outlines for accessibility.

The shared type scale uses 18px body text, 17?18px controls/table content, and
15?16px supporting text. Form controls are at least 56px tall; small action
buttons and responsive dialogs are enlarged without scaling the whole viewport.

## Appointment approval

All new bookings start as `requested` (Awaiting review) and reserve their assigned
resources. Existing confirmed bookings are unchanged. Use the dashboard review
link or Appointments > Awaiting review. Admins and receptionists can review all
requests; doctors can review only their assigned requests. Patients/nurses cannot
review. Accept and Reject both require UI confirmation.

POST `/appointments/{id}/approve` confirms a future pending appointment; POST
`/appointments/{id}/reject` cancels it and releases reservations using the existing
cancellation flow. Rejected requests appear as Cancelled in the existing status
model. Decisions lock the appointment, reject repeat decisions with 409, and
record the acting user through existing status-history triggers. No migration.
