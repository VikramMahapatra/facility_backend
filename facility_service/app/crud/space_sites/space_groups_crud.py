# app/crud/space_groups.py
import uuid
from typing import List, Optional
from sqlalchemy import or_, func, literal
from sqlalchemy.orm import Session
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...models.space_sites.space_groups import SpaceGroup
from ...schemas.space_sites.space_groups_schemas import SpaceGroupCreate, SpaceGroupOut, SpaceGroupRequest, SpaceGroupResponse, SpaceGroupUpdate

def get_space_groups(db: Session, org_id: uuid.UUID, params: SpaceGroupRequest) -> SpaceGroupResponse:
    space_group_query =  db.query(SpaceGroup).filter(SpaceGroup.org_id == org_id)
    
    if params.site_id and params.site_id.lower() != "all":
        space_group_query = space_group_query.filter(SpaceGroup.site_id == params.site_id)
        
    if params.search:
        search_term = f"%{params.search}%"
        space_group_query = space_group_query.filter(SpaceGroup.name.ilike(search_term))
    
    total = space_group_query.count()
    
    space_group_query = space_group_query.order_by(SpaceGroup.created_at.desc()).offset(params.skip).limit(params.limit)
    space_groups = space_group_query.all()
    
    space_groups_with_members = []
    for sg in space_groups:
        space_groups_with_members.append(SpaceGroupOut(
            id=sg.id,
            org_id=sg.org_id,
            site_id=sg.site_id,
            name=sg.name,
            kind=sg.kind,
            specs=sg.specs,
            group_members=len(sg.members)
        )
    )
    return {"spaceGroups": space_groups_with_members, "total": total}

def get_space_group_by_id(db: Session, group_id: str) -> SpaceGroupOut:
    sg =  db.query(SpaceGroup).filter(SpaceGroup.id == group_id).first()
    return get_space_response(sg)
    
def get_space_response(sg: SpaceGroup) -> SpaceGroupOut:
    return SpaceGroupOut(
            id=sg.id,
            org_id=sg.org_id,
            site_id=sg.site_id,
            name=sg.name,
            kind=sg.kind,
            specs=sg.specs,
            group_members=len(sg.members)
        )

def create_space_group(db: Session, group: SpaceGroupCreate) -> SpaceGroupOut:
    sg = SpaceGroup(**group.model_dump())
    db.add(sg)
    db.commit()
    db.refresh(sg)
    return get_space_response(sg)

def update_space_group(db: Session, group: SpaceGroupUpdate) -> SpaceGroupOut:
    sg = db.query(SpaceGroup).filter(SpaceGroup.id == group.id).first()
    if not sg:
        return None
    for k, v in group.dict(exclude_unset=True).items():
        setattr(sg, k, v)
    db.commit()
    db.refresh(sg)
    return get_space_response(sg)

def delete_space_group(db: Session, group_id: str) -> Optional[SpaceGroupOut]:
    db_group = get_space_group_by_id(db, group_id)
    if not db_group:
        return None
    db.delete(db_group)
    db.commit()

def get_space_group_lookup(db: Session, site_id:str, space_id:str, org_id: str):
    space_group_query = (
        db.query(
            SpaceGroup.id, 
            func.concat(
                SpaceGroup.name,
                literal(" "), 
                func.replace(SpaceGroup.kind, "_", " "),
                literal(" - "), 
                Site.name
            ).label("name")
        )
        .join(Site, SpaceGroup.site_id == Site.id)
        .filter(SpaceGroup.org_id == org_id)
    )
    
    if site_id and site_id.lower() != "all":  # only add filter if site_id is provided
        space_group_query = space_group_query.filter(SpaceGroup.site_id == site_id)
        
    if space_id:
        space_group_query = space_group_query.join(Space, func.lower(Space.kind) == func.lower(SpaceGroup.kind))
        
    return space_group_query.all()