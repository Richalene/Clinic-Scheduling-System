import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# -------------------------------------------------------------------
# Password Hashing setup (Argon2id)
# -------------------------------------------------------------------

# We configure Passlib to strictly use Argon2, falling back to bcrypt if needed.
# Since we explicitly installed passlib[argon2], argon2id will be used.
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# A pre-computed dummy hash of a generic password to use for constant-time mitigation
# on failed email lookups. This prevents timing attacks from revealing valid emails.
DUMMY_HASH = pwd_context.hash("dummy_password_for_constant_time_mitigation_123!")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored hash in constant time."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Returns a secure Argon2 hash of the password."""
    return pwd_context.hash(password)

def needs_rehash(hashed_password: str) -> bool:
    """Checks if the password hash needs to be updated (e.g. outdated parameters)."""
    return pwd_context.needs_update(hashed_password)

def verify_dummy() -> None:
    """
    Run a dummy password verification.
    Call this when a user is not found to equalize response times and prevent 
    email enumeration via timing side-channels.
    """
    pwd_context.verify("dummy_password", DUMMY_HASH)


# -------------------------------------------------------------------
# JWT Token Management
# -------------------------------------------------------------------

ALGORITHM = "HS256"

def create_token(subject: str, role: str, token_type: str, expires_delta: timedelta) -> str:
    """
    Generate a JWT token (access or refresh).
    """
    expire = datetime.now(timezone.utc) + expires_delta
    # Generate a unique JWT ID to track individual refresh tokens
    jti = secrets.token_urlsafe(32)
    
    to_encode = {
        "sub": subject,
        "role": role,
        "jti": jti,
        "type": token_type,
        "iat": datetime.now(timezone.utc),
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(subject: str, role: str) -> str:
    """Creates a short-lived access token (e.g., 15 minutes)."""
    delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(subject=subject, role=role, token_type="access", expires_delta=delta)

def create_refresh_token(subject: str, role: str) -> str:
    """Creates a longer-lived refresh token (e.g., 7 days)."""
    delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(subject=subject, role=role, token_type="refresh", expires_delta=delta)

def decode_token(token: str, expected_type: str) -> dict:
    """
    Decodes a JWT token, strictly pinning the algorithm to HS256 to prevent `alg: none` bypasses.
    Validates expiration automatically (via jose), and ensures claims are present.
    """
    # Pinned algorithm to prevent bypass attacks
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    
    # Verify it has all required claims
    token_type = payload.get("type")
    sub = payload.get("sub")
    role = payload.get("role")
    jti = payload.get("jti")
    
    if not all([token_type, sub, role, jti]):
        raise JWTError("Token is missing essential claims.")
        
    if token_type != expected_type:
        raise JWTError(f"Invalid token type. Expected {expected_type}.")
        
    return payload
