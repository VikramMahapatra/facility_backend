# app/crud/orgs.py
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from ...models.space_sites.orgs import Org
from ...schemas.space_sites.orgs_schemas import OrgCreate, OrgOut, OrgUpdate


def get_orgs(db: Session, skip: int = 0, limit: int = 100) -> List[Org]:
    return db.query(Org).offset(skip).limit(limit).all()


def get_org_by_id(db: Session, org_id: str) -> Optional[OrgOut]:
    db_org = (
        db.query(Org)
        .filter(Org.id == org_id)
        .first()
    )

    if not db_org:
        return None

    return OrgOut.model_validate(db_org, from_attributes=True)


def create_org(db: Session, org: OrgCreate) -> Org:
    db_org = Org(**org.dict())
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    return db_org


def update_org(db: Session, org: OrgUpdate) -> Optional[Org]:
    db_org = db.query(Org).filter(Org.id == org.id).first()
    if not db_org:
        return None
    for key, value in org.dict(exclude_unset=True).items():
        setattr(db_org, key, value)
    db.commit()
    db.refresh(db_org)
    return db_org


def delete_org(db: Session, org_id: str) -> Optional[Org]:
    db_org = db.query(Org).filter(Org.id == org_id).first()
    if not db_org:
        return None
    db.delete(db_org)
    db.commit()
    return db_org
