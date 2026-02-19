import calendar
from decimal import Decimal
from sqlite3 import IntegrityError
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, exists, func, cast, literal, or_, case
from sqlalchemy.dialects.postgresql import UUID

from facility_service.app.enum.space_sites_enum import OwnerMaintenanceStatus
from facility_service.app.models.financials.tax_codes import TaxCode
from facility_service.app.models.space_sites.buildings import Building
from facility_service.app.models.space_sites.maintenance_templates import MaintenanceTemplate
from facility_service.app.models.space_sites.space_owners import SpaceOwner
from shared.helpers.json_response_helper import error_response
from shared.models.users import Users
from shared.utils.app_status_code import AppStatusCode
from shared.utils.enums import OwnershipStatus
from ...models.space_sites.owner_maintenances import OwnerMaintenanceCharge
from shared.core.schemas import Lookup, UserToken
from ...models.space_sites.sites import Site
from ...models.space_sites.spaces import Space
from ...schemas.space_sites.owner_maintenances_schemas import OwnerMaintenanceBySpaceRequest, OwnerMaintenanceBySpaceResponse, OwnerMaintenanceCreate, OwnerMaintenanceListResponse, OwnerMaintenanceOut, OwnerMaintenanceRequest, OwnerMaintenanceUpdate
import uuid


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
            OwnerMaintenanceCharge.maintenance_no.ilike(search_term),
            Space.name.ilike(search_term)
        ))

    return filters


def get_owner_maintenance_query(db: Session, org_id: UUID, params: OwnerMaintenanceRequest):
    """Base query WITHOUT joins - use filters differently"""
    filters = build_owner_maintenance_filters(org_id, params)

    # Don't join in base query
    query = db.query(OwnerMaintenanceCharge).filter(*filters)

    return query


def get_owner_maintenance_by_id(db: Session, auth_db: Session, maintenance_id: str) -> Optional[OwnerMaintenanceOut]:
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

    # Get owner name based on owner type - FIXED INDENTATION
    owner_name = None
    owner_user_id = None
    if maintenance.space_owner:
        if maintenance.space_owner.owner_user_id:
            owner_user_id = maintenance.space_owner.owner_user_id
            # Fix indentation - this should be inside the if block
            user_record = auth_db.query(Users).filter(
                Users.id == maintenance.space_owner.owner_user_id,
                Users.is_deleted == False
            ).first()
            owner_name = f"{user_record.full_name}" if user_record else None
        elif maintenance.space_owner.owner_org:
            owner_name = maintenance.space_owner.owner_org.name

    # Get building name if building exists
    building_name = None
    if maintenance.space and maintenance.space.building:
        building_name = maintenance.space.building.name

    # Create data dict with ALL fields
    data = {
        **maintenance.__dict__,
        "space_name": space_name,
        "site_name": site_name,
        "owner_name": owner_name,
        "building_name": building_name,
        "owner_user_id": owner_user_id,
        "invoice_id": maintenance.invoice_id,
        "space_owner_id": maintenance.space_owner_id  # Make sure this is included
    }

    # Use model_validate with error handling
    try:
        maintenance_out = OwnerMaintenanceOut.model_validate(data)
        return maintenance_out  # Return just the model, not wrapped
    except Exception as e:
        # Log the validation error for debugging
        print(f"Validation error: {e}")
        print(f"Data being validated: {data}")
        # Use from_attributes as fallback
        return OwnerMaintenanceOut.model_validate(data, from_attributes=True)


def get_owner_maintenances(
    db: Session,
    auth_db: Session,
    user: UserToken,
    params: OwnerMaintenanceRequest
) -> OwnerMaintenanceListResponse:
    """Get paginated list of owner maintenance records"""

    # Build filters
    filters = build_owner_maintenance_filters(user.org_id, params)

    # Add organization and active owner filters
    filters.extend([
        Space.org_id == user.org_id,
        Site.org_id == user.org_id,
        # SpaceOwner.is_active == True,
        Space.is_deleted == False
    ])

    # Base query
    base_query = (
        db.query(OwnerMaintenanceCharge)
        .join(Space, OwnerMaintenanceCharge.space_id == Space.id)
        .join(Site, Space.site_id == Site.id)
        .join(SpaceOwner, OwnerMaintenanceCharge.space_owner_id == SpaceOwner.id)
        .filter(*filters)
    )

    # Get total count
    total = base_query.count()

    # Get paginated results
    results = (
        base_query
        .options(
            joinedload(OwnerMaintenanceCharge.space).joinedload(Space.site),
            joinedload(OwnerMaintenanceCharge.space_owner)
        )
        .order_by(OwnerMaintenanceCharge.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Transform results
    maintenances = []
    for maintenance in results:
        space_name = maintenance.space.name if maintenance.space else None
        site_name = maintenance.space.site.name if maintenance.space and maintenance.space.site else None

        # Get owner name - FIXED INDENTATION
        owner_name = None
        owner_user_id = None
        if maintenance.space_owner:
            if maintenance.space_owner.owner_user_id:
                owner_user_id = maintenance.space_owner.owner_user_id
                user_record = auth_db.query(Users).filter(
                    Users.id == maintenance.space_owner.owner_user_id,
                    Users.is_deleted == False
                ).first()
                owner_name = f"{user_record.full_name}" if user_record else None

        # Get building name
        building_name = None
        if maintenance.space and maintenance.space.building:
            building_name = maintenance.space.building.name

        # Include ALL required fields
        data = {
            **maintenance.__dict__,
            "space_name": space_name,
            "site_name": site_name,
            "owner_name": owner_name,
            "building_name": building_name,
            "owner_user_id": owner_user_id,
            "invoice_id": maintenance.invoice_id,
            "space_owner_id": maintenance.space_owner_id  # Make sure this is included
        }

        # Validate
        try:
            maintenance_out = OwnerMaintenanceOut.model_validate(data)
            maintenances.append(maintenance_out)
        except Exception as e:
            # Fallback to from_attributes
            print(f"Validation error for maintenance {maintenance.id}: {e}")
            maintenance_out = OwnerMaintenanceOut.model_validate(
                data, from_attributes=True)
            maintenances.append(maintenance_out)

    return OwnerMaintenanceListResponse(
        maintenances=maintenances,
        total=total or 0
    )


def create_owner_maintenance(db: Session, auth_db: Session, maintenance: OwnerMaintenanceCreate, user: UserToken):
    """Create a new owner maintenance record"""

    # Check if space exists and belongs to user's organization
    space = db.query(Space).filter(
        Space.id == maintenance.space_id,
        Space.org_id == user.org_id,
        Space.is_deleted == False
    ).first()

    if not space:
        return error_response(status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR), message="Space not found")

    # Find the active space owner for this space
    space_owner = db.query(SpaceOwner).filter(
        SpaceOwner.space_id == maintenance.space_id,
        SpaceOwner.is_active == True
    ).first()

    if not space_owner:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="No active owner found for this space. Please assign an owner first."
        )

    # Check for duplicate maintenance period for the same space owner
    existing_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.space_owner_id == space_owner.id,
        OwnerMaintenanceCharge.space_id == maintenance.space_id,
        OwnerMaintenanceCharge.is_deleted == False,

        # Overlapping logic
        OwnerMaintenanceCharge.period_start <= maintenance.period_end,
        OwnerMaintenanceCharge.period_end >= maintenance.period_start
    ).first()

    if existing_maintenance:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message=f"Maintenance already exists for this space owner for period starting {maintenance.period_start}"
        )

    # Validate period dates
    if maintenance.period_start >= maintenance.period_end:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Period start date must be before period end date"
        )

    # Validate amount
    # ✅ CALCULATE AMOUNT USING HELPER
    template = space.maintenance_template_id

    if not template:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Space does not have a maintenance template assigned"
        )

    # fetch template object
    maintenance_template = db.query(MaintenanceTemplate).get(template)

    amount = calculate_maintenance_amount(
        db=db,
        space=space,
        template=maintenance_template,
        start_date=maintenance.period_start,
        end_date=maintenance.period_end
    )

    if amount <= 0:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Maintenance amount could not be calculated"
        )

    # Create maintenance record with space_owner_id
    maintenance_data = maintenance.model_dump(exclude={"amount"})
    maintenance_data["org_id"] = space.org_id
    maintenance_data["space_owner_id"] = space_owner.id
    maintenance_data["amount"] = amount
    maintenance_data["tax_amount"] = amount.get("tax_amount")
    maintenance_data["total_amount"] = amount.get("total_amount")

    db_maintenance = OwnerMaintenanceCharge(**maintenance_data)

    try:
        db.add(db_maintenance)
        db.commit()
        db.refresh(db_maintenance)

        # Get the created maintenance
        created_maintenance = get_owner_maintenance_by_id(
            db, auth_db, str(db_maintenance.id))
        if not created_maintenance:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created maintenance")

        # Wrap in dictionary for OwnerMaintenanceDetailResponse
        return {"maintenance": created_maintenance}  # Wrap here

    except IntegrityError as e:
        db.rollback()
        return error_response(
            status_code=str(AppStatusCode.OPERATION_FAILED),
            message="Error creating maintenance record"
        )


def update_owner_maintenance(db: Session, auth_db: Session, maintenance: OwnerMaintenanceUpdate, user: UserToken):
    """Update an existing owner maintenance record"""

    # Get existing maintenance
    db_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.id == maintenance.id,
        OwnerMaintenanceCharge.is_deleted == False
    ).first()

    if not db_maintenance:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Maintenance record not found"
        )

    # Check if maintenance is already invoiced or paid
    if db_maintenance.status in ["invoiced", "paid"]:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message=f"Cannot update maintenance record with status '{db_maintenance.status}'"
        )

    # Get update data
    update_data = maintenance.model_dump(
        exclude_unset=True, exclude={"maintenance_no"})

    # Validate period dates if being updated
    if "period_start" in update_data or "period_end" in update_data:
        period_start = update_data.get(
            "period_start", db_maintenance.period_start)
        period_end = update_data.get("period_end", db_maintenance.period_end)

        if period_start >= period_end:
            return error_response(
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                message="Period start date must be before period end date"
            )

    # If space_id is being updated, find the new space owner
    new_space_owner_id = None
    if "space_id" in update_data:
        # Find active owner for the new space
        new_space_owner = db.query(SpaceOwner).filter(
            SpaceOwner.space_id == update_data["space_id"],
            SpaceOwner.is_active == True
        ).first()

        if not new_space_owner:
            return error_response(
                status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
                message="No active owner found for the new space"
            )

        new_space_owner_id = new_space_owner.id
        update_data["space_owner_id"] = new_space_owner_id

    # 🔹 Recalculate amount if user provides `amount` or space_id changed
    if "amount" in update_data or new_space_owner_id:
        # Determine which space to use for calculation
        space_id = update_data.get("space_id", db_maintenance.space_id)

        # Calculate the amount using your helper
        template = new_space_owner.space.maintenance_template_id

        if not template:
            raise error_response(
                message="Space does not have a maintenance template assigned"
            )

        # fetch template object
        maintenance_template = db.query(MaintenanceTemplate).get(template)

        amount = calculate_maintenance_amount(
            db=db,
            space=new_space_owner.space,
            template=maintenance_template,
            start_date=maintenance.period_start,
            end_date=maintenance.period_end
        )

        if amount and amount.get("base_amount") <= 0:
            raise HTTPException(
                status_code=400,
                detail="Maintenance amount could not be calculated"
            )

        # Replace existing value with recalculated amount
        update_data["amount"] = amount.get("base_amount")
        update_data["tax_amount"] = amount.get("tax_amount")
        update_data["total_amount"] = amount.get("total_amount")

    # Check for duplicate maintenance period if space owner or period is changing
    space_owner_id = new_space_owner_id if new_space_owner_id else db_maintenance.space_owner_id
    period_start = update_data.get("period_start", db_maintenance.period_start)

    # Check if either space_owner_id OR period_start is changing
    if (space_owner_id != db_maintenance.space_owner_id or
            period_start != db_maintenance.period_start):

        existing_maintenance = db.query(OwnerMaintenanceCharge).filter(
            OwnerMaintenanceCharge.space_owner_id == space_owner_id,
            OwnerMaintenanceCharge.period_start == period_start,
            OwnerMaintenanceCharge.id != maintenance.id,
            OwnerMaintenanceCharge.is_deleted == False
        ).first()

        if existing_maintenance:
            raise HTTPException(
                status_code=400,
                detail=f"Maintenance already exists for this space owner for period starting {period_start}"
            )

    # Update maintenance record
    for key, value in update_data.items():
        setattr(db_maintenance, key, value)

    try:
        db.commit()
        db.refresh(db_maintenance)

        # Get the updated maintenance with relationships
        updated_maintenance = get_owner_maintenance_by_id(
            db, auth_db, str(db_maintenance.id))
        return {"maintenance": updated_maintenance}  # Wrap in dictionary

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error updating maintenance record"
        )


def delete_owner_maintenance(db: Session, maintenance_id: str):
    """Soft delete an owner maintenance record"""

    # Get existing maintenance
    db_maintenance = db.query(OwnerMaintenanceCharge).filter(
        OwnerMaintenanceCharge.id == maintenance_id,
        OwnerMaintenanceCharge.is_deleted == False
    ).first()

    if not db_maintenance:
        raise HTTPException(
            status_code=404, detail="Maintenance record not found")

    # Check if maintenance is already invoiced or paid
    if db_maintenance.status in ["invoiced", "paid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete maintenance record with status '{db_maintenance.status}'"
        )

    # Soft delete - set is_deleted to True
    db_maintenance.is_deleted = True
    db_maintenance.updated_at = func.now()

    try:
        db.commit()
        db.refresh(db_maintenance)

        # Wrap in dictionary for OwnerMaintenanceDetailResponse
        return {"maintenance": db_maintenance}

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Error deleting maintenance record")


def owner_maintenances_status_lookup(db: Session, org_id: str) -> List[Dict]:
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in OwnerMaintenanceStatus
    ]


def get_spaces_with_owner_lookup(
    db: Session,
    auth_db: Session,
    site_id: str,
    building_id: Optional[str],
    org_id: str
):
    try:
        # Step 1: Get all spaces with active owners
        space_query = (
            db.query(
                Space.id,
                Space.name,
                SpaceOwner.owner_user_id
            )
            .join(Site, Space.site_id == Site.id)
            .join(Building, Space.building_block_id == Building.id)
            .join(
                SpaceOwner,
                and_(
                    SpaceOwner.space_id == Space.id,
                    SpaceOwner.is_active == True
                )
            )
            .filter(
                Site.is_deleted == False,
                Site.status == "active",
                Space.org_id == org_id,
                Space.is_deleted == False,
                SpaceOwner.status == OwnershipStatus.approved
            )
            .order_by(Space.name.asc())
        )

        if site_id and site_id.lower() != "all":
            space_query = space_query.filter(Space.site_id == site_id)

        if building_id and building_id.lower() != "all":
            space_query = space_query.filter(
                Space.building_block_id == building_id)

        spaces = space_query.all()

        # Step 2: Collect all user IDs
        user_ids = []
        for space in spaces:
            if space.owner_user_id:
                user_ids.append(space.owner_user_id)

        # Step 3: Fetch user names from auth_db
        user_names = {}
        if user_ids:
            # Fetch from auth_db
            users = auth_db.query(
                Users.id,
                Users.full_name
            ).filter(
                Users.id.in_(user_ids)
            ).all()

            user_names = {user.id: user.full_name for user in users}

        # Step 4: Build final results
        results = []
        for space in spaces:
            # Debug log
            print(
                f"Processing space: {space.name}, owner_user_id: {space.owner_user_id}")
            print(space)
            # Get user name
            owner_name = user_names.get(space.owner_user_id)

            # Build the display name
            display_name = f"{space.name} - {owner_name}"

            results.append({
                "id": space.id,
                "name": display_name
            })

        return results

    except Exception as e:
        return []


def get_owner_maintenances_by_space(
    db: Session,
    auth_db: Session,
    params: OwnerMaintenanceBySpaceRequest,
    user: UserToken
) -> OwnerMaintenanceBySpaceResponse:
    """Get all owner maintenance records for a specific space"""

    try:
        # Verify the space exists and belongs to user's organization
        space = db.query(Space).filter(
            Space.id == params.space_id,
            Space.org_id == user.org_id,
            Space.is_deleted == False
        ).options(
            joinedload(Space.site),
            joinedload(Space.building)
        ).first()

        if not space:
            raise HTTPException(
                status_code=404, detail="Space not found or you don't have access")

        # Build filters
        filters = [
            OwnerMaintenanceCharge.space_id == params.space_id,
            OwnerMaintenanceCharge.is_deleted == False
        ]

        # Add status filter if provided
        if params.status and params.status.lower() != "all":
            filters.append(OwnerMaintenanceCharge.status == params.status)

        # Add search filter if provided
        if params.search:
            search_term = f"%{params.search}%"
            filters.append(or_(
                OwnerMaintenanceCharge.maintenance_no.ilike(search_term)
            ))

        # Base query
        base_query = (
            db.query(OwnerMaintenanceCharge)
            .join(Space, OwnerMaintenanceCharge.space_id == Space.id)
            .join(Site, Space.site_id == Site.id)
            .outerjoin(SpaceOwner, OwnerMaintenanceCharge.space_owner_id == SpaceOwner.id)
            .filter(*filters)
        )

        # Get total count
        total = db.query(func.count()).select_from(
            base_query.subquery()).scalar()

        # Get paginated results
        results = (
            base_query
            .options(
                joinedload(OwnerMaintenanceCharge.space).joinedload(
                    Space.site),
                joinedload(OwnerMaintenanceCharge.space_owner)
            )
            .order_by(OwnerMaintenanceCharge.created_at.desc())
            .offset(params.skip)
            .limit(params.limit)
            .all()
        )

        # Transform results
        maintenances = []
        for maintenance in results:
            space_name = maintenance.space.name if maintenance.space else None
            site_name = maintenance.space.site.name if maintenance.space and maintenance.space.site else None

            # Get owner name based on owner type
            owner_name = None
            owner_user_id = None
            if maintenance.space_owner:
                if maintenance.space_owner.owner_user_id:
                    owner_user_id = maintenance.space_owner.owner_user_id
                    user_record = auth_db.query(Users).filter(
                        Users.id == maintenance.space_owner.owner_user_id,
                        Users.is_deleted == False
                    ).first()
                    owner_name = f"{user_record.full_name}" if user_record else None
                elif maintenance.space_owner.owner_org:
                    owner_name = maintenance.space_owner.owner_org.name

            # Get building name if building exists
            building_name = None
            if maintenance.space and maintenance.space.building:
                building_name = maintenance.space.building.name

            # Create data dict with ALL fields
            data = {
                **maintenance.__dict__,
                "space_name": space_name,
                "site_name": site_name,
                "owner_name": owner_name,
                "building_name": building_name,
                "owner_user_id": owner_user_id,
                "invoice_id": maintenance.invoice_id,
                "space_owner_id": maintenance.space_owner_id
            }

            # Use model_validate with error handling
            try:
                maintenance_out = OwnerMaintenanceOut.model_validate(data)
                maintenances.append(maintenance_out)
            except Exception:
                # Use from_attributes as fallback
                maintenance_out = OwnerMaintenanceOut.model_validate(
                    data, from_attributes=True)
                maintenances.append(maintenance_out)

        # SIMPLE: Just use params.space_id - Pydantic will handle UUID conversion
        return OwnerMaintenanceBySpaceResponse(
            space_id=params.space_id,  # Pydantic converts string to UUID
            space_name=space.name,
            site_name=space.site.name if space.site else None,
            total_records=total or 0,
            maintenances=maintenances
        )

    except Exception as e:
        print(f"Error in get_owner_maintenances_by_space: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


def auto_generate_owner_maintenance(db: Session, input_date: date):

    period_start, period_end = get_month_period(input_date)

    owners = (
        db.query(SpaceOwner)
        .join(Space, Space.id == SpaceOwner.space_id)
        .filter(
            SpaceOwner.status == OwnershipStatus.approved,
            SpaceOwner.start_date <= period_end,
            (SpaceOwner.end_date == None) | (
                SpaceOwner.end_date >= period_start),
            SpaceOwner.is_active == True,
        )
        .all()
    )

    created_count = 0   # ⭐ track new records

    for owner in owners:
        actual_start = max(owner.start_date, period_start)
        actual_end = period_end

        if owner.end_date:
            actual_end = min(owner.end_date, period_end)

        if actual_start > actual_end:
            continue

        # ⭐ NOW check duplicate
        exists = (
            db.query(OwnerMaintenanceCharge.id)
            .filter(
                OwnerMaintenanceCharge.space_owner_id == owner.id,
                OwnerMaintenanceCharge.period_start == actual_start,
                OwnerMaintenanceCharge.is_deleted == False
            )
            .first()
        )

        if exists:
            continue

        space = owner.space
        template = space.maintenance_template_id

        if not template:
            continue

        maintenance_template = db.query(MaintenanceTemplate).get(template)

        if not maintenance_template:
            continue

        # calculate amount
        amount = calculate_maintenance_amount(
            db=db,
            space=owner.space,
            template=maintenance_template,
            start_date=actual_start,
            end_date=actual_end
        )

        maintenance = OwnerMaintenanceCharge(
            org_id=space.org_id,
            space_owner_id=owner.id,
            space_id=space.id,
            period_start=actual_start,
            period_end=actual_end,
            amount=round(amount.get("base_amount"), 2),
            tax_amount=round(amount.get("tax_amount"), 2),
            total_amount=round(amount.get("total_amount"), 2),
            due_date=period_end
        )

        db.add(maintenance)
        created_count += 1   # ⭐ increment

    # ⭐ If no new records created → raise error
    if created_count == 0:
        return error_response(
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            message="Maintenance charges already generated for this period."
        )

    db.commit()

    return {"created": created_count}


def get_month_period(input_date: date):
    start = date(input_date.year, input_date.month, 1)
    last_day = calendar.monthrange(input_date.year, input_date.month)[1]
    end = date(input_date.year, input_date.month, last_day)
    return start, end


def get_calculated_maintenance_amount(
    db: Session,
    space_id: UUID,
    start_date: date,
    end_date: date
) -> Decimal:
    # Fetch space and template
    space = db.query(Space).filter(
        Space.id == space_id,
        Space.is_deleted == False
    ).first()

    if not space:
        raise error_response(message="Space not found")

    template = space.maintenance_template_id

    if not template:
        raise error_response(
            message="Maintenance template not found for this space")

    maintenance_template = db.query(MaintenanceTemplate).get(template)

    if not maintenance_template:
        raise error_response(message="Maintenance template not found")

    # Calculate amount
    amount = calculate_maintenance_amount(
        db=db,
        space=space,
        template=maintenance_template,
        start_date=start_date,
        end_date=end_date
    )

    return amount


def calculate_maintenance_amount(
    db: Session,
    space: Space,
    template: MaintenanceTemplate,
    start_date: date,
    end_date: date
):

    if not template:
        return {
            "base_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "total_amount": Decimal("0.00")
        }

    # -----------------------------
    # Determine billing period
    # -----------------------------

    month_start = date(start_date.year, start_date.month, 1)

    days_in_month = calendar.monthrange(
        month_start.year,
        month_start.month
    )[1]

    # -----------------------------
    # Calculate active days
    # -----------------------------

    active_days = (end_date - start_date).days + 1

    # -----------------------------
    # Calculate monthly base amount
    # -----------------------------

    base_amount = Decimal(template.amount)

    if template.calculation_type == "flat":
        monthly_amount = base_amount

    elif template.calculation_type == "per_sqft":
        monthly_amount = base_amount * Decimal(space.area_sqft or 0)

    elif template.calculation_type == "per_bed":
        monthly_amount = base_amount * Decimal(space.beds or 0)

    else:
        monthly_amount = base_amount

    # -----------------------------
    # Prorated BASE calculation
    # -----------------------------

    daily_rate = monthly_amount / Decimal(days_in_month)

    prorated_base = daily_rate * Decimal(active_days)

    prorated_base = prorated_base.quantize(Decimal("0.01"))

    # -----------------------------
    # Apply tax AFTER proration
    # -----------------------------
    tax_code = (db.query(TaxCode).filter(
        TaxCode.id == template.tax_code_id).first())

    total_amount, tax_amount = apply_tax(
        prorated_base,
        tax_code
    )

    return {
        "base_amount": prorated_base,
        "tax_amount": tax_amount,
        "total_amount": total_amount
    }


def apply_tax(amount: Decimal, tax_code: TaxCode | None) -> tuple[Decimal, Decimal]:

    if not tax_code:
        return amount, Decimal("0.00")

    tax_rate = Decimal(tax_code.rate) / Decimal("100")

    tax_amount = amount * tax_rate

    total = amount + tax_amount

    return (
        total.quantize(Decimal("0.01")),
        tax_amount.quantize(Decimal("0.01"))
    )
