# Minimum clinic booking flow

Run from `backend` so settings load `backend/.env`:

```powershell
python -m uvicorn app.main:app --reload
```

Install `requirements.txt` into your active virtual environment first. The
existing PostgreSQL schema, including `find_available_slots`, exclusion
constraints and deferred triggers, must already be installed. No additional database migration is required for profile editing or pictures. Do not rerun `schema.sql` on an existing
clinic database: it drops the public schema.

Development CORS includes `http://localhost:5173` and `http://127.0.0.1:5173`,
in addition to `ALLOWED_ORIGINS`. Production uses only configured origins.
Existing `.env` files do not need editing for development Vite access.

## React API sequence

1. Log in using `POST /auth/login` with form-encoded `username` (email) and
   `password`. Send `Authorization: Bearer <access_token>` on the calls below.
2. Read `GET /users/me`. It includes nullable `patient_id`, `staff_id`, and `phone_number`.
   Patient accounts need a patient profile to book.
3. Load catalogs:

   | Endpoint | Response / access |
   | --- | --- |
   | `GET /services/` | Service IDs, durations, room types, nurse requirement |
   | `GET /rooms/` | Room IDs, names, departments, types, status |
   | `GET /equipment/` | Equipment IDs, names, types, status |
   | `GET /patients/` | Patients; patient users only see themselves |
   | `GET /staff/` | Existing staff profiles; authentication now required |
   | `GET /staff/departments` | Existing departments; authentication now required |
   | `POST /patients/` | Admin/receptionist creates a walk-in patient |

   New lists accept `skip` and `limit` (maximum 100). Walk-in creation accepts
   `{"patient_name":"Walk In","phone_number":"555-1234"}` and returns a
   `patient_id`; it does not create or link a login account.

4. Search `GET /appointments/availability` with these query parameters:
   - `service_id`: positive integer.
   - `from_time`, `to_time`: future ISO timestamps including a timezone, for
     example `2030-10-01T09:00:00+08:00`. URL-encode offsets with `URLSearchParams`.
   - `equipment_ids`: optional repeated parameters, e.g.
     `equipment_ids=1&equipment_ids=3`.

   The window must be positive, at most 31 days, and include the whole service
   duration. Results contain up to 10 resource combinations at starts spaced
   30 minutes apart, starting at `from_time`. Each result includes
   `candidate_start`, `candidate_end`, `room_id`, `doctor_id`, nullable
   `nurse_id`, and `equipment_ids`. Several combinations can share a start.
   A valid search with no free resources returns `[]`.

5. Submit `POST /appointments/` using the selected candidate start:

   ```json
   {
     "patient_id": 1,
     "service_id": 2,
     "start_at": "2030-10-01T09:00:00+08:00",
     "priority": "normal",
     "equipment_ids": [1, 3]
   }
   ```

   Use actual lookup IDs and a date with staff shifts; the repository seed
   dates are historical. Room and staff are assigned automatically unless doctor_id is supplied and may
   differ from the advisory search result. The API rechecks availability,
   locks the selected resources, checks again, and saves all assignments in
   one transaction. PostgreSQL constraints remain the final concurrency guard.

   A successful booking returns **201** with status `requested`, a
   room, one doctor, a nurse when required, and all selected equipment.
   The response includes `assigned_staff: [{"staff_id":1}]` and
   `assigned_equipment: [{"equipment_id":1}]` in addition to existing fields.
   Staff-created urgent bookings remain `requested`, reserve their assigned
   resources, and never displace existing appointments. Patients cannot set
   urgent priority. Urgent requests also require an available slot in this flow.

6. Read `GET /appointments/` and cancel with
   `POST /appointments/{appointment_id}/cancel`. Cancellation releases the
   reservations through the existing database status cascade. Booking and
   cancellation record the acting user in status history.

Errors use `detail`: **400** invalid search range/past time, **401/403**
authentication/ownership, **404** missing referenced records, **409** unavailable
resources or a concurrent conflict, **422** invalid request shape. On 409,
refresh availability and let the user select again.

## Equipment scope

The existing schema does not define which equipment each service requires.
`equipment_ids` explicitly lists every item required for this booking; the
backend checks, reserves, and returns all of them. Omission means no equipment
is requested. It does not infer mandatory equipment from a service name.
Automatic service-equipment rules would need a separate agreed mapping.

This preserves the existing slot helper's staff/room rules. It does not add
qualification matching, departmental scheduling rules, reminders, forecasts,
automatic shifts, or automatic shift generation.

## Account editing

- `PATCH /users/me`: authenticated users may send any subset of `full_name`,
  `email`, and `phone_number`. Returns the same profile shape as `GET /users/me`.
  Phone numbers require an existing patient profile; `null` clears the phone.
  Names and emails cannot be null or blank. Role and activation changes are
  rejected on this endpoint. Patient names are updated in the same transaction.
- `POST /auth/change-password`: accepts `old_password` and `new_password`
  (12–128 characters). Checks the old password, saves the new hash, revokes
  refresh sessions, and clears the refresh cookie. Refresh sessions are revoked; existing access tokens
  expire normally. The frontend signs out immediately.
- `GET /users/` and `PATCH /users/{user_id}`: administrators only. Updates
  accept `full_name`, `email`, `role`, and `is_active` and return `UserRead`.
  Administrators cannot deactivate or demote themselves. Linked clinical
  profiles must keep their matching profession role. Changing an account to
  patient creates a patient profile if missing; assigning a clinical role
  does not automatically create a staff profile. Role changes and deactivation
  revoke refresh sessions. Deactivation preserves records and assignments.

Duplicate emails return **409** without partially saving the update. No additional database migration is required for account editing.

## Focused backend tests

Use a **separate disposable PostgreSQL database** whose name starts with
`clinic_test_`. The suite resets its public schema before each database test;
never point it at a real clinic database. `TEST_DATABASE_URL` is explicit and
independent of `.env`. Without it, database tests are skipped and the CORS test
still runs. Run one test process, since the fixtures reset the shared test DB.

```powershell
# Create this disposable database on a test PostgreSQL instance first.
$env:TEST_DATABASE_URL='postgresql+psycopg2://test_user:test_password@localhost:5432/clinic_test_booking'
python -m pytest tests -q
```

The suite exercises actual SQL triggers and constraints, authenticated HTTP
contracts, resource assignment, equipment conflicts, required nurse/shift/room
checks, ownership, cancellation/rebooking, deferred commit failure rollback,
two simultaneous booking transactions, profile persistence, account permissions,
deactivation, duplicate-email rollback, and password changes. It leaves the disposable test DB
populated for inspection; discard that DB when finished.

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

## Delete unused accounts

Administrators can choose Delete in Accounts and enter their own administrator password to
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
