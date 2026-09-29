
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Appointment,
    User,
    UserRole,
)
from app.schemas import AppointmentCreate, AppointmentRead
from app.services.scheduling import book_appointment, cancel_appointment

router = APIRouter(prefix="/appointments", tags=["Appointments"])

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
        if current_user.patient_profile and current_user.patient_profile.patient_id != apt_in.patient_id:
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
