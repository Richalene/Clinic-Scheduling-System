from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_vite_cors_is_development_only():
    values = dict(DATABASE_URL="postgresql://unused", SECRET_KEY="a" * 40, ALLOWED_ORIGINS="https://clinic.example.com")
    dev = Settings(_env_file=None, ENVIRONMENT="development", **values)
    production = Settings(_env_file=None, ENVIRONMENT="production", **values)
    assert "http://localhost:5173" in dev.get_allowed_origins_list
    assert "http://127.0.0.1:5173" in dev.get_allowed_origins_list
    assert production.get_allowed_origins_list == ["https://clinic.example.com"]
    with TestClient(app) as client:
        response = client.options("/appointments/", headers={"Origin":"http://localhost:5173", "Access-Control-Request-Method":"POST"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_me_and_lookup_permissions(client, headers):
    me = client.get("/users/me", headers=headers())
    assert me.status_code == 200, me.text
    assert me.json()["patient_id"] == 1
    assert me.json()["staff_id"] is None
    doctor = client.get("/users/me", headers=headers(1,"doctor")).json()
    assert doctor["staff_id"] == 1
    assert doctor["patient_id"] is None
    assert "password_hash" not in doctor
    for path in ["/services/", "/rooms/", "/equipment/", "/patients/", "/staff/", "/staff/departments"]:
        assert client.get(path).status_code == 401
        response = client.get(path, headers=headers())
        assert response.status_code == 200, response.text
        assert response.json()
    patients = client.get("/patients/", headers=headers()).json()
    assert [p["patient_id"] for p in patients] == [1]
    assert len(client.get("/patients/", headers=headers(4,"receptionist")).json()) == 2


def test_walk_in_patient(client, headers):
    payload = {"patient_name":"Walk In", "phone_number":"555-1234"}
    assert client.post("/patients/", json=payload, headers=headers()).status_code == 403
    response = client.post("/patients/", json=payload, headers=headers(4,"receptionist"))
    assert response.status_code == 201, response.text
    assert response.json()["user_id"] is None
