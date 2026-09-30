from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
import base64
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.dependencies import get_current_user
from app.config import settings
from app.services.profile_pictures import read_picture


@pytest.fixture
def avatar_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_PICTURE_DIR", str(tmp_path))
    actor = SimpleNamespace(created_at=datetime.now(timezone.utc), user_id=900, full_name="Picture User", email="picture@example.com", role="patient", is_active=True, patient_profile=None, staff_profile=None)
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app) as client:
        yield client, actor
    app.dependency_overrides.pop(get_current_user, None)


def png():
    output = BytesIO()
    Image.new("RGB", (400, 300), "green").save(output, format="PNG")
    return output.getvalue()


def test_upload_replace_isolate_and_remove(avatar_client):
    client, actor = avatar_client
    for _ in range(2):
        response = client.put("/users/me/picture", files={"file": ("picture.png", png(), "image/png")})
        assert response.status_code == 200, response.text
        picture = response.json()["profile_picture"]
        with Image.open(BytesIO(base64.b64decode(picture.split(",")[1]))) as image:
            assert image.size == (256, 256)
            assert image.format == "JPEG"
        assert client.get("/users/me").json()["profile_picture"] == picture
    actor.user_id = 901
    assert client.get("/users/me").json()["profile_picture"] is None
    client.delete("/users/me/picture")
    assert read_picture(900) == picture
    actor.user_id = 900
    assert client.delete("/users/me/picture").json()["profile_picture"] is None
    assert client.delete("/users/me/picture").status_code == 200


@pytest.mark.parametrize("content,status", [(b"<svg></svg>", 400), (b"x" * (2 * 1024 * 1024 + 1), 413)], ids=["invalid", "oversized"])
def test_invalid_upload_preserves_picture(avatar_client, content, status):
    client, _ = avatar_client
    client.put("/users/me/picture", files={"file": ("photo.png", png())})
    original = read_picture(900)
    response = client.put("/users/me/picture", files={"file": ("fake.png", content, "image/png")})
    assert response.status_code == status
    assert read_picture(900) == original


def test_picture_requires_login():
    with TestClient(app) as client:
        assert client.put("/users/me/picture", files={"file": ("photo.png", png())}).status_code == 401
        assert client.delete("/users/me/picture").status_code == 401
