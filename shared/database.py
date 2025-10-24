from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from shared.config import AUTH_DATABASE_URL, FACILITY_DATABASE_URL

# Separate bases
AuthBase = declarative_base()
Base = declarative_base()

# Auth DB
auth_engine = create_engine(
    AUTH_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,          # max idle connections
    max_overflow=10,      # max temporary extra connections
    pool_timeout=30       # wait time before failing
)
AuthSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=auth_engine)

# Facility DB
facility_engine = create_engine(
    FACILITY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30
)
FacilitySessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=facility_engine)

# Dependency


def get_auth_db():
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_facility_db():
    db = FacilitySessionLocal()
    try:
        yield db
    finally:
        db.close()
