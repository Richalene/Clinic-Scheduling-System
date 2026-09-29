import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base

# -------------------------------------------------------------------
# Enums defined in PostgreSQL
# -------------------------------------------------------------------

class UserRole(str, enum.Enum):
    administrator = 'administrator'
    receptionist = 'receptionist'
    doctor = 'doctor'
    nurse = 'nurse'
    patient = 'patient'

class StaffProfession(str, enum.Enum):
    doctor = 'doctor'
    nurse = 'nurse'

class ResourceStatus(str, enum.Enum):
    available = 'available'
    maintenance = 'maintenance'
    out_of_service = 'out_of_service'

class AppointmentStatus(str, enum.Enum):
    requested = 'requested'
    confirmed = 'confirmed'
    cancelled = 'cancelled'
    completed = 'completed'
    no_show = 'no_show'

class AppointmentPriority(str, enum.Enum):
    normal = 'normal'
    urgent = 'urgent'

class WaitlistStatus(str, enum.Enum):
    waiting = 'waiting'
    offered = 'offered'
    booked = 'booked'
    expired = 'expired'
    cancelled = 'cancelled'

# -------------------------------------------------------------------
# ORM Models
# -------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    staff_profile = relationship("Staff", back_populates="user", uselist=False, cascade="all, delete-orphan")
    patient_profile = relationship("Patient", back_populates="user", uselist=False)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="refresh_tokens")


class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(255), nullable=False)

    staff_members = relationship("Staff", back_populates="department")
    rooms = relationship("Room", back_populates="department")
    shifts = relationship("Shift", back_populates="department")


class Staff(Base):
    __tablename__ = "staff"

    staff_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, unique=True)
    department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="RESTRICT"), nullable=False)
    profession = Column(Enum(StaffProfession), nullable=False)
    qualification = Column(String(255), nullable=True)

    user = relationship("User", back_populates="staff_profile")
    department = relationship("Department", back_populates="staff_members")
    availability = relationship("StaffAvailability", back_populates="staff", cascade="all, delete-orphan")
    shifts = relationship("Shift", back_populates="staff", cascade="all, delete-orphan")
    appointments = relationship("AppointmentStaff", back_populates="staff", cascade="all, delete-orphan")


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    patient_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=True)

    user = relationship("User", back_populates="patient_profile")
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    waitlist_entries = relationship("WaitlistEntry", back_populates="patient", cascade="all, delete-orphan")


class Service(Base):
    __tablename__ = "services"

    service_id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    requires_nurse = Column(Boolean, nullable=False, default=False)
    room_type = Column(String(100), nullable=False)

    appointments = relationship("Appointment", back_populates="service")
    waitlist_entries = relationship("WaitlistEntry", back_populates="service")


class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="RESTRICT"), nullable=False)
    room_name = Column(String(255), nullable=False)
    room_type = Column(String(100), nullable=False)
    status = Column(Enum(ResourceStatus), nullable=False, default=ResourceStatus.available)

    department = relationship("Department", back_populates="rooms")
    appointments = relationship("Appointment", back_populates="room")


class Equipment(Base):
    __tablename__ = "equipment"

    equipment_id = Column(Integer, primary_key=True, index=True)
    equipment_name = Column(String(255), nullable=False)
    equipment_type = Column(String(100), nullable=False)
    status = Column(Enum(ResourceStatus), nullable=False, default=ResourceStatus.available)

    appointments = relationship("AppointmentEquipment", back_populates="equipment", cascade="all, delete-orphan")


class StaffAvailability(Base):
    __tablename__ = "staff_availability"

    availability_id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.staff_id", ondelete="CASCADE"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)

    staff = relationship("Staff", back_populates="availability")


class Shift(Base):
    __tablename__ = "shifts"

    shift_id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.staff_id", ondelete="CASCADE"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="CASCADE"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)

    staff = relationship("Staff", back_populates="shifts")
    department = relationship("Department", back_populates="shifts")


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.service_id", ondelete="RESTRICT"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.room_id", ondelete="RESTRICT"), nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.requested)
    priority = Column(Enum(AppointmentPriority), nullable=False, default=AppointmentPriority.normal)

    patient = relationship("Patient", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    room = relationship("Room", back_populates="appointments")
    
    assigned_staff = relationship("AppointmentStaff", back_populates="appointment", cascade="all, delete-orphan")
    assigned_equipment = relationship("AppointmentEquipment", back_populates="appointment", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="appointment", cascade="all, delete-orphan")


class AppointmentStaff(Base):
    __tablename__ = "appointment_staff"

    # Note: Primary key is (appointment_id, staff_id)
    appointment_id = Column(Integer, ForeignKey("appointments.appointment_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)
    staff_id = Column(Integer, ForeignKey("staff.staff_id", ondelete="CASCADE"), primary_key=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(AppointmentStatus), nullable=False)

    appointment = relationship("Appointment", back_populates="assigned_staff")
    staff = relationship("Staff", back_populates="appointments")


class AppointmentEquipment(Base):
    __tablename__ = "appointment_equipment"

    # Note: Primary key is (appointment_id, equipment_id)
    appointment_id = Column(Integer, ForeignKey("appointments.appointment_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment.equipment_id", ondelete="CASCADE"), primary_key=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(AppointmentStatus), nullable=False)

    appointment = relationship("Appointment", back_populates="assigned_equipment")
    equipment = relationship("Equipment", back_populates="appointments")


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    waitlist_id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.service_id", ondelete="CASCADE"), nullable=False)
    preferred_date = Column(Date, nullable=False)
    status = Column(Enum(WaitlistStatus), nullable=False, default=WaitlistStatus.waiting)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="waitlist_entries")
    service = relationship("Service", back_populates="waitlist_entries")


class StatusHistory(Base):
    __tablename__ = "status_history"

    history_id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.appointment_id", ondelete="CASCADE"), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    old_status = Column(Enum(AppointmentStatus), nullable=True)
    new_status = Column(Enum(AppointmentStatus), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    appointment = relationship("Appointment", back_populates="status_history")
    changer = relationship("User")
