# app/crud/space_group_members.py
import uuid
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import func, cast, or_, case
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from ...schemas.space_sites.space_groups_schemas import SpaceGroupOut
from ...schemas.space_sites.spaces_schemas import SpaceOut
from ...models.space_sites.sites import Site
from ...models.space_sites.space_groups import SpaceGroup
from ...models.space_sites.spaces import Space
from ...models.space_sites.space_group_members import SpaceGroupMember
from ...schemas.space_sites.space_group_members_schemas import SpaceGroupMemberBase, SpaceGroupMemberCreate, SpaceGroupMemberOut, SpaceGroupMemberRequest, SpaceGroupMemberResponse, SpaceGroupMemberUpdate

def build_filters(org_id : UUID, params: SpaceGroupMemberRequest):
    filters = []

    # org_id comes from SpaceGroup
    filters.append(Space.org_id == org_id)
     
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == params.site_id)
        
    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(Space.name.ilike(search_term), SpaceGroup.name.ilike(search_term)))

    return filters

def get_member_query(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    filters = build_filters(org_id, params)
    return db.query(SpaceGroupMember).filter(*filters)
        
def get_members_overview(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    filters = build_filters(org_id, params)
        
    counts =(
        db.query(
            func.count('*').label("total_assignments"),
            func.count(func.distinct(SpaceGroupMember.space_id)).label("total_spaces"),
            func.count(func.distinct(SpaceGroupMember.group_id)).label("total_groups"),
        )
        .select_from(SpaceGroupMember)  
        .join(Space, Space.id == SpaceGroupMember.space_id)\
        .join(SpaceGroup, SpaceGroup.id == SpaceGroupMember.group_id)\
        .filter(*filters)
        .one()
    )
    
    return {
        "totalAssignments": counts.total_assignments,
        "groupUsed": counts.total_spaces,
        "spaceAssigned": counts.total_groups      
    }
    
def get_assignment_preview(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    assignment_preview_query = (
            db.query(
                Site.name.label("site_name"),
                Space.name.label("space_name"),
                Space.code.label("space_code"),
                func.replace(SpaceGroup.kind, "_", " ").label("kind"),
                SpaceGroup.name.label("group_name"),
                SpaceGroup.specs
            )
            .select_from(Space) 
            .join(Site, Site.id == Space.site_id)
            .join(SpaceGroup, Space.kind == SpaceGroup.kind)
        )
    
    if params.space_id:
        assignment_preview_query = assignment_preview_query.filter(SpaceGroupMember.space_id == params.space_id)
    if params.group_id:
        assignment_preview_query = assignment_preview_query.filter(SpaceGroupMember.group_id == params.group_id)

    result = assignment_preview_query.first()
    if not result:
        raise HTTPException(status_code=404, detail="Assignment preview not found")
    return result

def get_members(db: Session, org_id: UUID, params: SpaceGroupMemberRequest) -> SpaceGroupMemberResponse:
    filters = build_filters(org_id, params)
    
    # total count query with joins
    total = (
        db.query(func.count('*'))
        .select_from(SpaceGroupMember)
        .join(Space, Space.id == SpaceGroupMember.space_id)
        .join(SpaceGroup, SpaceGroup.id == SpaceGroupMember.group_id)
        .join(Site, Site.id == Space.site_id)
        .filter(*filters)
        .scalar()
    )

    query = (
        db.query(
            SpaceGroupMember,
            Space,
            SpaceGroup,
            Site.id.label("site_id"),
            Site.name.label("site_name"),
        )
        .select_from(SpaceGroupMember)
        .join(Space, Space.id == SpaceGroupMember.space_id)
        .join(SpaceGroup, SpaceGroup.id == SpaceGroupMember.group_id)
        .join(Site, Site.id == Space.site_id)
        .filter(*filters)
        .offset(params.skip)
        .limit(params.limit)
    )

    results = []
    for member, space, group, site_id, site_name in query.all():
        results.append(
            SpaceGroupMemberOut(
                id=f"{member.group_id}_{member.space_id}",  # synthetic ID since composite PK
                group_id=member.group_id,
                space_id=member.space_id,
                site_id=site_id,
                site_name=site_name,
                assigned_date=member.assigned_date,
                assigned_by=member.assigned_by,
                space=SpaceOut.model_validate(space),
                group=SpaceGroupOut.model_validate(group),
            )
        )

    return {"assignments": results, "total": total}

def get_space_group_member_by_id(db: Session, group_id: str, space_id: str) -> Optional[SpaceGroupMember]:
    return db.query(SpaceGroupMember).filter(
        SpaceGroupMember.group_id == group_id,
        SpaceGroupMember.space_id == space_id
    ).first()

def add_member(db: Session, data: SpaceGroupMemberCreate) -> SpaceGroupMemberBase:
    # check if already exists
    existing = db.query(SpaceGroupMember).filter_by(
        group_id=data.group_id, space_id=data.space_id
    ).first()

    if existing:
        raise ValueError("Member already exists")

    member = SpaceGroupMember(
        group_id=data.group_id,
        space_id=data.space_id,
        assigned_by=data.assigned_by or "system",
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return SpaceGroupMemberBase.model_validate(member)


def update_member(db: Session, data: SpaceGroupMemberUpdate) -> SpaceGroupMemberBase:
    member = db.query(SpaceGroupMember).filter_by(
        group_id=data.group_id, space_id=data.space_id
    ).first()

    if not member:
        raise ValueError("Member not found")

    if data.assigned_by is not None:
        member.assigned_by = data.assigned_by

    db.commit()
    db.refresh(member)

    return SpaceGroupMemberBase.model_validate(member)


def delete_member(db: Session, group_id: UUID, space_id: UUID) -> bool:
    member = db.query(SpaceGroupMember).filter_by(
        group_id=group_id, space_id=space_id
    ).first()

    if not member:
        return False

    db.delete(member)
    db.commit()
    return True
