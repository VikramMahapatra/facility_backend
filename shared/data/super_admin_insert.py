
from shared.core.database import AuthSessionLocal
from shared.models.users import Users
from auth_service.app.models.user_organizations import UserOrganization


db = AuthSessionLocal()

try:
    # ✅ Check if super admin already exists
    existing_super_admin = (
        db.query(Users)
        .filter(
            Users.is_super_admin == True,
            Users.is_deleted == False
        )
        .first()
    )

    if existing_super_admin:
        print("✅ Super Admin already exists:", existing_super_admin.email)
    else:
        super_admin = Users(
            full_name="Super Admin",
            email="superadmin@zentrixel.com",
            username="superadmin@zentrixel.com",
            status="active",
            is_super_admin=True
        )

        db.add(super_admin)
        db.commit()

        print("🔥 Super Admin created successfully")

except Exception as e:
    db.rollback()
    print("❌ Error creating Super Admin:", str(e))

finally:
    db.close()
