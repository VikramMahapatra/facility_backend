from uuid import UUID

from shared.core.database import AuthSessionLocal
from shared.models.users import Users


def get_user_name(user_id: UUID):
    auth_db = AuthSessionLocal()
    try:
        user = auth_db.query(Users).filter(Users.id == user_id).first()
        return user.full_name if user else None
    finally:
        auth_db.close()


def get_user_detail(user_id: UUID):
    auth_db = AuthSessionLocal()
    try:
        user = auth_db.query(Users).filter(Users.id == user_id).first()
        return user if user else None
    finally:
        auth_db.close()


def get_users_bulk(user_ids):
    auth_db = AuthSessionLocal()
    try:
        users = (
            auth_db.query(Users)
            .filter(Users.id.in_(user_ids))
            .all()
        )

        return {u.id: u for u in users}
    finally:
        auth_db.close()
