# app/crud/spaces.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.space_sites.spaces import Space
from app.schemas.spaces_schemas import SpaceCreate, SpaceUpdate

def get_spaces(db: Session, skip: int = 0, limit: int = 100) -> List[Space]:
    return db.query(Space).offset(skip).limit(limit).all()

def get_space_by_id(db: Session, space_id: str) -> Optional[Space]:
    return db.query(Space).filter(Space.id == space_id).first()

def create_space(db: Session, space: SpaceCreate) -> Space:
    db_space = Space(id=str(uuid.uuid4()), **space.dict())
    db.add(db_space)
    db.commit()
    db.refresh(db_space)
    return db_space

def update_space(db: Session, space_id: str, space: SpaceUpdate) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None
    for k, v in space.dict(exclude_unset=True).items():
        setattr(db_space, k, v)
    db.commit()
    db.refresh(db_space)
    return db_space

def delete_space(db: Session, space_id: str) -> Optional[Space]:
    db_space = get_space_by_id(db, space_id)
    if not db_space:
        return None
    db.delete(db_space)
    db.commit()
    return db_space
