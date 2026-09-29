from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import User, UserRole

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/staff-schedule")
def get_staff_schedule(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator, UserRole.receptionist]))
):
    """View weekly staff schedule (Admin/Receptionist only)."""
    result = db.execute(text("SELECT * FROM v_weekly_staff_schedule"))
    return [dict(row._mapping) for row in result]

@router.get("/room-utilization")
def get_room_utilization(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator, UserRole.receptionist]))
):
    """View room utilization (Admin/Receptionist only)."""
    result = db.execute(text("SELECT * FROM v_room_utilization"))
    return [dict(row._mapping) for row in result]

@router.get("/cancellations")
def get_cancellations(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator, UserRole.receptionist]))
):
    """View cancellation summary (Admin/Receptionist only)."""
    result = db.execute(text("SELECT * FROM v_cancellation_summary"))
    return [dict(row._mapping) for row in result]
