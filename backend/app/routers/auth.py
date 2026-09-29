from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, limiter
from app.models import RefreshToken, User
from app.schemas import Token
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    needs_rehash,
    verify_dummy,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate a user and return an access token.
    Sets an HttpOnly cookie with the refresh token.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    # Generic error message to prevent email enumeration
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        # Run dummy verify to mitigate timing attacks
        verify_dummy()
        raise generic_error

    if not user.is_active:
        verify_dummy()
        raise generic_error

    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to too many failed attempts. Try again later."
        )

    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        # Handle failed attempt
        user.failed_login_attempts += 1
        # Exponential backoff (e.g., 5 failures -> 5 mins lock)
        if user.failed_login_attempts >= 5:
            lock_duration = 5 * (2 ** (user.failed_login_attempts - 5))
            # Cap lock duration to 24 hours to prevent permanent lockout
            lock_duration = min(lock_duration, 1440)
            user.locked_until = now + timedelta(minutes=lock_duration)
        db.commit()
        raise generic_error

    # Login successful, reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    
    # Transparent rehash if parameters updated
    if needs_rehash(user.password_hash):
        user.password_hash = get_password_hash(form_data.password)
        
    db.commit()

    # Generate tokens
    access_token = create_access_token(subject=str(user.user_id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.user_id), role=user.role)
    
    # Store refresh token hash for rotation
    rt_hash = get_password_hash(refresh_token)
    new_rt_record = RefreshToken(
        user_id=user.user_id,
        token_hash=rt_hash,
        expires_at=now + timedelta(days=7) # Matches config
    )
    db.add(new_rt_record)
    db.commit()

    # Set HttpOnly, Secure, SameSite cookie for the refresh token to prevent XSS exfiltration
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True, # HTTPS only in production
        samesite="strict",
        max_age=7 * 24 * 60 * 60
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
@limiter.limit("5/minute")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Exchanges a valid refresh token (from cookies) for a new access token.
    Rotates the refresh token (issues a new one, invalidates the old one).
    """
    token_str = request.cookies.get("refresh_token")
    if not token_str:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        payload = decode_token(token_str, expected_type="refresh")
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Find the token hash in the database
    # Since we only store hashes, we must iterate through the user's active tokens and verify
    # (In a highly loaded system, storing a JTI to quickly find the record before hashing is faster,
    # but since a user typically has few active sessions, iterating is acceptable here).
    active_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.user_id,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).all()

    matched_token_record = None
    for rt_record in active_tokens:
        if verify_password(token_str, rt_record.token_hash):
            matched_token_record = rt_record
            break

    if not matched_token_record:
        # Token reuse detected! Revoke all tokens for this user family to be safe.
        db.query(RefreshToken).filter(RefreshToken.user_id == user.user_id).update({"revoked": True})
        db.commit()
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid refresh token or token reuse detected.")

    # Invalidate the used token
    matched_token_record.revoked = True
    
    # Generate new tokens (Rotation)
    new_access_token = create_access_token(subject=str(user.user_id), role=user.role)
    new_refresh_token = create_refresh_token(subject=str(user.user_id), role=user.role)
    
    # Store new refresh token hash
    new_rt_hash = get_password_hash(new_refresh_token)
    new_rt_record = RefreshToken(
        user_id=user.user_id,
        token_hash=new_rt_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db.add(new_rt_record)
    db.commit()

    # Update cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60
    )

    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logs out the user by revoking the refresh token provided in the cookie
    and deleting the cookie from the browser.
    """
    token_str = request.cookies.get("refresh_token")
    if token_str:
        active_tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.user_id,
            RefreshToken.revoked == False
        ).all()

        for rt_record in active_tokens:
            if verify_password(token_str, rt_record.token_hash):
                rt_record.revoked = True
                db.commit()
                break

    response.delete_cookie("refresh_token")
    return {"detail": "Successfully logged out"}


@router.post("/change-password")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Changes the user's password and revokes all their existing refresh tokens 
    to force re-login on all devices.
    """
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
        
    current_user.password_hash = get_password_hash(payload.new_password)
    
    # Revoke all tokens
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.user_id).update({"revoked": True})
    db.commit()
    
    return {"detail": "Password updated successfully. All other sessions logged out."}
