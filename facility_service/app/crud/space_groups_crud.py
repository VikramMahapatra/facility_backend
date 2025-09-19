# app/crud/space_groups.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.space_groups import SpaceGroup
from ..schemas.space_groups_schemas import SpaceGroupCreate, SpaceGroupUpdate

def get_space_groups(db: Session, skip: int = 0, limit: int = 100) -> List[SpaceGroup]:
    return db.query(SpaceGroup).offset(skip).limit(limit).all()

def get_space_group_by_id(db: Session, group_id: str) -> Optional[SpaceGroup]:
    return db.query(SpaceGroup).filter(SpaceGroup.id == group_id).first()

def create_space_group(db: Session, group: SpaceGroupCreate) -> SpaceGroup:
    db_group = SpaceGroup(id=str(uuid.uuid4()), **group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def update_space_group(db: Session, group_id: str, group: SpaceGroupUpdate) -> Optional[SpaceGroup]:
    db_group = get_space_group_by_id(db, group_id)
    if not db_group:
        return None
    for k, v in group.dict(exclude_unset=True).items():
        setattr(db_group, k, v)
    db.commit()
    db.refresh(db_group)
    return db_group

def delete_space_group(db: Session, group_id: str) -> Optional[SpaceGroup]:
    db_group = get_space_group_by_id(db, group_id)
    if not db_group:
        return None
    db.delete(db_group)
    db.commit()
    return db_group
