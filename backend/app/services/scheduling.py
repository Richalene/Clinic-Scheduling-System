from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    AppointmentStatus,
    AppointmentStaff,
    AppointmentEquipment,
    Equipment,
    Patient,
    ResourceStatus,
    Room,
    Staff,
    Service,
    UserRole,
    WaitlistEntry,
    WaitlistStatus,
)
from app.schemas import AppointmentCreate

# Availability is advisory. Booking searches again in its transaction, locks
# selected resources, and relies on PostgreSQL exclusion constraints as the
# final concurrency guard (including callers outside this API).


def _equipment(db: Session, equipment_ids: list[int], lock: bool = False):
    if len(equipment_ids) > 50 or any(i <= 0 for i in equipment_ids) or len(set(equipment_ids)) != len(equipment_ids):
        raise HTTPException(status_code=400, detail="equipment_ids must contain at most 50 unique positive IDs")
    if not equipment_ids:
        return []
    query = db.query(Equipment).filter(Equipment.equipment_id.in_(equipment_ids)).order_by(Equipment.equipment_id)
    if lock:
        query = query.with_for_update().populate_existing()
    items = query.all()
    if len(items) != len(equipment_ids):
        raise HTTPException(status_code=404, detail="Equipment not found")
    return items


def get_available_slots(
    db: Session,
    service_id: int,
    from_time: datetime,
    to_time: datetime,
    equipment_ids: list[int] | None = None,
    doctor_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return the existing SQL helper's candidates, filtered for equipment."""
    if from_time.utcoffset() is None or to_time.utcoffset() is None:
        raise HTTPException(status_code=400, detail="Times must include a timezone offset")
    if from_time >= to_time:
        raise HTTPException(status_code=400, detail="from_time must be before to_time")
    if to_time - from_time > timedelta(days=31):
        raise HTTPException(status_code=400, detail="Search range cannot exceed 31 days")
    if from_time < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot search for slots in the past")
    service = db.query(Service).filter(Service.service_id == service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if doctor_id is not None:
        doctor = db.query(Staff).filter(Staff.staff_id == doctor_id).first()
        if doctor is None or doctor.profession.value != 'doctor':
            raise HTTPException(404, "Doctor not found")
        return _doctor_slots(db, service, from_time, to_time, equipment_ids or [], doctor_id)
    items = _equipment(db, equipment_ids or [])
    if any(item.status != ResourceStatus.available for item in items):
        return []
    # The existing helper limits its result to 10 combinations. Call it for
    # each candidate start so equipment conflicts are excluded BEFORE the
    # overall limit; otherwise an occupied morning can hide a free afternoon.
    result = db.execute(
        text("""
            SELECT DISTINCT slot.candidate_start, slot.candidate_end,
                slot.room_id, slot.doctor_id,
                CASE WHEN :requires_nurse THEN slot.nurse_id ELSE NULL END AS nurse_id
            FROM generate_series(
                CAST(:from_t AS timestamptz),
                CAST(:to_t AS timestamptz) - make_interval(mins => :duration),
                interval '30 minutes'
            ) AS candidate(start_at)
            CROSS JOIN LATERAL find_available_slots(
                :svc, candidate.start_at,
                candidate.start_at + make_interval(mins => :duration)
            ) AS slot
            WHERE NOT EXISTS (
                SELECT 1 FROM appointment_equipment ae
                WHERE ae.equipment_id = ANY(CAST(:equipment_ids AS integer[]))
                  AND ae.status IN ('requested', 'confirmed')
                  AND ae.start_at < slot.candidate_end
                  AND ae.end_at > slot.candidate_start
            )
            ORDER BY candidate_start, room_id, doctor_id, nurse_id
            LIMIT 10
        """),
        {"svc": service_id, "from_t": from_time, "to_t": to_time,
         "duration": service.duration_minutes, "requires_nurse": service.requires_nurse,
         "equipment_ids": equipment_ids or []},
    )
    return [{**dict(row), "equipment_ids": sorted(equipment_ids or [])} for row in result.mappings()]


def _doctor_slots(db, service, from_time, to_time, equipment_ids, doctor_id):
    # Filter the chosen doctor before LIMIT; the legacy SQL helper limits its
    # combinations internally and can otherwise hide this doctor's openings.
    items = _equipment(db, equipment_ids)
    if any(item.status != ResourceStatus.available for item in items):
        return []
    rows = db.execute(text("""
        WITH candidates AS (
            SELECT t AS start_at, t + make_interval(mins => :duration) AS end_at
            FROM generate_series(CAST(:start AS timestamptz), CAST(:end AS timestamptz) - make_interval(mins => :duration), interval '30 minutes') t
        ), available_staff AS (
            SELECT DISTINCT c.start_at, c.end_at, s.staff_id, s.profession
            FROM candidates c
            JOIN shifts sh ON sh.start_at <= c.start_at AND sh.end_at >= c.end_at
            JOIN staff s ON s.staff_id = sh.staff_id
            WHERE NOT EXISTS (SELECT 1 FROM appointment_staff a WHERE a.staff_id=s.staff_id
                AND a.status IN ('requested','confirmed') AND a.start_at<c.end_at AND a.end_at>c.start_at)
        )
        SELECT DISTINCT c.start_at AS candidate_start, c.end_at AS candidate_end,
            r.room_id, d.staff_id AS doctor_id, n.staff_id AS nurse_id
        FROM candidates c
        JOIN available_staff d ON d.start_at=c.start_at AND d.staff_id=:doctor AND d.profession='doctor'
        CROSS JOIN rooms r
        LEFT JOIN available_staff n ON :nurse AND n.start_at=c.start_at AND n.profession='nurse'
        WHERE r.status='available' AND r.room_type=:room_type
            AND (NOT :nurse OR n.staff_id IS NOT NULL)
            AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.room_id=r.room_id
                AND a.status IN ('requested','confirmed') AND a.start_at<c.end_at AND a.end_at>c.start_at)
            AND NOT EXISTS (SELECT 1 FROM appointment_equipment a WHERE a.equipment_id=ANY(CAST(:equipment AS integer[]))
                AND a.status IN ('requested','confirmed') AND a.start_at<c.end_at AND a.end_at>c.start_at)
        ORDER BY candidate_start, room_id, doctor_id, nurse_id LIMIT 10
    """), {"start":from_time,"end":to_time,"duration":service.duration_minutes,"doctor":doctor_id,
           "nurse":service.requires_nurse,"room_type":service.room_type,"equipment":equipment_ids})
    return [{**dict(row), "equipment_ids":sorted(equipment_ids)} for row in rows.mappings()]


def book_appointment(
    db: Session,
    user_id: int,
    user_role: UserRole,
    appointment_in: AppointmentCreate,
) -> Appointment:
    """Reserve room, staff and selected equipment in one transaction.

    All new bookings reserve resources and remain requested until reviewed.
    The dependency may already have started this session's transaction while
    authenticating, so do not nest db.begin() or commit before assignments exist.
    """
    try:
        service = db.query(Service).filter(Service.service_id == appointment_in.service_id).first()
        if service is None:
            raise HTTPException(status_code=404, detail="Service not found")
        patient = db.query(Patient).filter(Patient.patient_id == appointment_in.patient_id).first()
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        if user_role == UserRole.patient:
            if patient.user_id != user_id:
                raise HTTPException(status_code=403, detail="You can only book appointments for yourself")
            if appointment_in.priority == "urgent":
                raise HTTPException(status_code=403, detail="Patients cannot request urgent priority")

        end_at = appointment_in.start_at + timedelta(minutes=service.duration_minutes)
        # An exact start needs a window equal to the service duration, not zero.
        slots = get_available_slots(db, service.service_id, appointment_in.start_at, end_at, appointment_in.equipment_ids, appointment_in.doctor_id)
        if not slots:
            raise HTTPException(status_code=409, detail="No available resources at the requested time")
        chosen = slots[0]
        staff_ids = sorted({i for i in [chosen["doctor_id"], chosen["nurse_id"]] if i is not None})
        # Consistent lock order prevents competing API bookings from assigning
        # the same resources between validation and insertion.
        db.query(Room).filter(Room.room_id == chosen["room_id"]).with_for_update().all()
        db.query(Staff).filter(Staff.staff_id.in_(staff_ids)).order_by(Staff.staff_id).with_for_update().all()
        _equipment(db, appointment_in.equipment_ids, lock=True)
        checked = get_available_slots(db, service.service_id, appointment_in.start_at, end_at, appointment_in.equipment_ids, appointment_in.doctor_id)
        if chosen not in checked:
            raise HTTPException(status_code=409, detail="Slot is no longer available; search again")

        db.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user_id)})
        booking_status = AppointmentStatus.requested
        new_apt = Appointment(
            patient_id=patient.patient_id,
            service_id=service.service_id,
            room_id=chosen["room_id"],
            start_at=appointment_in.start_at,
            end_at=end_at,
            status=booking_status,
            priority=appointment_in.priority,
        )
        db.add(new_apt)
        db.flush()
        for staff_id in staff_ids:
            db.add(AppointmentStaff(appointment_id=new_apt.appointment_id, staff_id=staff_id,
                                   start_at=new_apt.start_at, end_at=end_at, status=booking_status))
        for equipment_id in appointment_in.equipment_ids:
            db.add(AppointmentEquipment(appointment_id=new_apt.appointment_id, equipment_id=equipment_id,
                                       start_at=new_apt.start_at, end_at=end_at, status=booking_status))
        db.commit()  # Includes deferred doctor/nurse checks, not just INSERT errors.
    except HTTPException:
        db.rollback()
        raise
    except DBAPIError as exc:
        db.rollback()
        code = getattr(exc.orig, "pgcode", None)
        if isinstance(exc, IntegrityError) or code in {"P0001", "40001", "40P01"}:
            raise HTTPException(status_code=409, detail="Resources conflict or no longer meet booking requirements") from exc
        raise
    db.refresh(new_apt)
    return new_apt


def cancel_appointment(db: Session, appointment_id: int, user_id: int) -> Appointment:
    """
    Cancels an appointment, freeing resources, and checks the waitlist to offer the slot.
    """
    apt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).with_for_update().first()
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if apt.status in [AppointmentStatus.cancelled, AppointmentStatus.completed]:
        raise HTTPException(status_code=400, detail="Cannot cancel an already completed or cancelled appointment")

    db.execute(text("SELECT set_config('app.current_user_id', :user_id, true)"), {"user_id": str(user_id)})
    # Cancel it
    apt.status = AppointmentStatus.cancelled
    # status_history is handled automatically by the DB trigger `tr_log_appointment_status_history`
    
    # Check waitlist for matching service and preferred date
    # Preferred date is just a Date, so we match it against the cancelled appointment's Date
    apt_date = apt.start_at.date()
    waitlist_entries = db.query(WaitlistEntry).filter(
        WaitlistEntry.service_id == apt.service_id,
        WaitlistEntry.preferred_date == apt_date,
        WaitlistEntry.status == WaitlistStatus.waiting
    ).order_by(WaitlistEntry.created_at.asc()).all()
    
    # Offer to the first person on the waitlist
    if waitlist_entries:
        first_entry = waitlist_entries[0]
        first_entry.status = WaitlistStatus.offered
        # (In a real system, we'd trigger an email/SMS notification here)

    try:
        db.commit()
        db.refresh(apt)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to cancel appointment")
        
    return apt
