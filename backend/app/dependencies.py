
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security import decode_token

# OAuth2 scheme for Swagger UI and token extraction from headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

def get_token(request: Request, token: str = Depends(oauth2_scheme)) -> str:
    """Extract token from Authorization header or fallback to cookie."""
    if token:
        return token
    # Fallback to HttpOnly cookie for refresh token endpoints if needed,
    # though access tokens are preferred in the Authorization header.
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Strip 'Bearer ' if present in cookie
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(get_token), db: Session = Depends(get_db)
) -> User:
    """
    Decodes the JWT token and fetches the current user from the database.
    Enforces that the user exists and is active. Re-reads role from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Pinned HS256 validation prevents bypass attacks
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.user_id == int(user_id)).first()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive or disabled user")
        
    return user


def require_role(allowed_roles: list[UserRole]):
    """
    Dependency factory to enforce role-based access control.
    Role is strictly verified against the live database user record, 
    not just the JWT claim, preventing stale privilege escalation.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough privileges"
            )
        return current_user
    return role_checker
