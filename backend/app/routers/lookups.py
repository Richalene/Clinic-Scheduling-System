"""Small, authenticated catalogs needed by the booking form."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Equipment, Patient, Room, Service, User, UserRole
from app.schemas import EquipmentRead, PatientBase, PatientRead, RoomRead, ServiceRead

router = APIRouter(tags=["Booking lookups"])


@router.get("/services/", response_model=list[ServiceRead])
def list_services(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return db.query(Service).order_by(Service.service_id).offset(skip).limit(limit).all()


@router.get("/rooms/", response_model=list[RoomRead])
def list_rooms(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return db.query(Room).order_by(Room.room_id).offset(skip).limit(limit).all()


@router.get("/equipment/", response_model=list[EquipmentRead])
def list_equipment(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return db.query(Equipment).order_by(Equipment.equipment_id).offset(skip).limit(limit).all()


@router.get("/patients/", response_model=list[PatientRead])
def list_patients(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    query = db.query(Patient)
    if user.role == UserRole.patient:
        query = query.filter(Patient.user_id == user.user_id)
    return query.order_by(Patient.patient_id).offset(skip).limit(limit).all()


@router.post("/patients/", response_model=PatientRead, status_code=201)
def create_walk_in_patient(
    payload: PatientBase,
    db: Session = Depends(get_db),
    user: User = Depends(require_role([UserRole.administrator, UserRole.receptionist])),
):
    """Register a walk-in patient without creating or linking a login account."""
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient
