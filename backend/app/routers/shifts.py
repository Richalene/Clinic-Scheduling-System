from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import Shift, User, UserRole
from app.schemas import BaseSchema, InputSchema

router = APIRouter(prefix="/shifts", tags=["Shifts"])

class ShiftCreate(InputSchema):
    staff_id: int
    department_id: int
    start_at: datetime
    end_at: datetime

class ShiftRead(BaseSchema):
    shift_id: int
    staff_id: int
    department_id: int
    start_at: datetime
    end_at: datetime

@router.get("/", response_model=list[ShiftRead])
def list_shifts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    staff_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.administrator, UserRole.doctor, UserRole.nurse, UserRole.receptionist]))
):
    """
    List shifts. Staff can see their own shifts. Receptionists/Admins can see all.
    """
    query = db.query(Shift)
    
    # IDOR protection: if user is not admin/receptionist, force filter to their own staff_id
    if current_user.role in [UserRole.doctor, UserRole.nurse]:
        # User must only see their own shifts
        # Find their staff_id
        if current_user.staff_profile:
            query = query.filter(Shift.staff_id == current_user.staff_profile.staff_id)
        else:
            return [] # No profile, no shifts
    elif staff_id:
        query = query.filter(Shift.staff_id == staff_id)
        
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=ShiftRead, status_code=status.HTTP_201_CREATED)
def create_shift(
    shift_in: ShiftCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator]))
):
    """Create a new shift (Admin only)."""
    if shift_in.start_at >= shift_in.end_at:
        raise HTTPException(status_code=400, detail="Start time must be before end time")
        
    shift = Shift(
        staff_id=shift_in.staff_id,
        department_id=shift_in.department_id,
        start_at=shift_in.start_at,
        end_at=shift_in.end_at
    )
    db.add(shift)
    try:
        db.commit()
        db.refresh(shift)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Shift overlaps with an existing shift for this staff member")
        
    return shift
