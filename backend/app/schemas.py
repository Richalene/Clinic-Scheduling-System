from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import (
    AppointmentPriority,
    AppointmentStatus,
    ResourceStatus,
    StaffProfession,
    UserRole,
    WaitlistStatus,
)

# -------------------------------------------------------------------
# Base Configuration
# -------------------------------------------------------------------

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class InputSchema(BaseModel):
    # Reject unknown fields to prevent mass assignment vulnerabilities
    model_config = ConfigDict(extra="forbid")

# -------------------------------------------------------------------
# Token Schemas
# -------------------------------------------------------------------

class Token(BaseSchema):
    access_token: str
    token_type: str

class TokenPayload(BaseSchema):
    sub: str
    role: UserRole
    jti: str
    type: str

# -------------------------------------------------------------------
# User Schemas
# -------------------------------------------------------------------

class UserBase(InputSchema):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=12, max_length=128)
    role: UserRole

class AccountDeleteRequest(InputSchema):
    admin_password: str = Field(min_length=1, max_length=128)


class UserUpdate(InputSchema):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    is_active: bool | None = None
    role: UserRole | None = None

    @field_validator("full_name", "email", "is_active", "role")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        if isinstance(value, str) and len(value.strip()) < 2:
            raise ValueError("This field cannot be blank")
        return value.strip() if type(value) is str else value

class ProfileUpdate(InputSchema):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone_number: str | None = Field(None, max_length=50)

    @field_validator("full_name", "email")
    @classmethod
    def reject_blank(cls, value):
        if value is None or len(value.strip()) < 2:
            raise ValueError("This field cannot be blank or null")
        return value.strip()

class UserRead(BaseSchema):
    user_id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    # CRITICAL: password_hash, failed_login_attempts, locked_until are explicitly omitted

class UserMeRead(UserRead):
    profile_picture: str | None = None
    patient_id: int | None = None
    staff_id: int | None = None
    phone_number: str | None = None

# -------------------------------------------------------------------
# Department Schemas
# -------------------------------------------------------------------

class DepartmentBase(InputSchema):
    department_name: str = Field(..., min_length=2, max_length=255)

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentRead(BaseSchema):
    department_id: int
    department_name: str

# -------------------------------------------------------------------
# Staff Schemas
# -------------------------------------------------------------------

class StaffBase(InputSchema):
    department_id: int
    profession: StaffProfession
    qualification: str | None = Field(None, max_length=255)

class StaffCreate(StaffBase):
    user_id: int

class StaffUpdate(InputSchema):
    department_id: int | None = None
    profession: StaffProfession | None = None
    qualification: str | None = Field(None, max_length=255)

class StaffRead(BaseSchema):
    staff_id: int
    user_id: int
    department_id: int
    profession: StaffProfession
    qualification: str | None
    user: UserRead
    department: DepartmentRead

# -------------------------------------------------------------------
# Patient Schemas
# -------------------------------------------------------------------

class PatientBase(InputSchema):
    patient_name: str = Field(..., min_length=2, max_length=255)
    phone_number: str | None = Field(None, max_length=50)

class PatientCreate(PatientBase):
    user_id: int | None = None

class PatientUpdate(InputSchema):
    patient_name: str | None = Field(None, min_length=2, max_length=255)
    phone_number: str | None = Field(None, max_length=50)

class PatientRead(BaseSchema):
    patient_id: int
    user_id: int | None
    patient_name: str
    phone_number: str | None

# -------------------------------------------------------------------
# Service Schemas
# -------------------------------------------------------------------

class ServiceBase(InputSchema):
    service_name: str = Field(..., min_length=2, max_length=255)
    duration_minutes: int = Field(..., gt=0)
    requires_nurse: bool = False
    room_type: str = Field(..., min_length=2, max_length=100)

class ServiceCreate(ServiceBase):
    pass

class ServiceRead(BaseSchema):
    service_id: int
    service_name: str
    duration_minutes: int
    requires_nurse: bool
    room_type: str

# -------------------------------------------------------------------
# Room & Equipment Schemas
# -------------------------------------------------------------------

class RoomRead(BaseSchema):
    room_id: int
    department_id: int
    room_name: str
    room_type: str
    status: ResourceStatus

class EquipmentRead(BaseSchema):
    equipment_id: int
    equipment_name: str
    equipment_type: str
    status: ResourceStatus

# -------------------------------------------------------------------
# Appointment Schemas
# -------------------------------------------------------------------

class AppointmentBase(InputSchema):
    patient_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_at: AwareDatetime
    priority: AppointmentPriority = AppointmentPriority.normal

class AppointmentCreate(AppointmentBase):
    doctor_id: int | None = Field(None, gt=0)
    # Equipment requirements are selected explicitly; the database has no
    # service-to-equipment requirement table. Room/staff are assigned by system.
    equipment_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("equipment_ids")
    @classmethod
    def validate_equipment_ids(cls, value):
        if any(item <= 0 for item in value) or len(value) != len(set(value)):
            raise ValueError("equipment_ids must contain unique positive IDs")
        return value

class AvailableSlotRead(BaseSchema):
    candidate_start: datetime
    candidate_end: datetime
    room_id: int
    doctor_id: int
    nurse_id: int | None
    equipment_ids: list[int] = Field(default_factory=list)

class AppointmentStaffRead(BaseSchema):
    staff_id: int

class AppointmentEquipmentRead(BaseSchema):
    equipment_id: int

class AppointmentUpdate(InputSchema):
    start_at: datetime | None = None
    status: AppointmentStatus | None = None
    priority: AppointmentPriority | None = None

class AppointmentRead(BaseSchema):
    appointment_id: int
    patient_id: int
    service_id: int
    room_id: int | None
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
    priority: AppointmentPriority
    
    # Nested minimal details for frontend
    patient: PatientRead | None = None
    service: ServiceRead | None = None
    room: RoomRead | None = None
    assigned_staff: list[AppointmentStaffRead] = Field(default_factory=list)
    assigned_equipment: list[AppointmentEquipmentRead] = Field(default_factory=list)

# -------------------------------------------------------------------
# Waitlist Schemas
# -------------------------------------------------------------------

class WaitlistEntryBase(InputSchema):
    patient_id: int
    service_id: int
    preferred_date: date

class WaitlistEntryCreate(WaitlistEntryBase):
    pass

class WaitlistEntryRead(BaseSchema):
    waitlist_id: int
    patient_id: int
    service_id: int
    preferred_date: date
    status: WaitlistStatus
    created_at: datetime


class PatientAccountCreate(UserBase):
    password: str = Field(min_length=12, max_length=128)
    phone_number: str | None = Field(None, max_length=50)


class StaffAccountCreate(UserCreate):
    department_id: int | None = Field(None, gt=0)
    qualification: str | None = Field(None, max_length=255)
