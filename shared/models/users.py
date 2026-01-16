import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, MetaData, String, Table, Text, func, text
from ..core.database import AuthBase
from sqlalchemy.orm import relationship


import threading
from datetime import datetime
import secrets
from passlib.context import CryptContext
from sqlalchemy import event, inspect
from shared.core.database import FacilitySessionLocal

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


class Users(AuthBase):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(200), nullable=False)

    username = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)

    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    picture_url = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="active")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)  # ✅ Soft delete field

    organizations = relationship(
        "UserOrganization",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        self.password = bcrypt_context.hash(password)

    def verify_password(self, password: str) -> bool:
        return bcrypt_context.verify(password, self.password)


# @event.listens_for(Users, 'after_insert')
# def sync_user_to_hrms_on_create(mapper, connection, target):
#     """
#     Auto-sync new user to HRMS when created
#     Uses table reflection to work with existing HRMS tables
#     """

#     if target.account_type == "tenant":
#         return

#     def sync_in_thread():
#         """Run sync in a separate thread"""
#         try:
#             sync_user_to_hrms_postgres(target)
#         except Exception as e:
#             print(f" HRMS sync error: {e}")

#     thread = threading.Thread(target=sync_in_thread, daemon=True)
#     thread.start()
#     print(f" Started HRMS sync for user: {target.email}")

# def sync_user_to_hrms_postgres(user):
#     """
#     Synchronous function to sync user to HRMS using SQLAlchemy Core
#     """
#     try:
#         pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#         # Get database sessions
#         facility_db = FacilitySessionLocal()
#         hrms_db = HrmsSessionLocal()

#         try:
#             # 1. Check if sync is enabled in system settings
#             settings = facility_db.query(SystemSetting).first()
#             if not settings or not settings.can_sync_to_hrms:
#                 print(f"HRMS sync disabled in settings")
#                 return

#             # 2. Prepare user data
#             name_parts = user.full_name.split() if user.full_name else ["User", ""]
#             first_name = name_parts[0]
#             last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
#             email = user.email or f"user_{str(user.id)[:8]}@temp.com"

#             print(f" Syncing user to HRMS: {email}")

#             try:
#                 # 3. Use SQLAlchemy Core with table reflection
#                 metadata = MetaData()

#                 # Reflect the employees table (auto-discover schema)
#                 employees_table = Table('employees', metadata, autoload_with=hrms_engine)

#                 # 4. Check if employee already exists
#                 from sqlalchemy import select
#                 stmt = select(employees_table.c.email).where(employees_table.c.email == email)
#                 result = hrms_db.execute(stmt).first()

#                 if result:
#                     print(f"Employee {email} already exists in HRMS")
#                     return

#                 # 5. Get or create default department
#                 departments_table = Table('departments', metadata, autoload_with=hrms_engine)

#                 dept_stmt = select(departments_table.c.department_id).limit(1)
#                 dept_result = hrms_db.execute(dept_stmt).first()

#                 if dept_result:
#                     department_id = dept_result[0]
#                 else:
#                     # Insert and get ID using RETURNING
#                     insert_stmt = departments_table.insert().returning(departments_table.c.department_id).values(
#                         department_name="General",
#                         description="Default department",
#                         created_at=datetime.utcnow()
#                     )
#                     dept_result = hrms_db.execute(insert_stmt).first()
#                     department_id = dept_result[0]
#                     hrms_db.flush()

#                 # 6. Get or create default role
#                 roles_table = Table('roles', metadata, autoload_with=hrms_engine)

#                 role_stmt = select(roles_table.c.role_id).where(roles_table.c.role_name == 'Employee').limit(1)
#                 role_result = hrms_db.execute(role_stmt).first()

#                 if role_result:
#                     role_id = role_result[0]
#                 else:
#                     insert_stmt = roles_table.insert().returning(roles_table.c.role_id).values(
#                         role_name="Employee",
#                         description="Default employee role",
#                         permissions="{}",
#                         created_at=datetime.utcnow()
#                     )
#                     role_result = hrms_db.execute(insert_stmt).first()
#                     role_id = role_result[0]
#                     hrms_db.flush()

#                 # 7. Generate temporary password
#                 temp_password = secrets.token_urlsafe(12)
#                 password_hash = pwd_context.hash(temp_password)

#                 # 8. Insert employee - check which columns exist
#                 employee_id = str(uuid.uuid4())

#                 # Get columns from reflected table
#                 columns = employees_table.columns.keys()
#                 print(f"Employees table columns: {columns}")

#                 # Prepare insert values
#                 insert_values = {
#                     'employee_id': employee_id,
#                     'first_name': first_name,
#                     'last_name': last_name,
#                     'email': email,
#                     'password_hash': password_hash,
#                     'department_id': department_id,
#                     'role_id': role_id,
#                     'join_date': datetime.utcnow().date(),
#                     'status': user.status or "active",
#                     'created_at': datetime.utcnow()
#                 }

#                 # Add employee_code only if column exists
#                 if 'employee_code' in columns:
#                     # Use dummy value - HRMS will regenerate it
#                     insert_values['employee_code'] = 'TEMP_CODE'

#                 # Add manager_id if column exists and you have a default
#                 if 'manager_id' in columns:
#                     # Optional: set to NULL or find a default manager
#                     insert_values['manager_id'] = None

#                 # Insert using SQLAlchemy Core
#                 insert_stmt = employees_table.insert().values(**insert_values)
#                 hrms_db.execute(insert_stmt)

#                 hrms_db.commit()
#                 print(f" Created employee {email} in HRMS")
#                 print(f" Employee ID: {employee_id}")
#                 print(f" Temporary password: {temp_password}")

#             except Exception as e:
#                 hrms_db.rollback()
#                 print(f" Error creating employee: {e}")
#                 # Print full error for debugging
#                 import traceback
#                 traceback.print_exc()

#         finally:
#             facility_db.close()
#             hrms_db.close()

#     except Exception as e:
#         print(f" HRMS sync error: {str(e)}")
#         import traceback
#         traceback.print_exc()
