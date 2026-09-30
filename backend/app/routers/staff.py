
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Department, Staff, User, UserRole
from app.schemas import (
    DepartmentCreate,
    DepartmentRead,
    StaffCreate,
    StaffRead,
)

router = APIRouter(prefix="/staff", tags=["Staff"])

# -------------------------------------------------------------------
# Departments
# -------------------------------------------------------------------

@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List departments. Open to any authenticated user."""
    return db.query(Department).offset(skip).limit(limit).all()

@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    dept_in: DepartmentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator]))
):
    """Create a new department (Admin only)."""
    dept = Department(department_name=dept_in.department_name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

# -------------------------------------------------------------------
# Staff Profiles
# -------------------------------------------------------------------

@router.get("/", response_model=list[StaffRead])
def list_staff(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List staff. Open to any authenticated user."""
    return db.query(Staff).offset(skip).limit(limit).all()

@router.post("/", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
def create_staff(
    staff_in: StaffCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role([UserRole.administrator]))
):
    """Link an existing user account to a new staff profile (Admin only)."""
    user = db.query(User).filter(User.user_id == staff_in.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role not in [UserRole.doctor, UserRole.nurse]:
        raise HTTPException(status_code=400, detail="User must have doctor or nurse role to be staff")
        
    if db.query(Staff).filter(Staff.user_id == staff_in.user_id).first():
        raise HTTPException(status_code=409, detail="User already has a staff profile")
        
    staff = Staff(
        user_id=staff_in.user_id,
        department_id=staff_in.department_id,
        profession=staff_in.profession,
        qualification=staff_in.qualification
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff
