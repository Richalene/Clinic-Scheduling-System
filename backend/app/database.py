from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# Determine if we should echo SQL statements
# echo=True is helpful for debugging but can leak sensitive data in production
is_development = settings.ENVIRONMENT.lower() == "development"

# Create the SQLAlchemy engine
# pool_pre_ping=True tests the connection for liveness upon each checkout from the pool
engine = create_engine(
    settings.DATABASE_URL,
    echo=is_development,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory for creating new DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative ORM models
Base = declarative_base()

def get_db() -> Generator:
    """
    FastAPI dependency that yields a database session and ensures it is closed
    after the request completes. If an exception occurs, the session is safely closed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
