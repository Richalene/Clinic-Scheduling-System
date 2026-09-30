from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import limiter
from slowapi import _rate_limit_exceeded_handler
from app.routers import appointments, auth, lookups, reports, shifts, staff, users, waitlist

# Conditionally disable docs in production
docs_kwargs = {}
if settings.ENVIRONMENT.lower() == "production":
    docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="Clinic Scheduling System API",
    version="1.0.0",
    **docs_kwargs
)

# Apply Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list,
    allow_credentials=True, # Required for HttpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Generic IntegrityError Handler to prevent DB leaks
@app.exception_handler(IntegrityError)
async def sqlalchemy_integrity_error_handler(request: Request, exc: IntegrityError):
    # Log the exact error securely on the backend only
    # print(exc) # Use proper logging in production
    return JSONResponse(
        status_code=409,
        content={"detail": "A conflict occurred with the database constraint (e.g. unique violation or overlap)."}
    )

# Register Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(staff.router)
app.include_router(shifts.router)
app.include_router(appointments.router)
app.include_router(waitlist.router)
app.include_router(reports.router)
app.include_router(lookups.router)

@app.get("/health", tags=["Health"])
def health_check():
    """Public health check endpoint."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}
