"""Integration tests require an explicitly named disposable PostgreSQL database.

Never read the developer's .env or reset the application's database.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

TEST_URL = os.environ.get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = TEST_URL or "postgresql+psycopg2://test:test@localhost/clinic_test_unused"
os.environ["SECRET_KEY"] = "test-only-secret-not-used-outside-tests-123456789"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from app.security import create_access_token


@pytest.fixture
def database():
    if not TEST_URL:
        pytest.skip("Set TEST_DATABASE_URL to a disposable clinic_test_* PostgreSQL database")
    url = make_url(TEST_URL)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test_"):
        pytest.fail("Refusing to reset a database without a clinic_test_ name")
    engine = create_engine(url)
    schema = (Path(__file__).resolve().parents[2] / "database" / "schema.sql").read_text()
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    with engine.begin() as connection:
        # Execute without bind parameters: PL/pgSQL messages contain literal %.
        with connection.connection.driver_connection.cursor() as cursor:
            cursor.execute(schema)
        connection.execute(text("""
            INSERT INTO departments(department_name) VALUES ('General');
            INSERT INTO users(full_name,email,password_hash,role) VALUES
                ('Doctor One','doctor@example.com','unused','doctor'),
                ('Nurse One','nurse@example.com','unused','nurse'),
                ('Patient One','patient@example.com','unused','patient'),
                ('Reception One','reception@example.com','unused','receptionist'),
                ('Patient Two','patient2@example.com','unused','patient'),
                ('No Profile','no-profile@example.com','unused','patient');
            INSERT INTO staff(user_id,department_id,profession) VALUES (1,1,'doctor'),(2,1,'nurse');
            INSERT INTO patients(user_id,patient_name) VALUES (3,'Patient One'),(5,'Patient Two');
            INSERT INTO services(service_name,duration_minutes,requires_nurse,room_type) VALUES
                ('Consultation',30,false,'Consultation'),('Treatment',30,true,'Consultation');
            INSERT INTO rooms(department_id,room_name,room_type) VALUES
                (1,'Room One','Consultation'),(1,'Room Two','Consultation');
            INSERT INTO equipment(equipment_name,equipment_type,status) VALUES
                ('ECG','Diagnostic','available'),('Broken ECG','Diagnostic','maintenance');
        """))
        connection.execute(text("""
            INSERT INTO shifts(staff_id,department_id,start_at,end_at)
            VALUES (1,1,:start,:end),(2,1,:start,:end)
        """), {"start": start, "end": start + timedelta(hours=8)})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory, start
    engine.dispose()


@pytest.fixture
def client(database):
    factory, _ = database

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def headers():
    def for_user(user_id=3, role="patient"):
        return {"Authorization": "Bearer " + create_access_token(str(user_id), role)}
    return for_user
