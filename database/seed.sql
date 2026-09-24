-- database/seed.sql

-- Safe to ignore if schema was just dropped
TRUNCATE users, departments, staff, patients, services, rooms, equipment, staff_availability, shifts, appointments, appointment_staff, appointment_equipment, waitlist_entries, status_history RESTART IDENTITY CASCADE;

BEGIN;

-- 1. Departments
INSERT INTO departments (department_name) VALUES 
('General Practice'),
('Pediatrics');

-- 2. Users (1 admin, 1 receptionist, 4 doctors, 3 nurses, 2 patients)
INSERT INTO users (full_name, email, password_hash, role) VALUES
('Admin Alice', 'admin@clinic.com', 'hash_admin', 'administrator'),
('Recp Bob', 'bob@clinic.com', 'hash_recp', 'receptionist'),
('Dr. Charlie', 'charlie@clinic.com', 'hash_doc', 'doctor'),
('Dr. Diana', 'diana@clinic.com', 'hash_doc', 'doctor'),
('Dr. Eve', 'eve@clinic.com', 'hash_doc', 'doctor'),
('Dr. Frank', 'frank@clinic.com', 'hash_doc', 'doctor'),
('Nurse Grace', 'grace@clinic.com', 'hash_nur', 'nurse'),
('Nurse Heidi', 'heidi@clinic.com', 'hash_nur', 'nurse'),
('Nurse Ivan', 'ivan@clinic.com', 'hash_nur', 'nurse'),
('Patient John', 'john@gmail.com', 'hash_pat', 'patient'),
('Patient Mary', 'mary@gmail.com', 'hash_pat', 'patient');

-- 3. Staff (Link users to departments)
-- Doctors
INSERT INTO staff (user_id, department_id, profession, qualification) VALUES
(3, 1, 'doctor', 'MD General'),
(4, 1, 'doctor', 'MD General'),
(5, 2, 'doctor', 'MD Pediatrics'),
(6, 2, 'doctor', 'MD Pediatrics');
-- Nurses
INSERT INTO staff (user_id, department_id, profession, qualification) VALUES
(7, 1, 'nurse', 'RN'),
(8, 1, 'nurse', 'RN'),
(9, 2, 'nurse', 'RN Pediatrics');

-- 4. Patients (including one created by receptionist without user account)
INSERT INTO patients (user_id, patient_name, phone_number) VALUES
(10, 'John Doe', '555-0100'),
(11, 'Mary Smith', '555-0200'),
(NULL, 'Walkin Tim', '555-0300');

-- 5. Services
INSERT INTO services (service_name, duration_minutes, requires_nurse, room_type) VALUES
('Standard Consultation', 30, FALSE, 'Consultation Room'),
('Extended Consultation', 60, FALSE, 'Consultation Room'),
('Vaccination', 15, TRUE, 'Treatment Room'),
('Minor Procedure', 45, TRUE, 'Treatment Room'),
('Pediatric Checkup', 30, FALSE, 'Consultation Room');

-- 6. Rooms (6 rooms, 2 types)
INSERT INTO rooms (department_id, room_name, room_type, status) VALUES
(1, 'Room 101', 'Consultation Room', 'available'),
(1, 'Room 102', 'Consultation Room', 'available'),
(1, 'Room 103', 'Treatment Room', 'available'),
(2, 'Room 201', 'Consultation Room', 'available'),
(2, 'Room 202', 'Consultation Room', 'available'),
(2, 'Room 203', 'Treatment Room', 'maintenance');

-- 7. Equipment (5 items, 1 in maintenance)
INSERT INTO equipment (equipment_name, equipment_type, status) VALUES
('Ultrasound A', 'Imaging', 'available'),
('ECG Machine', 'Diagnostic', 'available'),
('Defibrillator', 'Emergency', 'available'),
('Vaccine Cooler', 'Storage', 'available'),
('Blood Pressure Monitor', 'Diagnostic', 'maintenance');

-- 8. Shifts
INSERT INTO shifts (staff_id, department_id, start_at, end_at) VALUES
-- Dr. Charlie (GP)
(1, 1, '2023-10-09 08:00:00+00', '2023-10-09 16:00:00+00'),
(1, 1, '2023-10-10 08:00:00+00', '2023-10-10 16:00:00+00'),
-- Dr. Diana (GP)
(2, 1, '2023-10-09 10:00:00+00', '2023-10-09 18:00:00+00'),
-- Dr. Eve (Pediatrics) - intentional gap on 2023-10-10
(3, 2, '2023-10-09 09:00:00+00', '2023-10-09 17:00:00+00'),
-- Dr. Frank (Pediatrics) - thin coverage (only 4 hours)
(4, 2, '2023-10-10 08:00:00+00', '2023-10-10 12:00:00+00'),
-- Nurse Grace
(5, 1, '2023-10-09 08:00:00+00', '2023-10-09 16:00:00+00'),
-- Nurse Heidi
(6, 1, '2023-10-10 08:00:00+00', '2023-10-10 16:00:00+00'),
-- Nurse Ivan
(7, 2, '2023-10-09 09:00:00+00', '2023-10-09 17:00:00+00');


-- 9. Appointments (10 appointments: completed, cancelled, confirmed, requested. 1 urgent requested)

-- A1. Completed past appointment
INSERT INTO appointments (patient_id, service_id, room_id, start_at, end_at, status, priority)
VALUES (1, 1, 1, '2023-10-09 08:30:00+00', '2023-10-09 09:00:00+00', 'completed', 'normal');
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES (1, 1, '2023-10-09 08:30:00+00', '2023-10-09 09:00:00+00', 'completed');

-- A2. Cancelled appointment
INSERT INTO appointments (patient_id, service_id, room_id, start_at, end_at, status, priority)
VALUES (2, 2, 2, '2023-10-09 10:00:00+00', '2023-10-09 11:00:00+00', 'cancelled', 'normal');
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES (2, 2, '2023-10-09 10:00:00+00', '2023-10-09 11:00:00+00', 'cancelled');

-- A3. Confirmed appointment requiring nurse
INSERT INTO appointments (patient_id, service_id, room_id, start_at, end_at, status, priority)
VALUES (3, 3, 3, '2023-10-09 11:00:00+00', '2023-10-09 11:15:00+00', 'confirmed', 'normal');
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES 
(3, 1, '2023-10-09 11:00:00+00', '2023-10-09 11:15:00+00', 'confirmed'),
(3, 5, '2023-10-09 11:00:00+00', '2023-10-09 11:15:00+00', 'confirmed');
INSERT INTO appointment_equipment (appointment_id, equipment_id, start_at, end_at, status) VALUES (3, 1, '2023-10-09 11:00:00+00', '2023-10-09 11:15:00+00', 'confirmed');

-- A4. Urgent requested appointment
INSERT INTO appointments (patient_id, service_id, room_id, start_at, end_at, status, priority)
VALUES (1, 4, 3, '2023-10-09 12:00:00+00', '2023-10-09 12:45:00+00', 'requested', 'urgent');

-- A5 to A10. Mix of other appointments
INSERT INTO appointments (patient_id, service_id, room_id, start_at, end_at, status, priority) VALUES 
(2, 5, 4, '2023-10-09 14:00:00+00', '2023-10-09 14:30:00+00', 'confirmed', 'normal'),
(3, 1, 1, '2023-10-09 14:30:00+00', '2023-10-09 15:00:00+00', 'requested', 'normal'),
(1, 1, 1, '2023-10-10 09:00:00+00', '2023-10-10 09:30:00+00', 'confirmed', 'normal'),
(2, 1, 2, '2023-10-10 09:30:00+00', '2023-10-10 10:00:00+00', 'completed', 'normal'),
(3, 3, 3, '2023-10-09 15:00:00+00', '2023-10-09 15:15:00+00', 'confirmed', 'normal'),
(1, 5, 4, '2023-10-10 10:00:00+00', '2023-10-10 10:30:00+00', 'no_show', 'normal');

-- Assign staff to A5
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES (5, 3, '2023-10-09 14:00:00+00', '2023-10-09 14:30:00+00', 'confirmed');
-- Assign staff to A7
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES (7, 1, '2023-10-10 09:00:00+00', '2023-10-10 09:30:00+00', 'confirmed');
-- Assign staff to A9
INSERT INTO appointment_staff (appointment_id, staff_id, start_at, end_at, status) VALUES 
(9, 1, '2023-10-09 15:00:00+00', '2023-10-09 15:15:00+00', 'confirmed'),
(9, 5, '2023-10-09 15:00:00+00', '2023-10-09 15:15:00+00', 'confirmed');

-- 10. Waitlist entries (3 waitlist entries)
INSERT INTO waitlist_entries (patient_id, service_id, preferred_date, status) VALUES
(1, 1, '2023-10-11', 'waiting'),
(2, 3, '2023-10-11', 'waiting'),
(3, 5, '2023-10-12', 'waiting');

COMMIT;
