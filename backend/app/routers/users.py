
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.profile_pictures import read_picture, store_picture, remove_picture
from app.database import get_db
from app.dependencies import get_current_user, require_role, limiter
from app.models import Department, Staff, Patient, RefreshToken, User, UserRole
from app.schemas import PatientAccountCreate, StaffAccountCreate, AccountDeleteRequest, ProfileUpdate, UserCreate, UserMeRead, UserRead, UserUpdate
from app.security import get_password_hash, verify_password

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_patient(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Public self-registration. Forcibly creates a 'patient' role account,
    regardless of what role the user specified in the payload.
    Also automatically creates a corresponding patient profile.
    """
    if db.query(User).filter(User.email == user_in.email).first():
        # Prevent email enumeration via generic response or standard conflict
        # A generic 400 is safer but standard practice often allows 409 for UX.
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.patient, # Forcibly override
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create the patient profile
    new_patient = Patient(
        user_id=new_user.user_id,
        patient_name=new_user.full_name
    )
    db.add(new_patient)
    db.commit()

    return new_user


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_staff_or_admin(
    user_in: UserCreate, 
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role([UserRole.administrator]))
):
    """
    Admin-only endpoint to create staff or other administrators.
    """
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role, # Admin can assign any role
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/", response_model=list[UserRead])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role([UserRole.administrator]))
):
    """Admin-only: list all users."""
    users = db.query(User).order_by(User.user_id).offset(skip).limit(limit).all()
    return users


@router.get("/me", response_model=UserMeRead)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get the currently logged-in user."""
    return UserMeRead(
        **UserRead.model_validate(current_user).model_dump(),
        profile_picture=read_picture(current_user.user_id),
        patient_id=current_user.patient_profile.patient_id if current_user.patient_profile else None,
        staff_id=current_user.staff_profile.staff_id if current_user.staff_profile else None,
        phone_number=current_user.patient_profile.phone_number if current_user.patient_profile else None,
    )


def save_account(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account could not be saved. The email may already be in use.") from exc


@router.patch("/me", response_model=UserMeRead)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit only your own contact fields; roles and activation are admin-only."""
    changes = payload.model_dump(exclude_unset=True)
    patient = current_user.patient_profile
    if "phone_number" in changes and patient is None:
        raise HTTPException(status_code=400, detail="Phone numbers are available for patient profiles only")
    phone = changes.pop("phone_number", None)
    for field, value in changes.items():
        setattr(current_user, field, value)
    if patient is not None:
        if "full_name" in changes:
            patient.patient_name = current_user.full_name
        if "phone_number" in payload.model_fields_set:
            patient.phone_number = phone.strip() or None if phone else None
    save_account(db)
    db.refresh(current_user)
    return get_current_user_profile(current_user)


@router.put("/me/picture", response_model=UserMeRead)
async def upload_my_picture(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    try:
        content = await file.read(2 * 1024 * 1024 + 1)
        store_picture(current_user.user_id, content)
    finally:
        await file.close()
    return get_current_user_profile(current_user)


@router.delete("/me/picture", response_model=UserMeRead)
def delete_my_picture(current_user: User = Depends(get_current_user)):
    remove_picture(current_user.user_id)
    return get_current_user_profile(current_user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role([UserRole.administrator]))
):
    """Admin-only: update a user's details, role, or active status."""
    # Serialize privilege changes and recheck the actor after acquiring the lock.
    # Concurrent admins cannot deactivate one another using stale authorization.
    db.execute(text("SELECT pg_advisory_xact_lock(7152941)"))
    db.refresh(admin_user)
    if not admin_user.is_active or admin_user.role != UserRole.administrator:
        raise HTTPException(status_code=403, detail="Administrator access is required")
    user = db.query(User).filter(User.user_id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = user_in.model_dump(exclude_unset=True)
    next_role = update_data.get("role", user.role)
    if user.user_id == admin_user.user_id and (
        next_role != UserRole.administrator or update_data.get("is_active") is False
    ):
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account or remove your own administrator role")
    if user.staff_profile and next_role != user.staff_profile.profession.value:
        raise HTTPException(status_code=409, detail="This account has a clinical staff profile. Its role must match that profile to preserve scheduling history.")
    if next_role == UserRole.patient and not user.patient_profile:
        user.patient_profile = Patient(patient_name=update_data.get("full_name", user.full_name))
    if user.patient_profile and "full_name" in update_data:
        user.patient_profile.patient_name = update_data["full_name"]
    if next_role != user.role or update_data.get("is_active") is False:
        db.query(RefreshToken).filter(RefreshToken.user_id == user.user_id).update({"revoked": True})
    for key, value in update_data.items():
        setattr(user, key, value)
        
    save_account(db)
    db.refresh(user)
    return user


@router.delete("/{user_id}")
@limiter.limit("5/minute")
def delete_unused_account(
    request: Request,
    user_id: int,
    payload: AccountDeleteRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role([UserRole.administrator])),
):
    """Delete unused registrations only; preserve all clinical and audit history."""
    db.execute(text("SELECT pg_advisory_xact_lock(7152941)"))
    db.refresh(admin_user, with_for_update=True)
    if not admin_user.is_active or admin_user.role != UserRole.administrator:
        raise HTTPException(403, "Administrator access is required")
    if not verify_password(payload.admin_password, admin_user.password_hash):
        raise HTTPException(403, "Incorrect administrator password")
    if user_id == admin_user.user_id:
        raise HTTPException(400, "You cannot delete your own account")
    target = db.query(User).filter(User.user_id == user_id).with_for_update().first()
    if target is None:
        raise HTTPException(404, "User not found")
    # Lock parent rows before checking children. Concurrent FK inserts must wait,
    # so a new booking cannot slip between the history checks and deletion.
    if db.execute(text("SELECT 1 FROM staff WHERE user_id=:id"), {"id": user_id}).first():
        raise HTTPException(409, "This account has a staff profile. Deactivate it instead to preserve staff records.")
    patients = db.query(Patient).filter(Patient.user_id == user_id).with_for_update().all()
    for patient in patients:
        for table in ("appointments", "waitlist_entries"):
            if db.execute(text(f"SELECT 1 FROM {table} WHERE patient_id=:id LIMIT 1"), {"id": patient.patient_id}).first():
                raise HTTPException(409, "This account has appointment or waitlist history. Deactivate it instead.")
    if db.execute(text("SELECT 1 FROM status_history WHERE changed_by_user_id=:id LIMIT 1"), {"id": user_id}).first():
        raise HTTPException(409, "This account has recorded actions. Deactivate it instead to preserve history.")
    try:
        db.execute(text("DELETE FROM patients WHERE user_id=:id"), {"id": user_id})
        db.execute(text("DELETE FROM users WHERE user_id=:id"), {"id": user_id})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This account has linked records and cannot be deleted. Deactivate it instead.") from exc
    try:
        remove_picture(user_id)
    except OSError:
        # The account deletion has committed; do not misreport it as a failure.
        import logging
        logging.getLogger(__name__).exception("Could not remove picture for deleted account %s", user_id)
    return {"detail": "Unused account deleted"}


@router.post("/patient-accounts", response_model=UserRead, status_code=201)
def create_patient_account(payload: PatientAccountCreate, db: Session = Depends(get_db), actor: User = Depends(require_role([UserRole.receptionist, UserRole.administrator]))):
    user = User(full_name=payload.full_name, email=payload.email, password_hash=get_password_hash(payload.password), role=UserRole.patient, is_active=True)
    user.patient_profile = Patient(patient_name=payload.full_name, phone_number=payload.phone_number)
    db.add(user)
    save_account(db)
    db.refresh(user)
    return user


@router.post("/staff-accounts", response_model=UserRead, status_code=201)
def create_staff_account(payload: StaffAccountCreate, db: Session = Depends(get_db), actor: User = Depends(require_role([UserRole.administrator]))):
    if payload.role not in (UserRole.doctor, UserRole.nurse, UserRole.receptionist, UserRole.administrator):
        raise HTTPException(422, "Choose a staff role")
    clinical = payload.role in (UserRole.doctor, UserRole.nurse)
    if clinical:
        if payload.department_id is None:
            raise HTTPException(422, "A department is required for doctors and nurses")
        if db.get(Department, payload.department_id) is None:
            raise HTTPException(404, "Department not found")
    elif payload.department_id is not None or payload.qualification is not None:
        raise HTTPException(422, "Clinical profile fields apply only to doctors and nurses")
    user = User(full_name=payload.full_name, email=payload.email, password_hash=get_password_hash(payload.password), role=payload.role, is_active=True)
    if clinical:
        user.staff_profile = Staff(department_id=payload.department_id, profession=payload.role.value, qualification=payload.qualification)
    db.add(user)
    save_account(db)
    db.refresh(user)
    return user
