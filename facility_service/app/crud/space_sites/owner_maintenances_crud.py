from sqlite3 import IntegrityError
from typing import List, Optional
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session ,joinedload
from sqlalchemy import and_, func, cast, or_, case
from sqlalchemy.dialects.postgresql import UUID

from facility_service.app.models.space_sites.space_owners import SpaceOwner
from shared.helpers.json_response_helper import error_response
from shared.utils.app_status_code import AppStatusCode
from ...models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from shared.core.schemas import UserToken
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...schemas.space_sites.owner_maintenances_schemas import  OwnerMaintenanceCreate, OwnerMaintenanceListResponse, OwnerMaintenanceOut, OwnerMaintenanceRequest, OwnerMaintenanceUpdate



def build_owner_maintenance_filters(org_id: UUID, params: OwnerMaintenanceRequest):
    """Build filters for owner maintenance queries"""
    filters = [
        OwnerMaintenanceCharge.is_deleted == False
    ]
    
    # Filter by site_id
    if params.site_id and params.site_id.lower() != "all":
        filters.append(Space.site_id == UUID(params.site_id))
    
    # Filter by status
    if params.status and params.status.lower() != "all":
        filters.append(OwnerMaintenanceCharge.status == params.status)
    
    # Search filter
    if params.search:
        search_term = f"%{params.search}%"
        filters.append(or_(
            OwnerMaintenanceCharge.maintenance_no.ilike(search_term)
        ))
    
    return filters


def get_owner_maintenance_query(db: Session, org_id: UUID, params: OwnerMaintenanceRequest):
    """Base query WITHOUT joins - use filters differently"""
    filters = build_owner_maintenance_filters(org_id, params)
    
    # Don't join in base query
    query = db.query(OwnerMaintenanceCharge).filter(*filters)
    
    return query


def get_owner_maintenance_by_id(db: Session, maintenance_id: str) -> Optional[OwnerMaintenanceOut]:
    """Get single maintenance record by ID"""
    maintenance = (
        db.query(OwnerMaintenanceCharge)
        .join(Space, OwnerMaintenanceCharge.space_id == Space.id)
        .join(Site, Space.site_id == Site.id)
        .outerjoin(SpaceOwner, OwnerMaintenanceCharge.space_owner_id == SpaceOwner.id)
        .filter(
            OwnerMaintenanceCharge.id == maintenance_id,
            OwnerMaintenanceCharge.is_deleted == False
        )
        .options(
            joinedload(OwnerMaintenanceCharge.space).joinedload(Space.site),
            joinedload(OwnerMaintenanceCharge.space_owner)
        )
        .first()
    )
    
    if not maintenance:
        return None
    
    # Get related data
    space_name = maintenance.space.name if maintenance.space else None
    site_name = maintenance.space.site.name if maintenance.space and maintenance.space.site else None
    owner_name = None
    
    # Try to get owner name from space_owner relationship
    if maintenance.space_owner and maintenance.space_owner.owner_org:
        owner_name = maintenance.space_owner.owner_org.name
    elif maintenance.space_owner and maintenance.space_owner.owner_user_id:
        # You might need to fetch user name from auth_db here
        owner_name = "User Owner"  # Placeholder
    
    data = {
        **maintenance.__dict__,
        "space_name": space_name,
        "site_name": site_name,
        "owner_name": owner_name
    }
    
    maintenance_out = OwnerMaintenanceOut.model_validate(data)
    return {"maintenance": maintenance_out}



def get_owner_maintenances(
    db: Session, 
    auth_db: Session,
    user: UserToken, 
    params: OwnerMaintenanceRequest
) -> OwnerMaintenanceListResponse:
    """Get paginated list of owner maintenance records"""
    
    base_query = get_owner_maintenance_query(db, user.org_id, params)
    
    # Add organization filter differently
    base_query = base_query.filter(
        OwnerMaintenanceCharge.space_id.in_(
            db.query(Space.id)
            .join(Site, Space.site_id == Site.id)
            .filter(
                Space.org_id == user.org_id,
                Site.org_id == user.org_id
            )
        )
    )
    
    # Use joinedload for relationships
    query = (
        base_query
        .options(
            joinedload(OwnerMaintenanceCharge.space).joinedload(Space.site),
            joinedload(OwnerMaintenanceCharge.space_owner)
        )
    )
    
    # Get total count
    total = db.query(func.count()).select_from(base_query.subquery()).scalar()
    
    # Get paginated results
    results = (
        query
        .order_by( 
            OwnerMaintenanceCharge.created_at.desc()
        )
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )
    
    # Transform results
    maintenances = []
    for maintenance in results:
        space_name = maintenance.space.name if maintenance.space else None
        site_name = maintenance.space.site.name if maintenance.space and maintenance.space.site else None
        #owner_name = maintenance.space_owner.owner_name if maintenance.space_owner else None
        
        data = {
            **maintenance.__dict__,
            "space_name": space_name,
            "site_name": site_name,
            "owner_name": None
        }
        maintenances.append(OwnerMaintenanceOut.model_validate(data))
    
    return OwnerMaintenanceListResponse(
        maintenances=maintenances,
        total=total or 0
    )
    
    
def create_owner_maintenance(db: Session, maintenance: OwnerMaintenanceCreate, user: UserToken):
    """Create a new owner maintenance record"""
    
    # Check if space exists and belongs to user's organization
    space = db.query(Space).filter(
        Space.id == maintenance.space_id,
        Space.org_id == user.org_id,
        Space.is_deleted == False
    ).first()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    
    # Check if space owner exists
    space_owner = db.query(SpaceOwner).filter(
        SpaceOwner.id == maintenance.space_owner_id,
        SpaceOwner.is_active == True
    ).first()
    
    if not space_owner:
        raise HTTPException(status_code=404, detail="Space owner not found or is not active")
        
    # Check for duplicate maintenance period for the same space owner
    existing_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.space_owner_id == maintenance.space_owner_id,
        OwnerMaintenanceCharge.period_start == maintenance.period_start,
        OwnerMaintenanceCharge.is_deleted == False
    ).first()
    
    if existing_maintenance:
        raise HTTPException(
            status_code=400,
            detail=f"Maintenance already exists for this owner for period starting {maintenance.period_start}"
        )
    
    # Validate period dates
    if maintenance.period_start >= maintenance.period_end:
        raise HTTPException(
            status_code=400,
            detail="Period start date must be before period end date"
        )
    
    # Validate amount
    if maintenance.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than 0"
        )
    
    # Create maintenance record
    maintenance_data = maintenance.model_dump()
    db_maintenance = OwnerMaintenanceCharge(**maintenance_data)
    
    try:
        db.add(db_maintenance)
        db.commit()
        db.refresh(db_maintenance)
        
        # Get the created maintenance with relationships
        created_maintenance = get_owner_maintenance_by_id(db, str(db_maintenance.id))
        return created_maintenance
        
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error creating maintenance record",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def update_owner_maintenance(db: Session, maintenance: OwnerMaintenanceUpdate):
    """Update an existing owner maintenance record"""
    
    # Get existing maintenance
    db_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.id == maintenance.id,
        OwnerMaintenanceCharge.is_deleted == False
    ).first()
    
    if not db_maintenance:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    # Check if maintenance is already invoiced or paid
    if db_maintenance.status in ["invoiced", "paid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update maintenance record with status '{db_maintenance.status}'"
        )
    
    # Get update data
    update_data = maintenance.model_dump(exclude_unset=True, exclude={"maintenance_no"})
    
    # Validate period dates if being updated
    if "period_start" in update_data or "period_end" in update_data:
        period_start = update_data.get("period_start", db_maintenance.period_start)
        period_end = update_data.get("period_end", db_maintenance.period_end)
        
        if period_start >= period_end:
            raise HTTPException(
                status_code=400,
                detail="Period start date must be before period end date"
            )
    
    # Validate amount if being updated
    if "amount" in update_data and update_data["amount"] <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than 0"
        )
    
    # Check for duplicate maintenance period if changing owner or period
    space_owner_id = update_data.get("space_owner_id", db_maintenance.space_owner_id)
    period_start = update_data.get("period_start", db_maintenance.period_start)
    
    if space_owner_id != db_maintenance.space_owner_id or period_start != db_maintenance.period_start:
        existing_maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.space_owner_id == space_owner_id,
            OwnerMaintenanceCharge.period_start == period_start,
            OwnerMaintenanceCharge.id != maintenance.id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()
        
        if existing_maintenance:
            raise HTTPException(
                status_code=400,
                detail=f"Maintenance already exists for this owner for period starting {period_start}"
            )
    
    # Check if space owner exists if changing owner
    if "space_owner_id" in update_data:
        space_owner = db.query(SpaceOwner).filter(
            SpaceOwner.id == update_data["space_owner_id"],
            SpaceOwner.is_active == True
        ).first()
        
        if not space_owner:
            raise HTTPException(status_code=404, detail="Space owner not found or is not active")
    
    # Update maintenance record
    for key, value in update_data.items():
        setattr(db_maintenance, key, value)
    
    try:
        db.commit()
        db.refresh(db_maintenance)
        
        # Get the updated maintenance with relationships
        updated_maintenance = get_owner_maintenance_by_id(db, str(db_maintenance.id))
        return updated_maintenance
        
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating maintenance record",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


def delete_owner_maintenance(db: Session, maintenance_id: str):
    """Soft delete an owner maintenance record"""
    
    # Get existing maintenance
    db_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.id == maintenance_id,
        OwnerMaintenanceCharge.is_deleted == False
    ).first()
    
    if not db_maintenance:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    
    # Check if maintenance is already invoiced or paid
    if db_maintenance.status in ["invoiced", "paid"]:
        return error_response(
            message=f"Cannot delete maintenance record with status '{db_maintenance.status}'",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )
    
    # Soft delete - set is_deleted to True
    db_maintenance.is_deleted = True
    db_maintenance.updated_at = func.now()
    
    try:
        db.commit()
        db.refresh(db_maintenance)
        
        # Get the deleted maintenance with relationships
        deleted_maintenance = get_owner_maintenance_by_id(db, str(db_maintenance.id))
        return deleted_maintenance
        
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error deleting maintenance record",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )
