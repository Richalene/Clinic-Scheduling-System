
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, UserRole, WaitlistEntry
from app.schemas import WaitlistEntryCreate, WaitlistEntryRead

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])

@router.post("/", response_model=WaitlistEntryRead, status_code=status.HTTP_201_CREATED)
def join_waitlist(
    waitlist_in: WaitlistEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Join the waitlist. 
    Patients can only join for themselves.
    """
    if current_user.role == UserRole.patient:
        if current_user.patient_profile and current_user.patient_profile.patient_id != waitlist_in.patient_id:
            raise HTTPException(status_code=403, detail="You can only add yourself to the waitlist.")
            
    entry = WaitlistEntry(
        patient_id=waitlist_in.patient_id,
        service_id=waitlist_in.service_id,
        preferred_date=waitlist_in.preferred_date
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/", response_model=list[WaitlistEntryRead])
def list_waitlist(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    View waitlist.
    Patients see only their own entries.
    Admins/Receptionists see all.
    """
    query = db.query(WaitlistEntry)
    
    if current_user.role == UserRole.patient:
        if current_user.patient_profile:
            query = query.filter(WaitlistEntry.patient_id == current_user.patient_profile.patient_id)
        else:
            return []
            
    return query.offset(skip).limit(limit).all()
