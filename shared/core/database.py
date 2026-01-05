from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from shared.core.config import AUTH_DATABASE_URL, FACILITY_DATABASE_URL , HRMS_DATABASE_URL

# Separate bases
AuthBase = declarative_base()
Base = declarative_base()

POOL_SIZE = 2
MAX_OVERFLOW = 2

# Auth DB
auth_engine = create_engine(
    AUTH_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=POOL_SIZE,          # max idle connections
    max_overflow=MAX_OVERFLOW,      # max temporary extra connections
    pool_timeout=30       # wait time before failing
)
AuthSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=auth_engine)

# Facility DB
facility_engine = create_engine(
    FACILITY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=30
)
FacilitySessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=facility_engine)

     
# HRMS PostgreSQL Engine (UPDATED)
hrms_engine = create_engine(
    HRMS_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=30
)
HrmsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=hrms_engine)


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
        
#hrms dependancy
def get_hrms_db():
    db = HrmsSessionLocal()
    try:
        yield db
    finally:
        db.close()