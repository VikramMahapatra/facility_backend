from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from shared.config import AUTH_DATABASE_URL, FACILITY_DATABASE_URL

Base = declarative_base()

auth_engine = create_engine(AUTH_DATABASE_URL)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)

facility_engine = create_engine(FACILITY_DATABASE_URL)
FacilitySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=facility_engine)

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
        
        

