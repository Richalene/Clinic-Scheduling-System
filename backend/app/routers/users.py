
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Patient, User, UserRole
from app.schemas import UserCreate, UserRead, UserUpdate
from app.security import get_password_hash

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
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/me", response_model=UserRead)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get the currently logged-in user."""
    return current_user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role([UserRole.administrator]))
):
    """Admin-only: update a user's details, role, or active status."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Prevent the admin from accidentally deactivating themselves permanently 
    # without a recovery mechanism, though it is allowed technically.
    
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
        
    db.commit()
    db.refresh(user)
    return user
