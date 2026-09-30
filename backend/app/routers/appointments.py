
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Appointment,
    AppointmentStatus,
    User,
    UserRole,
)
from app.schemas import AppointmentCreate, AppointmentRead, AvailableSlotRead
from app.services.scheduling import book_appointment, cancel_appointment, get_available_slots

router = APIRouter(prefix="/appointments", tags=["Appointments"])

@router.get("/availability", response_model=list[AvailableSlotRead])
def availability(
    from_time: AwareDatetime,
    to_time: AwareDatetime,
    service_id: int = Query(..., gt=0),
    doctor_id: int | None = Query(None, gt=0),
    equipment_ids: list[int] = Query(default=[], max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search up to 31 days; equipment IDs use repeated query parameters."""
    return get_available_slots(db, service_id, from_time, to_time, equipment_ids, doctor_id)

@router.post("/", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    apt_in: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Book a new appointment.
    Patients can only book for themselves.
    Staff/Receptionist can book for anyone.
    """
    if current_user.role == UserRole.patient:
        # IDOR check
        if not current_user.patient_profile or current_user.patient_profile.patient_id != apt_in.patient_id:
            raise HTTPException(status_code=403, detail="You can only book appointments for yourself.")
            
    # book_appointment service handles 409 double-booking checking
    return book_appointment(db, current_user.user_id, current_user.role, apt_in)


@router.get("/", response_model=list[AppointmentRead])
def list_appointments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List appointments. 
    Patients see only their own.
    Doctors/Nurses see appointments they are assigned to.
    Receptionist/Admin sees all.
    """
    query = db.query(Appointment)
    
    if current_user.role == UserRole.patient:
        if current_user.patient_profile:
            query = query.filter(Appointment.patient_id == current_user.patient_profile.patient_id)
        else:
            return []
            
    elif current_user.role in [UserRole.doctor, UserRole.nurse]:
        if current_user.staff_profile:
            # Filter to appointments where this staff is assigned
            query = query.join(Appointment.assigned_staff).filter(
                Appointment.assigned_staff.any(staff_id=current_user.staff_profile.staff_id)
            )
        else:
            return []
            
    return query.offset(skip).limit(limit).all()


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel an appointment.
    Frees resources and notifies waitlist automatically via service logic.
    """
    apt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    # IDOR Check
    if current_user.role == UserRole.patient:
        if not current_user.patient_profile or current_user.patient_profile.patient_id != apt.patient_id:
            raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment")
            
    return cancel_appointment(db, appointment_id, current_user.user_id)


def review_appointment(appointment_id, approve, db, current_user):
    if current_user.role not in (UserRole.administrator, UserRole.receptionist, UserRole.doctor):
        raise HTTPException(403, "You cannot review appointments")
    apt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).with_for_update().first()
    if apt is None:
        raise HTTPException(404, "Appointment not found")
    if current_user.role == UserRole.doctor:
        profile = current_user.staff_profile
        if profile is None or not any(item.staff_id == profile.staff_id for item in apt.assigned_staff):
            raise HTTPException(403, "You can only review appointments assigned to you")
    if apt.status != AppointmentStatus.requested:
        raise HTTPException(409, "This appointment has already been reviewed or cancelled. Refresh the list.")
    if not approve:
        return cancel_appointment(db, appointment_id, current_user.user_id)
    if apt.start_at <= datetime.now(timezone.utc):
        raise HTTPException(409, "This appointment has already started. Reject it and arrange a new time.")
    try:
        db.execute(text("SELECT set_config('app.current_user_id', :id, true)"), {"id":str(current_user.user_id)})
        apt.status = AppointmentStatus.confirmed
        # Existing triggers revalidate reservations and required clinicians,
        # cascade the new status to assignments, and record the acting user.
        db.commit()
    except DBAPIError as exc:
        db.rollback()
        raise HTTPException(409, "The appointment could not be approved. Its resources may no longer be available.") from exc
    db.refresh(apt)
    return apt


@router.post("/{appointment_id}/approve", response_model=AppointmentRead)
def approve_appointment(appointment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return review_appointment(appointment_id, True, db, current_user)


@router.post("/{appointment_id}/reject", response_model=AppointmentRead)
def reject_appointment(appointment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return review_appointment(appointment_id, False, db, current_user)
