from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, local

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.models import UserRole
from app.schemas import AppointmentCreate
from app.services import scheduling


def payload(start, **changes):
    return {"patient_id": 1, "service_id": 2, "start_at": start.isoformat(), "equipment_ids": [1], **changes}


def test_available_book_cancel_and_back_to_back(client, database, headers):
    factory, start = database
    params = {"service_id": 2, "from_time": start.isoformat(),
              "to_time": (start + timedelta(minutes=30)).isoformat(), "equipment_ids": [1]}
    slots = client.get("/appointments/availability", params=params, headers=headers())
    assert slots.status_code == 200, slots.text
    assert slots.json()[0]["nurse_id"] == 2
    booked = client.post("/appointments/", json=payload(start), headers=headers())
    assert booked.status_code == 201, booked.text
    body = booked.json()
    assert body["status"] == "requested"
    assert body["room_id"] in [1, 2]
    assert {row["staff_id"] for row in body["assigned_staff"]} == {1, 2}
    assert body["assigned_equipment"] == [{"equipment_id": 1}]
    assert client.get("/appointments/availability", params=params, headers=headers()).json() == []
    assert client.post("/appointments/", json=payload(start), headers=headers()).status_code == 409
    assert client.post("/appointments/", json=payload(start + timedelta(minutes=30)), headers=headers()).status_code == 201
    cancelled = client.post(f'/appointments/{body["appointment_id"]}/cancel', headers=headers())
    assert cancelled.status_code == 200, cancelled.text
    assert client.post("/appointments/", json=payload(start), headers=headers()).status_code == 201
    with factory() as db:
        assert db.execute(text("SELECT count(*) FROM status_history WHERE changed_by_user_id = 3")).scalar() == 4


@pytest.mark.parametrize("equipment_ids, expected", [([2],409), ([999],404), ([1,1],422), ([-1],422)])
def test_invalid_equipment_does_not_save(client, database, headers, equipment_ids, expected):
    factory, start = database
    response = client.post("/appointments/", json=payload(start, equipment_ids=equipment_ids), headers=headers())
    assert response.status_code == expected, response.text
    with factory() as db:
        assert db.execute(text("SELECT count(*) FROM appointments")).scalar() == 0


def test_patient_ownership_and_urgent_policy(client, database, headers):
    _, start = database
    assert client.post("/appointments/", json=payload(start, patient_id=2), headers=headers()).status_code == 403
    assert client.post("/appointments/", json=payload(start), headers=headers(6)).status_code == 403
    assert client.post("/appointments/", json=payload(start, priority="urgent"), headers=headers()).status_code == 403
    urgent = client.post("/appointments/", json=payload(start, priority="urgent"), headers=headers(4,"receptionist"))
    assert urgent.status_code == 201, urgent.text
    assert urgent.json()["status"] == "requested"


@pytest.mark.parametrize("change, expected", [({"service_id":999},404), ({"patient_id":999},404), ({"start_at":"2020-01-01T09:00:00+00:00"},400), ({"start_at":"2035-01-01T09:00:00"},422)])
def test_bad_booking_input(client, database, headers, change, expected):
    _, start = database
    response = client.post("/appointments/", json=payload(start, **change), headers=headers(4,"receptionist"))
    assert response.status_code == expected, response.text


def test_availability_validation_and_auth(client, database, headers):
    _, start = database
    params = {"service_id":1,"from_time":start.isoformat(),"to_time":start.isoformat()}
    assert client.get("/appointments/availability", params=params).status_code == 401
    assert client.get("/appointments/availability", params=params, headers=headers()).status_code == 400
    params["to_time"] = (start + timedelta(days=32)).isoformat()
    assert client.get("/appointments/availability", params=params, headers=headers()).status_code == 400


def test_failed_deferred_constraint_rolls_back_everything(client, database, headers):
    factory, start = database
    # Force a real PostgreSQL failure at commit, after appointment + assignments
    # have been flushed. This verifies the transaction's deferred-error boundary.
    with factory() as db:
        db.execute(text("""
            CREATE FUNCTION reject_test_booking() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'Test deferred failure'; END; $$ LANGUAGE plpgsql;
            CREATE CONSTRAINT TRIGGER reject_test_booking AFTER INSERT ON appointments
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_test_booking();
        """))
        db.commit()
    response = client.post("/appointments/", json=payload(start), headers=headers())
    assert response.status_code == 409, response.text
    with factory() as db:
        for table in ["appointments", "appointment_staff", "appointment_equipment", "status_history"]:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0


def test_concurrent_bookings_only_one_succeeds(database, monkeypatch):
    factory, start = database
    barrier, calls = Barrier(2), local()
    original = scheduling.get_available_slots

    def synchronized_search(*args, **kwargs):
        rows = original(*args, **kwargs)
        calls.count = getattr(calls, "count", 0) + 1
        if calls.count == 1:
            barrier.wait(timeout=10)
        return rows

    monkeypatch.setattr(scheduling, "get_available_slots", synchronized_search)

    def book():
        with factory() as db:
            try:
                scheduling.book_appointment(db, 3, UserRole.patient, AppointmentCreate(**payload(start)))
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: book(), range(2)))
    assert sorted(results) == [201,409]
    with factory() as db:
        assert db.execute(text("SELECT count(*) FROM appointments")).scalar() == 1
        assert db.execute(text("SELECT count(*) FROM appointment_staff")).scalar() == 2
        assert db.execute(text("SELECT count(*) FROM appointment_equipment")).scalar() == 1


def test_equipment_conflicts_do_not_hide_later_slots(client, database, headers):
    factory, start = database
    # Reserve only the equipment, leaving rooms and staff free. The first ten
    # room/staff combinations conflict, but the later part of the day is free.
    with factory() as db:
        db.execute(text("""
            WITH booked AS (
                INSERT INTO appointments(patient_id,service_id,start_at,end_at,status)
                SELECT 1,1,t,t + interval '30 minutes','requested'
                FROM generate_series(CAST(:start AS timestamptz),
                     CAST(:start AS timestamptz) + interval '150 minutes', interval '30 minutes') AS t
                RETURNING appointment_id,start_at,end_at,status
            )
            INSERT INTO appointment_equipment(appointment_id,equipment_id,start_at,end_at,status)
            SELECT appointment_id,1,start_at,end_at,status FROM booked
        """), {"start":start})
        db.commit()
    params = {"service_id":2, "from_time":start.isoformat(),
              "to_time":(start + timedelta(hours=4)).isoformat(), "equipment_ids":[1]}
    response = client.get("/appointments/availability", params=params, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()
    from datetime import datetime
    assert datetime.fromisoformat(response.json()[0]["candidate_start"]) == start + timedelta(hours=3)
    assert client.post("/appointments/", json=payload(start), headers=headers()).status_code == 409


def test_consultation_does_not_reserve_an_unneeded_nurse(client, database, headers):
    _, start = database
    response = client.post("/appointments/", json=payload(start, service_id=1, equipment_ids=[]), headers=headers())
    assert response.status_code == 201, response.text
    assert response.json()["assigned_staff"] == [{"staff_id":1}]
    assert response.json()["assigned_equipment"] == []


@pytest.mark.parametrize("unavailable", [
    "DELETE FROM shifts WHERE staff_id = 1",
    "DELETE FROM shifts WHERE staff_id = 2",
    "UPDATE rooms SET status = 'maintenance'",
    "UPDATE rooms SET room_type = 'Wrong type'",
])
def test_missing_required_resources_rejects_booking(client, database, headers, unavailable):
    factory, start = database
    with factory() as db:
        db.execute(text(unavailable))
        db.commit()
    response = client.post("/appointments/", json=payload(start), headers=headers())
    assert response.status_code == 409, response.text
