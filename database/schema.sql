-- database/schema.sql

-- Reset schema for re-runnability
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- Enable btree_gist for EXCLUDE constraints on ranges
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Custom types (enums)
CREATE TYPE user_role AS ENUM ('administrator', 'receptionist', 'doctor', 'nurse', 'patient');
CREATE TYPE staff_profession AS ENUM ('doctor', 'nurse');
CREATE TYPE resource_status AS ENUM ('available', 'maintenance', 'out_of_service');
CREATE TYPE appointment_status AS ENUM ('requested', 'confirmed', 'cancelled', 'completed', 'no_show');
CREATE TYPE appointment_priority AS ENUM ('normal', 'urgent');
CREATE TYPE waitlist_status AS ENUM ('waiting', 'offered', 'booked', 'expired', 'cancelled');

-- 1. users
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. departments
CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(255) NOT NULL
);

-- 3. staff
CREATE TABLE staff (
    staff_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    profession staff_profession NOT NULL,
    qualification VARCHAR(255),
    UNIQUE (user_id)
);

-- 4. patients
CREATE TABLE patients (
    patient_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    patient_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(50)
);

-- 5. services
CREATE TABLE services (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(255) NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    requires_nurse BOOLEAN NOT NULL DEFAULT FALSE,
    room_type VARCHAR(100) NOT NULL
);

-- 6. rooms
CREATE TABLE rooms (
    room_id SERIAL PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    room_name VARCHAR(255) NOT NULL,
    room_type VARCHAR(100) NOT NULL,
    status resource_status NOT NULL DEFAULT 'available'
);

-- 7. equipment
CREATE TABLE equipment (
    equipment_id SERIAL PRIMARY KEY,
    equipment_name VARCHAR(255) NOT NULL,
    equipment_type VARCHAR(100) NOT NULL,
    status resource_status NOT NULL DEFAULT 'available'
);

-- 8. staff_availability
CREATE TABLE staff_availability (
    availability_id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(staff_id) ON DELETE CASCADE,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    CHECK (end_at > start_at)
);

-- 9. shifts
CREATE TABLE shifts (
    shift_id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(staff_id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    CHECK (end_at > start_at),
    EXCLUDE USING gist (
        staff_id WITH =, 
        tstzrange(start_at, end_at, '[)') WITH &&
    )
);

-- 10. appointments
CREATE TABLE appointments (
    appointment_id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(service_id) ON DELETE RESTRICT,
    room_id INTEGER REFERENCES rooms(room_id) ON DELETE RESTRICT,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL DEFAULT 'requested',
    priority appointment_priority NOT NULL DEFAULT 'normal',
    CHECK (end_at > start_at),
    -- Constraint to enforce room double-booking prevention
    EXCLUDE USING gist (
        room_id WITH =, 
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('requested', 'confirmed')),
    
    -- Unique constraint to allow composite foreign keys in mapping tables
    UNIQUE (appointment_id, start_at, end_at, status)
);

-- 11. appointment_staff
CREATE TABLE appointment_staff (
    appointment_id INTEGER NOT NULL,
    staff_id INTEGER NOT NULL REFERENCES staff(staff_id) ON DELETE CASCADE,
    -- Denormalized times and status to enforce double-booking constraints via DB extensions
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL,
    
    PRIMARY KEY (appointment_id, staff_id),
    
    FOREIGN KEY (appointment_id, start_at, end_at, status) 
        REFERENCES appointments(appointment_id, start_at, end_at, status) 
        ON UPDATE CASCADE ON DELETE CASCADE,
        
    -- Constraint to enforce staff double-booking prevention
    EXCLUDE USING gist (
        staff_id WITH =, 
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('requested', 'confirmed'))
);

-- 12. appointment_equipment
CREATE TABLE appointment_equipment (
    appointment_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL REFERENCES equipment(equipment_id) ON DELETE CASCADE,
    -- Denormalized times and status to enforce double-booking constraints via DB extensions
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL,
    
    PRIMARY KEY (appointment_id, equipment_id),
    
    FOREIGN KEY (appointment_id, start_at, end_at, status) 
        REFERENCES appointments(appointment_id, start_at, end_at, status) 
        ON UPDATE CASCADE ON DELETE CASCADE,
        
    -- Constraint to enforce equipment double-booking prevention
    EXCLUDE USING gist (
        equipment_id WITH =, 
        tstzrange(start_at, end_at, '[)') WITH &&
    ) WHERE (status IN ('requested', 'confirmed'))
);

-- 13. waitlist_entries
CREATE TABLE waitlist_entries (
    waitlist_id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(service_id) ON DELETE CASCADE,
    preferred_date DATE NOT NULL,
    status waitlist_status NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. status_history
CREATE TABLE status_history (
    history_id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(appointment_id) ON DELETE CASCADE,
    changed_by_user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    old_status appointment_status,
    new_status appointment_status NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-------------------------------------------------------------------------------
-- Triggers & Functions
-------------------------------------------------------------------------------

-- T1. Enforce appointment duration matches service duration
CREATE OR REPLACE FUNCTION check_appointment_duration()
RETURNS TRIGGER AS $$
DECLARE
    svc_duration INTEGER;
BEGIN
    SELECT duration_minutes INTO svc_duration FROM services WHERE service_id = NEW.service_id;
    IF EXTRACT(EPOCH FROM (NEW.end_at - NEW.start_at))/60 != svc_duration THEN
        RAISE EXCEPTION 'Appointment duration must exactly match the service duration (% minutes)', svc_duration;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_appointment_duration
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION check_appointment_duration();

-- T2. Room type must match service room type
CREATE OR REPLACE FUNCTION check_room_type_match()
RETURNS TRIGGER AS $$
DECLARE
    svc_room_type VARCHAR;
    rm_type VARCHAR;
BEGIN
    IF NEW.room_id IS NOT NULL THEN
        SELECT room_type INTO svc_room_type FROM services WHERE service_id = NEW.service_id;
        SELECT room_type INTO rm_type FROM rooms WHERE room_id = NEW.room_id;
        IF rm_type != svc_room_type THEN
            RAISE EXCEPTION 'Room type (%) does not match service room type (%)', rm_type, svc_room_type;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_room_type_match
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION check_room_type_match();

-- T3. Automatically write status history when appointment status changes
CREATE OR REPLACE FUNCTION log_appointment_status_history()
RETURNS TRIGGER AS $$
DECLARE
    acting_user INTEGER;
BEGIN
    IF (TG_OP = 'INSERT') OR (OLD.status IS DISTINCT FROM NEW.status) THEN
        -- Try to get acting user from session context if available, otherwise NULL
        BEGIN
            acting_user := NULLIF(current_setting('app.current_user_id', true), '')::INTEGER;
        EXCEPTION WHEN OTHERS THEN
            acting_user := NULL;
        END;
        
        INSERT INTO status_history (appointment_id, changed_by_user_id, old_status, new_status)
        VALUES (NEW.appointment_id, acting_user, 
                CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE OLD.status END, 
                NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_log_appointment_status_history
AFTER INSERT OR UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION log_appointment_status_history();

-- T4. Room and equipment status must be 'available' when assigned to non-cancelled appointments
CREATE OR REPLACE FUNCTION check_room_status()
RETURNS TRIGGER AS $$
DECLARE
    rm_status resource_status;
BEGIN
    IF NEW.room_id IS NOT NULL AND NEW.status IN ('requested', 'confirmed') THEN
        SELECT status INTO rm_status FROM rooms WHERE room_id = NEW.room_id;
        IF rm_status != 'available' THEN
            RAISE EXCEPTION 'Room % is not available (current status: %)', NEW.room_id, rm_status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_room_status
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION check_room_status();

CREATE OR REPLACE FUNCTION check_equipment_status()
RETURNS TRIGGER AS $$
DECLARE
    eq_status resource_status;
BEGIN
    IF NEW.status IN ('requested', 'confirmed') THEN
        SELECT status INTO eq_status FROM equipment WHERE equipment_id = NEW.equipment_id;
        IF eq_status != 'available' THEN
            RAISE EXCEPTION 'Equipment % is not available (current status: %)', NEW.equipment_id, eq_status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_equipment_status
BEFORE INSERT OR UPDATE ON appointment_equipment
FOR EACH ROW EXECUTE FUNCTION check_equipment_status();

-- T5. Staff shift coverage: assigned appointments must fall within staff's shifts
CREATE OR REPLACE FUNCTION check_staff_within_shift()
RETURNS TRIGGER AS $$
DECLARE
    shift_exists BOOLEAN;
BEGIN
    IF NEW.status IN ('requested', 'confirmed') THEN
        SELECT EXISTS (
            SELECT 1 FROM shifts 
            WHERE staff_id = NEW.staff_id 
              AND start_at <= NEW.start_at 
              AND end_at >= NEW.end_at
        ) INTO shift_exists;
        
        IF NOT shift_exists THEN
            RAISE EXCEPTION 'Staff % does not have a shift covering the appointment % to %', NEW.staff_id, NEW.start_at, NEW.end_at;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_staff_within_shift
BEFORE INSERT OR UPDATE ON appointment_staff
FOR EACH ROW EXECUTE FUNCTION check_staff_within_shift();

-- T6. Requirements for 'confirmed' status: check requires_nurse
CREATE OR REPLACE FUNCTION check_confirmed_requirements()
RETURNS TRIGGER AS $$
DECLARE
    req_nurse BOOLEAN;
    doc_count INTEGER;
    nurse_count INTEGER;
BEGIN
    IF NEW.status = 'confirmed' THEN
        SELECT requires_nurse INTO req_nurse FROM services WHERE service_id = NEW.service_id;
        
        SELECT 
            COUNT(CASE WHEN s.profession = 'doctor' THEN 1 END),
            COUNT(CASE WHEN s.profession = 'nurse' THEN 1 END)
        INTO doc_count, nurse_count
        FROM appointment_staff ast
        JOIN staff s ON ast.staff_id = s.staff_id
        WHERE ast.appointment_id = NEW.appointment_id;
        
        IF doc_count < 1 THEN
            RAISE EXCEPTION 'Confirmed appointment requires at least one doctor assigned.';
        END IF;
        
        IF req_nurse AND nurse_count < 1 THEN
            RAISE EXCEPTION 'Confirmed appointment requires at least one nurse assigned because the service requires it.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Must be deferred to allow inserting assignment records in the same transaction
CREATE CONSTRAINT TRIGGER tr_check_confirmed_requirements
AFTER INSERT OR UPDATE ON appointments
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION check_confirmed_requirements();

-------------------------------------------------------------------------------
-- Views
-------------------------------------------------------------------------------

-- V1. v_weekly_staff_schedule
CREATE OR REPLACE VIEW v_weekly_staff_schedule AS
SELECT 
    s.staff_id,
    u.full_name AS staff_name,
    sh.start_at AS shift_start,
    sh.end_at AS shift_end,
    d.department_name,
    COALESCE(
        json_agg(
            json_build_object(
                'appointment_id', a.appointment_id,
                'start_at', a.start_at,
                'end_at', a.end_at,
                'status', a.status
            )
        ) FILTER (WHERE a.appointment_id IS NOT NULL), '[]'::json
    ) AS assigned_appointments
FROM staff s
JOIN users u ON s.user_id = u.user_id
JOIN shifts sh ON s.staff_id = sh.staff_id
JOIN departments d ON sh.department_id = d.department_id
LEFT JOIN appointment_staff ast ON s.staff_id = ast.staff_id 
    AND ast.start_at >= sh.start_at AND ast.end_at <= sh.end_at
    AND ast.status IN ('requested', 'confirmed')
LEFT JOIN appointments a ON ast.appointment_id = a.appointment_id
GROUP BY s.staff_id, u.full_name, sh.start_at, sh.end_at, d.department_name;

-- V2. v_staff_workload
CREATE OR REPLACE VIEW v_staff_workload AS
SELECT 
    s.staff_id,
    u.full_name AS staff_name,
    date_trunc('week', sh.start_at) AS week_start,
    COUNT(DISTINCT a.appointment_id) AS appointment_count,
    COALESCE(SUM(EXTRACT(EPOCH FROM (a.end_at - a.start_at))/60), 0) AS total_booked_minutes
FROM staff s
JOIN users u ON s.user_id = u.user_id
JOIN shifts sh ON s.staff_id = sh.staff_id
LEFT JOIN appointment_staff ast ON s.staff_id = ast.staff_id 
    AND ast.start_at >= sh.start_at AND ast.end_at <= sh.end_at
    AND ast.status IN ('requested', 'confirmed', 'completed')
LEFT JOIN appointments a ON ast.appointment_id = a.appointment_id
GROUP BY s.staff_id, u.full_name, date_trunc('week', sh.start_at);

-- V3. v_room_utilization
CREATE OR REPLACE VIEW v_room_utilization AS
WITH daily_room_shifts AS (
    -- Assume room available minutes is bounded by department shifts or standard 8 hours?
    -- A simple approach is just summing up booked minutes per day vs a flat 12 hour available
    -- Here we just list the booked minutes per day for simplicity.
    SELECT 
        a.room_id,
        date_trunc('day', a.start_at) as day_date,
        SUM(EXTRACT(EPOCH FROM (a.end_at - a.start_at))/60) as booked_minutes,
        720 AS available_minutes -- assuming 12 hours availability
    FROM appointments a
    WHERE a.status IN ('requested', 'confirmed', 'completed')
      AND a.room_id IS NOT NULL
    GROUP BY a.room_id, date_trunc('day', a.start_at)
)
SELECT 
    r.room_id,
    r.room_name,
    d.day_date,
    COALESCE(d.booked_minutes, 0) AS booked_minutes,
    COALESCE(d.available_minutes, 720) AS available_minutes
FROM rooms r
LEFT JOIN daily_room_shifts d ON r.room_id = d.room_id;

-- V4. v_understaffed_shifts
-- Find shifts where a department has < 1 doctor or < 1 nurse
CREATE OR REPLACE VIEW v_understaffed_shifts AS
SELECT 
    d.department_name,
    sh.start_at,
    sh.end_at,
    COUNT(CASE WHEN s.profession = 'doctor' THEN 1 END) AS doctor_count,
    COUNT(CASE WHEN s.profession = 'nurse' THEN 1 END) AS nurse_count
FROM shifts sh
JOIN staff s ON sh.staff_id = s.staff_id
JOIN departments d ON sh.department_id = d.department_id
GROUP BY d.department_name, sh.start_at, sh.end_at
HAVING COUNT(CASE WHEN s.profession = 'doctor' THEN 1 END) < 1 
    OR COUNT(CASE WHEN s.profession = 'nurse' THEN 1 END) < 1;

-- V5. v_cancellation_summary
CREATE OR REPLACE VIEW v_cancellation_summary AS
SELECT 
    date_trunc('day', h.changed_at) AS cancel_day,
    s.service_name,
    COUNT(*) AS cancellation_count
FROM status_history h
JOIN appointments a ON h.appointment_id = a.appointment_id
JOIN services s ON a.service_id = s.service_id
WHERE h.new_status = 'cancelled'
GROUP BY date_trunc('day', h.changed_at), s.service_name;

-- V6. v_waitlist_candidates
CREATE OR REPLACE VIEW v_waitlist_candidates AS
SELECT 
    w.waitlist_id,
    w.patient_id,
    p.patient_name,
    w.service_id,
    s.service_name,
    w.preferred_date,
    w.created_at
FROM waitlist_entries w
JOIN patients p ON w.patient_id = p.patient_id
JOIN services s ON w.service_id = s.service_id
WHERE w.status = 'waiting'
ORDER BY w.preferred_date ASC, w.created_at ASC;

-------------------------------------------------------------------------------
-- Helper Function
-------------------------------------------------------------------------------

-- find_available_slots
-- Returns candidate slots for a given service within a time range,
-- checking staff shifts and room availability.
CREATE OR REPLACE FUNCTION find_available_slots(
    p_service_id INTEGER, 
    p_from TIMESTAMPTZ, 
    p_to TIMESTAMPTZ
)
RETURNS TABLE (
    candidate_start TIMESTAMPTZ,
    candidate_end TIMESTAMPTZ,
    room_id INTEGER,
    doctor_id INTEGER,
    nurse_id INTEGER
) AS $$
DECLARE
    svc_duration INTERVAL;
    svc_req_nurse BOOLEAN;
    svc_room_type VARCHAR;
    slot_start TIMESTAMPTZ;
    slot_end TIMESTAMPTZ;
BEGIN
    SELECT make_interval(mins => duration_minutes), requires_nurse, room_type 
    INTO svc_duration, svc_req_nurse, svc_room_type 
    FROM services WHERE service_id = p_service_id;

    -- We loop through available slots by hour/half-hour for simplicity.
    -- A simpler implementation is returning available rooms & staff that cover a 
    -- generated series of slots within the requested window.
    RETURN QUERY
    WITH candidate_slots AS (
        SELECT t AS c_start, t + svc_duration AS c_end
        FROM generate_series(p_from, p_to - svc_duration, '30 minutes'::interval) AS t
    ),
    valid_rooms AS (
        SELECT cs.c_start, cs.c_end, r.room_id
        FROM candidate_slots cs
        CROSS JOIN rooms r
        WHERE r.room_type = svc_room_type 
          AND r.status = 'available'
          AND NOT EXISTS (
              SELECT 1 FROM appointments a 
              WHERE a.room_id = r.room_id 
                AND a.status IN ('requested', 'confirmed')
                AND a.start_at < cs.c_end AND a.end_at > cs.c_start
          )
    ),
    valid_doctors AS (
        SELECT cs.c_start, cs.c_end, s.staff_id AS doc_id
        FROM candidate_slots cs
        JOIN shifts sh ON sh.start_at <= cs.c_start AND sh.end_at >= cs.c_end
        JOIN staff s ON sh.staff_id = s.staff_id AND s.profession = 'doctor'
        WHERE NOT EXISTS (
              SELECT 1 FROM appointment_staff ast 
              WHERE ast.staff_id = s.staff_id 
                AND ast.status IN ('requested', 'confirmed')
                AND ast.start_at < cs.c_end AND ast.end_at > cs.c_start
        )
    ),
    valid_nurses AS (
        SELECT cs.c_start, cs.c_end, s.staff_id AS nurs_id
        FROM candidate_slots cs
        JOIN shifts sh ON sh.start_at <= cs.c_start AND sh.end_at >= cs.c_end
        JOIN staff s ON sh.staff_id = s.staff_id AND s.profession = 'nurse'
        WHERE NOT EXISTS (
              SELECT 1 FROM appointment_staff ast 
              WHERE ast.staff_id = s.staff_id 
                AND ast.status IN ('requested', 'confirmed')
                AND ast.start_at < cs.c_end AND ast.end_at > cs.c_start
        )
    )
    SELECT 
        vr.c_start, 
        vr.c_end, 
        vr.room_id, 
        vd.doc_id, 
        vn.nurs_id
    FROM valid_rooms vr
    JOIN valid_doctors vd ON vr.c_start = vd.c_start
    LEFT JOIN valid_nurses vn ON vr.c_start = vn.c_start
    WHERE (NOT svc_req_nurse) OR (vn.nurs_id IS NOT NULL)
    ORDER BY vr.c_start ASC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;
