# app/crud/space_group_members.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.space_group_members import SpaceGroupMember
from app.schemas.space_group_members import SpaceGroupMemberCreate

def get_space_group_members(db: Session, skip: int = 0, limit: int = 100) -> List[SpaceGroupMember]:
    return db.query(SpaceGroupMember).offset(skip).limit(limit).all()

def get_space_group_member_by_id(db: Session, group_id: str, space_id: str) -> Optional[SpaceGroupMember]:
    return db.query(SpaceGroupMember).filter(
        SpaceGroupMember.group_id == group_id,
        SpaceGroupMember.space_id == space_id
    ).first()

def create_space_group_member(db: Session, member: SpaceGroupMemberCreate) -> SpaceGroupMember:
    db_member = SpaceGroupMember(**member.dict())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

def delete_space_group_member(db: Session, group_id: str, space_id: str) -> Optional[SpaceGroupMember]:
    db_member = get_space_group_member_by_id(db, group_id, space_id)
    if not db_member:
        return None
    db.delete(db_member)
    db.commit()
    return db_member
