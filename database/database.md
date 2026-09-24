# Clinic Workforce Scheduling System - Database

This directory contains the database schema, seed data, and tests for the Clinic Workforce Scheduling System.

## How to Run

1. Ensure PostgreSQL (>= 15) is running locally or via Docker.
   For example, using Docker:
   ```bash
   docker run --name clinic-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=clinic -p 5432:5432 -d postgres:16
   ```

2. Execute the scripts in the following order. Note that `schema.sql` uses `DROP SCHEMA public CASCADE;` to ensure re-runnability, which will delete all existing data in the database.

   ```bash
   # 1. Create the schema, constraints, triggers, and views
   psql -d clinic -U postgres -f database/schema.sql
   
   # 2. Load the realistic seed data
   psql -d clinic -U postgres -f database/seed.sql
   
   # 3. Run the database tests
   psql -d clinic -U postgres -f database/tests.sql
   ```

## Design Decisions

### Double Booking Prevention (Core Requirement)
Double-booking is prevented strictly at the database level using the `btree_gist` extension, which allows us to create `EXCLUDE` constraints over timestamp ranges (`tstzrange`).

1. **Rooms**: The `appointments` table has an `EXCLUDE USING gist` constraint that prevents two appointments with the same `room_id` from having overlapping time ranges (where `start_at < end_at`), provided their status is 'requested' or 'confirmed'.
2. **Staff & Equipment**: The mapping tables (`appointment_staff` and `appointment_equipment`) denormalize the `start_at`, `end_at`, and `status` from the `appointments` table. 
   - **Consistency**: A composite foreign key `FOREIGN KEY (appointment_id, start_at, end_at, status) REFERENCES appointments(appointment_id, start_at, end_at, status) ON UPDATE CASCADE` guarantees that the times and status stay perfectly synced with the main appointment.
   - **Exclusion**: These mapping tables have their own `EXCLUDE USING gist` constraints to prevent overlapping times for the same `staff_id` or `equipment_id`.
3. **Shifts**: The `shifts` table also uses an `EXCLUDE USING gist` constraint to prevent overlapping shifts for the same staff member.

### Triggers for Usability
We use triggers to ensure database state correctness without relying on application-level validations:
- **`tr_check_appointment_duration`**: Enforces that `appointments.end_at - start_at` exactly matches the `services.duration_minutes`.
- **`tr_check_room_type_match`**: Ensures `rooms.room_type` matches `services.room_type`.
- **`tr_log_appointment_status_history`**: Automatically appends a record to `status_history` whenever an appointment's status changes.
- **`tr_check_room_status` / `tr_check_equipment_status`**: Rejects assignment if the resource is in 'maintenance' or 'out_of_service'.
- **`tr_check_staff_within_shift`**: Ensures assigned appointments strictly fall within the boundaries of a staff member's shift in `shifts`.
- **`tr_check_confirmed_requirements`**: A *deferred* trigger that runs at the end of the transaction to verify that a 'confirmed' appointment has at least 1 doctor, and if `services.requires_nurse` is true, at least 1 nurse.

## Assumptions and Limitations

- **Time ranges**: Range bounds are treated as `[)` (inclusive start, exclusive end) to seamlessly allow back-to-back appointments where the end of one equals the start of the next.
- **Status meaning**: `cancelled`, `completed`, and `no_show` statuses are considered "inactive". If an appointment enters these states, the EXCLUDE constraints ignore them, instantly freeing up the room, staff, and equipment.
- **Urgent Requests**: These are inserted with `status = 'requested'` and `priority = 'urgent'`. The EXCLUDE constraint treats 'requested' as an active block so nobody else accidentally books it before staff review. If it conflicts with an existing appointment, the urgent request must be handled (e.g. by cancelling the conflicting appointment first, or bypassing the conflict check by omitting room/staff until confirmed).
- **Concurrency**: PostgreSQL handles the concurrency locks naturally during inserts with the EXCLUDE constraint. If two users try to book the exact same slot concurrently, the second transaction will fail with an exclusion violation.
- **Simplification in Slot Search**: The `find_available_slots` function uses `generate_series` to search 30-minute blocks. It checks staff/room availability through subqueries. It returns a matrix of valid candidate slots. It does not heavily optimize for minimum workload, but it limits to 10 nearest results. 

## Notes for the Backend Team (FastAPI)

1. **Catching Exceptions**: When inserting overlapping appointments, PostgreSQL will throw an **Exclusion Violation (`23P01`)**. You must catch this specific SQLAlchemy/psycopg error and return a `409 Conflict` (or similar friendly error) to the frontend.
2. **Assigning Staff/Equipment**: Because of the `tr_check_confirmed_requirements` deferred constraint, you **MUST** wrap the appointment insertion and staff/equipment insertions within a single database transaction (`BEGIN; ... COMMIT;`), or the appointment must be created as 'requested' and later updated to 'confirmed'.
3. **Session User for Logs**: To properly record `changed_by_user_id` in `status_history`, your FastAPI app can execute `SET LOCAL app.current_user_id = '123';` at the start of the transaction. The trigger `tr_log_appointment_status_history` reads this session variable.
4. **Views**: Read directly from the provided `v_*` views for your dashboards. They heavily aggregate JSON and dates, saving you from writing complex ORM joins.
    - `v_weekly_staff_schedule`
    - `v_staff_workload`
    - `v_room_utilization`
    - `v_understaffed_shifts`
    - `v_cancellation_summary`
    - `v_waitlist_candidates`
5. **Finding Slots**: Use `SELECT * FROM find_available_slots(service_id, from_time, to_time)` to get a list of valid starting combinations.
