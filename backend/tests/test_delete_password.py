from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.models import UserRole
from app.routers.users import delete_unused_account
from app.schemas import AccountDeleteRequest
from app.security import get_password_hash


@pytest.mark.parametrize("password,expected", [("wrong-password", 403), ("AdminPassword123!", 404)])
def test_delete_checks_acting_admin_password_before_target_lookup(password, expected):
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
    admin = SimpleNamespace(user_id=7, role=UserRole.administrator, is_active=True, password_hash=get_password_hash("AdminPassword123!"))
    with pytest.raises(HTTPException) as error:
        delete_unused_account.__wrapped__(Request({"type":"http", "method":"DELETE", "path":"/users/99", "headers":[]}), 99, AccountDeleteRequest(admin_password=password), db, admin)
    assert error.value.status_code == expected
    db.commit.assert_not_called()
    if expected == 403:
        db.query.assert_not_called()
