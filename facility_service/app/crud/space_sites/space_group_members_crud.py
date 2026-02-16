# app/crud/space_group_members.py
import uuid
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import func, cast, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from ...schemas.space_sites.space_groups_schemas import SpaceGroupOut
from ...schemas.space_sites.spaces_schemas import SpaceOut
from ...models.space_sites.sites import Site
from ...models.space_sites.space_groups import SpaceGroup
from ...models.space_sites.spaces import Space
from ...models.space_sites.space_group_members import SpaceGroupMember
from ...schemas.space_sites.space_group_members_schemas import SpaceGroupMemberBase, SpaceGroupMemberCreate, SpaceGroupMemberOut, SpaceGroupMemberRequest, SpaceGroupMemberResponse, SpaceGroupMemberUpdate
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response


def build_filters(org_id: UUID, params: SpaceGroupMemberRequest):
    filters = []

    # org_id comes from SpaceGroup
    filters.append(Space.org_id == org_id)

    # Add soft-delete filters for all related models
    filters.append(Space.is_deleted == False)
    filters.append(Site.is_deleted == False)
    filters.append(SpaceGroup.is_deleted == False)

    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == params.site_id)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            Space.name.ilike(search_term),
            SpaceGroup.name.ilike(search_term),
            Site.name.ilike(search_term)
        ))

    return filters


def get_member_query(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    filters = build_filters(org_id, params)
    return db.query(SpaceGroupMember).filter(*filters)


def get_members_overview(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    filters = build_filters(org_id, params)

    counts = (
        db.query(
            func.count('*').label("total_assignments"),
            func.count(func.distinct(SpaceGroupMember.space_id)
                       ).label("total_spaces"),
            func.count(func.distinct(SpaceGroupMember.group_id)
                       ).label("total_groups"),
        )
        .select_from(SpaceGroupMember)
        .join(Space, Space.id == SpaceGroupMember.space_id)
        .join(SpaceGroup, SpaceGroup.id == SpaceGroupMember.group_id)
        .join(Site, Site.id == Space.site_id)
        .filter(*filters)
        .one()
    )

    # Only count non-deleted spaces for assignment rate calculation
    overall_spaces = db.query(
        func.count('*')
    ).filter(
        Space.org_id == org_id,
        Space.is_deleted == False
    ).scalar()

    assignment_rate = (counts.total_spaces /
                       overall_spaces * 100) if overall_spaces else 0
    assignment_rate = round(assignment_rate, 2)

    return {
        "totalAssignments": counts.total_assignments,
        "groupUsed": counts.total_groups,
        "spaceAssigned": counts.total_spaces,
        "assignmentRate": float(assignment_rate)
    }


def get_assignment_preview(db: Session, org_id: UUID, params: SpaceGroupMemberRequest):
    # Remove SpaceGroupMember from filters since we're previewing BEFORE creation
    filters = []

    # org_id comes from Space
    filters.append(Space.org_id == org_id)

    # Add soft-delete filters
    filters.append(Space.is_deleted == False)
    filters.append(Site.is_deleted == False)
    filters.append(SpaceGroup.is_deleted == False)

    # Add specific filters for the preview
    if params.space_id:
        filters.append(Space.id == params.space_id)
    if params.group_id:
        filters.append(SpaceGroup.id == params.group_id)

    # ✅ CHANGED: Query Space and SpaceGroup directly, not through SpaceGroupMember
    assignment_preview_query = (
        db.query(
            Site.name.label("site_name"),
            Space.name.label("space_name"),
            func.replace(SpaceGroup.kind, "_", " ").label("kind"),
            SpaceGroup.name.label("group_name"),
            SpaceGroup.specs
        )
        .select_from(Space)  # ✅ CHANGED: Start from Space table
        .join(Site, Site.id == Space.site_id)
        # ✅ CHANGED: Direct join on group_id
        .join(SpaceGroup, SpaceGroup.id == params.group_id)
        .filter(*filters)
    )

    result = assignment_preview_query.first()
    if not result:
        return error_response(
            message="Space or Group not found for preview",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )

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
        # ⬅ Order by latest updated
        .order_by(SpaceGroupMember.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
    )

    results = []
    for member, space, group, site_id, site_name in query.all():
        results.append(
            SpaceGroupMemberOut(
                # synthetic ID since composite PK
                id=f"{member.group_id}_{member.space_id}",
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
    # Check if space and group exist and are not deleted
    space = db.query(Space).filter(
        Space.id == data.space_id,
        Space.is_deleted == False
    ).first()
    if not space:
        raise ValueError("Space not found or has been deleted")

    group = db.query(SpaceGroup).filter(
        SpaceGroup.id == data.group_id,
        SpaceGroup.is_deleted == False
    ).first()
    if not group:
        raise ValueError("Space group not found or has been deleted")

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
