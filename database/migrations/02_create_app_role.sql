-- database/migrations/02_create_app_role.sql
-- Proposal: Dedicated least-privilege database role for the FastAPI backend

-- Create the role with a password (replace 'SecureAppPassword123!' before running)
CREATE ROLE clinic_app_role WITH LOGIN PASSWORD 'SecureAppPassword123!';

-- Grant connect permission on the database
GRANT CONNECT ON DATABASE clinic TO clinic_app_role;

-- Grant usage on the schema
GRANT USAGE ON SCHEMA public TO clinic_app_role;

-- Grant SELECT, INSERT, UPDATE, DELETE on all existing tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO clinic_app_role;

-- Grant USAGE and SELECT on all sequences (needed for SERIAL primary keys)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO clinic_app_role;

-- Ensure future tables/sequences also automatically grant permissions to the app role
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clinic_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO clinic_app_role;
