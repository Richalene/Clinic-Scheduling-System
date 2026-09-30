from datetime import datetime, timedelta, timezone

import pytest

from app.models import Patient, RefreshToken, User, UserRole
from app.security import get_password_hash, verify_password


@pytest.fixture
def admin(database, headers):
    factory, _ = database
    with factory() as db:
        user = User(full_name="Admin One", email="admin@example.com", password_hash=get_password_hash("AdminPassword123!"), role=UserRole.administrator)
        db.add(user)
        db.commit()
        return user.user_id, headers(user.user_id, "administrator")


def test_profile_changes_persist_and_sync_patient(client, database, headers):
    response = client.patch("/users/me", headers=headers(), json={
        "full_name": "Updated Patient", "email": "updated@example.com", "phone_number": "09171234567",
    })
    assert response.status_code == 200, response.text
    assert response.json()["phone_number"] == "09171234567"
    assert "password_hash" not in response.json()
    assert client.get("/users/me", headers=headers()).json()["email"] == "updated@example.com"
    factory, _ = database
    with factory() as db:
        assert db.get(User, 3).full_name == "Updated Patient"
        assert db.get(Patient, 1).patient_name == "Updated Patient"
        assert db.get(User, 5).full_name == "Patient Two"
    assert client.patch("/users/me", headers=headers(), json={"phone_number": None}).json()["phone_number"] is None


@pytest.mark.parametrize("payload", [{"role":"administrator"}, {"is_active":False}, {"user_id":5}, {"full_name":None}, {"full_name":"  "}, {"email":None}])
def test_profile_rejects_privilege_fields_and_invalid_values(client, headers, payload):
    assert client.patch("/users/me", headers=headers(), json=payload).status_code == 422


def test_duplicate_email_rolls_back_entire_profile(client, database, headers):
    result = client.patch("/users/me", headers=headers(), json={"full_name":"Must Not Save", "email":"patient2@example.com"})
    assert result.status_code == 409
    factory, _ = database
    with factory() as db:
        assert db.get(User, 3).full_name == "Patient One"
        assert db.get(Patient, 1).patient_name == "Patient One"


def test_staff_phone_requires_patient_profile(client, headers):
    assert client.patch("/users/me", headers=headers(1,"doctor"), json={"phone_number":"123"}).status_code == 400
    assert client.patch("/users/me", headers=headers(1,"doctor"), json={"full_name":"New Doctor Name"}).status_code == 200


def test_admin_permissions_and_role_changes(client, headers, admin, database):
    admin_id, admin_headers = admin
    assert client.patch("/users/5", headers=headers(), json={"role":"administrator"}).status_code == 403
    assert client.get("/users/", headers=headers()).status_code == 403
    assert client.get("/users/", headers=admin_headers).status_code == 200
    changed = client.patch("/users/4", headers=admin_headers, json={"role":"patient", "full_name":"Now A Patient"})
    assert changed.status_code == 200, changed.text
    factory, _ = database
    with factory() as db:
        assert db.get(User, 4).patient_profile.patient_name == "Now A Patient"
    assert client.patch(f"/users/{admin_id}", headers=admin_headers, json={"is_active":False}).status_code == 400
    assert client.patch(f"/users/{admin_id}", headers=admin_headers, json={"role":"patient"}).status_code == 400
    assert client.patch("/users/1", headers=admin_headers, json={"role":"patient"}).status_code == 409
    assert client.patch("/users/5", headers=admin_headers, json={"full_name":None}).status_code == 422


def test_deactivation_blocks_access_and_revokes_refresh(client, database, headers, admin):
    factory, _ = database
    with factory() as db:
        db.add(RefreshToken(user_id=5, token_hash="test-session", expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()
    _, admin_headers = admin
    response = client.patch("/users/5", headers=admin_headers, json={"is_active":False})
    assert response.status_code == 200, response.text
    assert client.get("/users/me", headers=headers(5)).status_code == 403
    with factory() as db:
        assert db.query(RefreshToken).filter_by(user_id=5).one().revoked
        assert db.get(Patient, 2) is not None
    assert client.patch("/users/5", headers=admin_headers, json={"is_active":True}).status_code == 200
    assert client.get("/users/me", headers=headers(5)).status_code == 200


def test_password_validation_verification_and_revocation(client, database, headers):
    factory, _ = database
    with factory() as db:
        db.get(User, 3).password_hash = get_password_hash("OriginalPassword123!")
        db.add(RefreshToken(user_id=3, token_hash="password-test-session", expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.commit()
    endpoint = "/auth/change-password"
    assert client.post(endpoint, headers=headers(), json={"old_password":"wrong", "new_password":"ReplacementPassword123!"}).status_code == 400
    assert client.post(endpoint, headers=headers(), json={"old_password":"OriginalPassword123!", "new_password":"short"}).status_code == 422
    response = client.post(endpoint, headers=headers(), json={"old_password":"OriginalPassword123!", "new_password":"ReplacementPassword123!"})
    assert response.status_code == 200, response.text
    with factory() as db:
        assert verify_password("ReplacementPassword123!", db.get(User, 3).password_hash)
        assert db.query(RefreshToken).filter_by(user_id=3).one().revoked
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_delete_unused_account_and_protect_linked_records(client, database, headers, admin, monkeypatch):
    from app.dependencies import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    admin_id, auth = admin
    assert client.request("DELETE", '/users/5', json={"admin_password": "AdminPassword123!"}, headers=headers()).status_code == 403
    assert client.request("DELETE", f'/users/{admin_id}', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 400
    assert client.request("DELETE", '/users/1', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 409
    assert client.request("DELETE", '/users/999', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 404
    factory, _ = database
    with factory() as db:
        db.add(RefreshToken(user_id=5, token_hash='deletion-test-session', expires_at=datetime.now(timezone.utc)+timedelta(days=1)))
        db.commit()
    assert client.request("DELETE", '/users/5', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 200
    with factory() as db:
        assert db.get(User, 5) is None
        assert db.get(Patient, 2) is None
        assert db.query(RefreshToken).filter_by(user_id=5).count() == 0
    assert client.get('/users/me', headers=headers(5)).status_code == 401


def test_delete_preserves_appointment_and_actor_history(client, database, headers, admin, monkeypatch):
    from app.dependencies import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    _, auth = admin
    _, start = database
    result = client.post('/appointments/', headers=headers(4, 'receptionist'), json={
        'patient_id': 1, 'service_id': 1, 'start_at': start.isoformat(), 'priority': 'normal', 'equipment_ids': [],
    })
    assert result.status_code == 201, result.text
    assert client.request("DELETE", '/users/3', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 409
    assert client.request("DELETE", '/users/4', json={"admin_password": "AdminPassword123!"}, headers=auth).status_code == 409
    assert client.get('/users/me', headers=headers()).status_code == 200


def test_reception_creates_patient_account_only(client, database, headers):
    payload = {"full_name":"New Patient", "email":"new@example.com", "password":"PatientPassword123!", "phone_number":"12345"}
    assert client.post('/users/patient-accounts', headers=headers(), json=payload).status_code == 403
    auth = headers(4, 'receptionist')
    assert client.post('/users/patient-accounts', headers=auth, json={**payload, 'role':'administrator'}).status_code == 422
    result = client.post('/users/patient-accounts', headers=auth, json=payload)
    assert result.status_code == 201, result.text
    factory, _ = database
    with factory() as db:
        user = db.get(User, result.json()['user_id'])
        assert user.role == UserRole.patient
        assert user.patient_profile.phone_number == '12345'
        assert verify_password(payload['password'], user.password_hash)
    assert client.post('/users/patient-accounts', headers=auth, json=payload).status_code == 409
    assert client.post('/users/staff-accounts', headers=auth, json={**{k:v for k,v in payload.items() if k != 'phone_number'}, 'role':'doctor','department_id':1}).status_code == 403


def test_admin_creates_clinical_profile_atomically(client, database, headers, admin):
    _, auth = admin
    payload = {'full_name':'Dr. New', 'email':'newdoctor@example.com', 'password':'DoctorPassword123!', 'role':'doctor'}
    assert client.post('/users/staff-accounts', headers=auth, json=payload).status_code == 422
    assert client.post('/users/staff-accounts', headers=auth, json={**payload, 'department_id':999}).status_code == 404
    result = client.post('/users/staff-accounts', headers=auth, json={**payload, 'department_id':1})
    assert result.status_code == 201, result.text
    factory, _ = database
    with factory() as db:
        user = db.get(User, result.json()['user_id'])
        assert user.staff_profile.profession.value == 'doctor'
        assert user.staff_profile.department_id == 1
    assert client.post('/users/staff-accounts', headers=auth, json={**payload, 'department_id':1}).status_code == 409
