
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_, and_
from uuid import UUID
from datetime import date
import json
from facility_service.app.models.leasing_tenants.commercial_partners import CommercialPartner
from facility_service.app.models.leasing_tenants.tenants import Tenant
from facility_service.app.models.parking_access.parking_zones import ParkingZone
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.spaces import Space
from shared.helpers.json_response_helper import error_response

from ...enum.parking_passes_enum import ParkingPassStatus
from shared.core.schemas import Lookup

from ...models.parking_access.parking_pass import ParkingPass
from ...schemas.parking_access.parking_pass_schemas import (
    FamilyInfo,
    ParkingPassCreate,
    ParkingPassOut,
    ParkingPassUpdate,
    ParkingPassRequest,
    VehicleInfo,
)


# ---------------- FILTER BUILDER ----------------
# ---------------- FILTER BUILDER ----------------
def build_pass_filters(org_id: UUID, params: ParkingPassRequest):
    filters = [
        ParkingPass.org_id == org_id,
        ParkingPass.is_deleted == False
    ]

    if params.site_id and params.site_id != "all":
        filters.append(ParkingPass.site_id == params.site_id)

    if params.zone_id:
        filters.append(ParkingPass.zone_id == params.zone_id)
    
    if params.space_id and params.space_id != "all":
        filters.append(ParkingPass.space_id == params.space_id)

    if params.status:
        filters.append(func.lower(ParkingPass.status) == func.lower(params.status))

    if params.search:
        filters.append(or_(
            ParkingPass.vehicle_no.ilike(f"%{params.search}%"),
            ParkingPass.pass_no.ilike(f"%{params.search}%"),
            ParkingPass.pass_holder_name.ilike(f"%{params.search}%")  # Added this
        ))

    return filters

# ---------------- LIST ----------------
def get_parking_passes(db: Session, org_id: UUID, params: ParkingPassRequest):
    """
    Get all parking passes with partner information
    """
    filters = build_pass_filters(org_id, params)
    
    # Get all partner IDs from parking passes
    partner_ids_query = db.query(ParkingPass.partner_id).filter(
        *filters,
        ParkingPass.partner_id.isnot(None)
    ).distinct()
    
    partner_ids = [p.partner_id for p in partner_ids_query.all() if p.partner_id]
    
    # Pre-fetch all partner information (tenants and commercial partners)
    partners_info = {}
    if partner_ids:
        # Get tenants information
        tenants = db.query(
            Tenant.id, 
            Tenant.name, 
            Tenant.vehicle_info, 
            Tenant.family_info
        ).filter(
            Tenant.id.in_(partner_ids),
            Tenant.is_deleted == False
        ).all()
        
        # Get commercial partners information
        commercial_partners = db.query(
            CommercialPartner.id,
            CommercialPartner.legal_name,
            CommercialPartner.vehicle_info
        ).filter(
            CommercialPartner.id.in_(partner_ids),
            CommercialPartner.is_deleted == False
        ).all()
        
        # Store tenant information
        for tenant in tenants:
            partners_info[str(tenant.id)] = {
                'name': tenant.name,
                'vehicle_info': tenant.vehicle_info,
                'family_info': tenant.family_info
            }
        
        # Store commercial partner information
        for cp in commercial_partners:
            partners_info[str(cp.id)] = {
                'name': cp.legal_name or cp.name,
                'vehicle_info': cp.vehicle_info,
                'family_info': None  # Commercial partners don't have family_info
            }

    # Main query for parking passes with site/space/zone info
    base_query = (
        db.query(
            ParkingPass,
            Site.name.label('site_name'),
            Space.name.label('space_name'),
            ParkingZone.name.label('zone_name')
        )
        .outerjoin(Site, ParkingPass.site_id == Site.id)
        .outerjoin(Space, ParkingPass.space_id == Space.id)
        .outerjoin(ParkingZone, ParkingPass.zone_id == ParkingZone.id)
        .filter(*filters)
    )

    # Get total count for pagination
    total = base_query.with_entities(func.count(ParkingPass.id)).scalar()

    # Apply pagination and ordering
    results = (
        base_query
        .order_by(ParkingPass.valid_to.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Process and convert results
    passes_out = []
    for pass_obj, site_name, space_name, zone_name in results:
        # Get partner info if exists
        partner_info = partners_info.get(str(pass_obj.partner_id)) if pass_obj.partner_id else None
        
        # Parse vehicle_info from partner
        vehicle_info_list = []
        if partner_info and partner_info.get('vehicle_info'):
            try:
                # Handle both string JSON and already parsed data
                if isinstance(partner_info['vehicle_info'], str):
                    vehicles_data = json.loads(partner_info['vehicle_info'])
                else:
                    vehicles_data = partner_info['vehicle_info']
                
                # Extract vehicle information
                if isinstance(vehicles_data, list):
                    for vehicle in vehicles_data:
                        if isinstance(vehicle, dict) and vehicle.get('number'):
                            vehicle_info_list.append(VehicleInfo(
                                type=vehicle.get('type', ''),
                                number=vehicle.get('number', '')
                            ))
            except (json.JSONDecodeError, TypeError, AttributeError):
                vehicle_info_list = []  # If parsing fails, return empty list
        
        # Parse family_info from partner (only for tenants)
        family_info_list = []
        if partner_info and partner_info.get('family_info'):
            try:
                # Handle both string JSON and already parsed data
                if isinstance(partner_info['family_info'], str):
                    family_data = json.loads(partner_info['family_info'])
                else:
                    family_data = partner_info['family_info']
                
                # Extract family information
                if isinstance(family_data, list):
                    for member in family_data:
                        if isinstance(member, dict) and member.get('member'):
                            family_info_list.append(FamilyInfo(
                                member=member.get('member', ''),
                                relation=member.get('relation', '')
                            ))
            except (json.JSONDecodeError, TypeError, AttributeError):
                family_info_list = []  # If parsing fails, return empty list
        
        # Create dictionary for ParkingPassOut
        pass_dict = {
            **{k: v for k, v in pass_obj.__dict__.items() if not k.startswith('_')},
            "site_name": site_name,
            "space_name": space_name,
            "zone_name": zone_name,
            "partner_name": partner_info.get('name') if partner_info else None,
            "vehicle_info": vehicle_info_list if vehicle_info_list else None,
            "family_info": family_info_list if family_info_list else None
        }
        
        # Convert to Pydantic model
        passes_out.append(ParkingPassOut.model_validate(pass_dict))

    return {
        "passes": passes_out,
        "total": total
    }

# ---------------- GET BY ID ----------------
def get_parking_pass_by_id(db: Session, pass_id: UUID):
    return (
        db.query(ParkingPass)
        .filter(ParkingPass.id == pass_id, ParkingPass.is_deleted == False)
        .first()
    )
# ---------------- CREATE ----------------

# ---------------- CREATE ----------------
def create_parking_pass(db: Session, data: ParkingPassCreate):
    payload = data.model_dump()
    
    try:
        # Get partner_id from payload
        partner_id = payload.get("partner_id")
        if not partner_id:
            return error_response(message="partner_id is required")
        
        vehicle_no = payload.get("vehicle_no")
        if not vehicle_no:
            return error_response(message="vehicle_no is required")
        
        # ✅ SINGLE EFFICIENT CHECK: Find ANY active/blocked pass for this vehicle
        existing_pass = db.query(ParkingPass).filter(
            ParkingPass.vehicle_no == vehicle_no,
            ParkingPass.is_deleted == False,
            ParkingPass.status.in_(['active', 'blocked'])
        ).first()

        if existing_pass:
            # Get the existing partner's name for error message
            other_partner_name = None
            other_partner_id = existing_pass.partner_id
            if other_partner_id:
                # Check Tenant first
                other_partner = db.query(Tenant).filter(
                    Tenant.id == other_partner_id,
                    Tenant.is_deleted == False
                ).first()
                
                if not other_partner:
                    # Check CommercialPartner
                    other_partner = db.query(CommercialPartner).filter(
                        CommercialPartner.id == other_partner_id,
                        CommercialPartner.is_deleted == False
                    ).first()
                
                if other_partner:
                    # Get the correct name field
                    if hasattr(other_partner, 'name') and other_partner.name:
                        other_partner_name = other_partner.name
                    elif hasattr(other_partner, 'legal_name') and other_partner.legal_name:
                        other_partner_name = other_partner.legal_name
            
            # Case 1: Same partner trying to create duplicate
            if existing_pass.partner_id == partner_id:
                return error_response(
                    message=f"This partner already has an active/blocked parking pass for vehicle {vehicle_no}"
                )
            # Case 2: Different partner trying to use same vehicle
            else:
                if other_partner_name:
                    return error_response(
                        message=f"Vehicle {vehicle_no} is already assigned to {other_partner_name}. One vehicle can only have one active parking pass."
                    )
                else:
                    return error_response(
                        message=f"Vehicle {vehicle_no} is already assigned to another partner. One vehicle can only have one active parking pass."
                    )
        # ---------------------------- GET PARTNER INFO ----------------------------
        # Try to find partner in Tenant table
        partner = db.query(Tenant).filter(
            Tenant.id == partner_id,
            Tenant.is_deleted == False
        ).first()
        
        # If not found in Tenant, try CommercialPartner
        if not partner:
            partner = db.query(CommercialPartner).filter(
                CommercialPartner.id == partner_id,
                CommercialPartner.is_deleted == False
            ).first()
        
        if not partner:
            return error_response(message="Partner not found")
        
        # Get partner name (check different possible name fields)
        partner_name = None
        if hasattr(partner, 'name'):
            partner_name = partner.name
        elif hasattr(partner, 'legal_name'):
            partner_name = partner.legal_name
            
            
        # ---------------------------- SET PASS HOLDER NAME ----------------------------
        # Logic: If pass_holder_name is empty/None, use partner name, else use provided
        pass_holder_name = payload.get("pass_holder_name")
        # Check for None, empty string, or whitespace only
        if (pass_holder_name is None or str(pass_holder_name).strip() == "") and partner_name:
            payload["pass_holder_name"] = partner_name  # Use partner name
        else:
            payload["pass_holder_name"] = pass_holder_name  # Keep user-provided value
                
        # ---------------------------- FETCH VEHICLE INFO ----------------------------
        # Extract vehicle info from partner for response
        vehicles = []
        if hasattr(partner, 'vehicle_info') and partner.vehicle_info:
            # Parse vehicle_info
            vehicles_data = []
            if isinstance(partner.vehicle_info, str):
                try:
                    vehicles_data = json.loads(partner.vehicle_info)
                except:
                    vehicles_data = []
            else:
                vehicles_data = partner.vehicle_info
            
            # Extract vehicle information
            if isinstance(vehicles_data, list):
                for vehicle in vehicles_data:
                    if isinstance(vehicle, dict) and vehicle.get("number"):
                        vehicles.append(VehicleInfo(
                            type=vehicle.get("type", ""),
                            number=vehicle.get("number", "")
                        ))
        
        # ---------------------------- FETCH FAMILY INFO ----------------------------
        # Extract family info (only if partner has this field)
        family_info = []
        if hasattr(partner, 'family_info') and partner.family_info:
            family_data = []
            if isinstance(partner.family_info, str):
                try:
                    family_data = json.loads(partner.family_info)
                except:
                    family_data = []
            else:
                family_data = partner.family_info
            
            if isinstance(family_data, list):
                for member in family_data:
                    if isinstance(member, dict) and member.get("member"):
                        family_info.append(FamilyInfo(
                            member=member.get("member", ""),
                            relation=member.get("relation", "")
                        ))
        
        # ---------------------------- CREATE PASS ----------------------------
        db_pass = ParkingPass(**payload)
        db.add(db_pass)
        db.commit()
        db.refresh(db_pass)
        
        # Prepare response - include vehicle_info and family_info in ParkingPassOut
        db_pass_dict = {k: v for k, v in db_pass.__dict__.items() if not k.startswith("_")}
        pass_out = ParkingPassOut.model_validate(db_pass_dict)
        
        # Add partner info directly to ParkingPassOut
        pass_out.partner_name = partner_name
        pass_out.vehicle_info = vehicles  # Add partner's vehicles to pass_out
        pass_out.family_info = family_info if family_info else None  # Add family info if exists
        
        parking_pass=pass_out.model_dump()
        return parking_pass
        
    except Exception as e:
        db.rollback()
        return error_response(message=str(e))
    

# ---------------- UPDATE ----------------
# ---------------- UPDATE ----------------
def update_parking_pass(db: Session, data: ParkingPassUpdate):
    try:
        # Get the existing pass
        db_pass = get_parking_pass_by_id(db, data.id)
        if not db_pass:
            return error_response(message="Parking pass not found")

        update_data = data.model_dump(exclude_unset=True)
        
        # Check if vehicle_no is being updated
        vehicle_no = update_data.get("vehicle_no", db_pass.vehicle_no)
        partner_id = update_data.get("partner_id", db_pass.partner_id)
        
        # If vehicle_no is being updated, perform the same check as create
        if 'vehicle_no' in update_data or 'partner_id' in update_data:
            # ✅ SINGLE EFFICIENT CHECK: Find ANY active/blocked pass for this vehicle (excluding current pass)
            existing_pass = db.query(ParkingPass).filter(
                ParkingPass.vehicle_no == vehicle_no,
                ParkingPass.id != data.id,  # Exclude current pass
                ParkingPass.is_deleted == False,
                ParkingPass.status.in_(['active', 'blocked'])
            ).first()

            if existing_pass:
                # Get the existing partner's name for error message
                other_partner_name = None
                other_partner_id = existing_pass.partner_id
                if other_partner_id:
                    # Check Tenant first
                    other_partner = db.query(Tenant).filter(
                        Tenant.id == other_partner_id,
                        Tenant.is_deleted == False
                    ).first()
                    
                    if not other_partner:
                        # Check CommercialPartner
                        other_partner = db.query(CommercialPartner).filter(
                            CommercialPartner.id == other_partner_id,
                            CommercialPartner.is_deleted == False
                        ).first()
                    
                    if other_partner:
                        # Get the correct name field
                        if hasattr(other_partner, 'name') and other_partner.name:
                            other_partner_name = other_partner.name
                        elif hasattr(other_partner, 'legal_name') and other_partner.legal_name:
                            other_partner_name = other_partner.legal_name
                
                # Case 1: Same partner trying to update to duplicate vehicle
                if existing_pass.partner_id == partner_id:
                    return error_response(
                        message=f"This partner already has an active/blocked parking pass for vehicle {vehicle_no}"
                    )
                # Case 2: Different partner trying to use same vehicle
                else:
                    if other_partner_name:
                        return error_response(
                            message=f"Vehicle {vehicle_no} is already assigned to {other_partner_name}. One vehicle can only have one active parking pass."
                        )
                    else:
                        return error_response(
                            message=f"Vehicle {vehicle_no} is already assigned to another partner. One vehicle can only have one active parking pass."
                        )
        
        # ---------------------------- GET PARTNER INFO IF PARTNER CHANGED ----------------------------
        partner_info_needed = False
        if 'partner_id' in update_data or 'pass_holder_name' in update_data:
            partner_info_needed = True
            
        partner = None
        partner_name = None
        vehicles = []
        family_info = []
        
        if partner_info_needed:
            # Get the partner_id from update or existing pass
            current_partner_id = update_data.get("partner_id", db_pass.partner_id)
            
            if current_partner_id:
                # Try to find partner in Tenant table
                partner = db.query(Tenant).filter(
                    Tenant.id == current_partner_id,
                    Tenant.is_deleted == False
                ).first()
                
                # If not found in Tenant, try CommercialPartner
                if not partner:
                    partner = db.query(CommercialPartner).filter(
                        CommercialPartner.id == current_partner_id,
                        CommercialPartner.is_deleted == False
                    ).first()
                
                if not partner:
                    return error_response(message="Partner not found")
                
                # Get partner name
                if hasattr(partner, 'name') and partner.name:
                    partner_name = partner.name
                elif hasattr(partner, 'legal_name') and partner.legal_name:
                    partner_name = partner.legal_name
                
                # ---------------------------- UPDATE PASS HOLDER NAME ----------------------------
                # Logic: If pass_holder_name is empty/None in update, use partner name
                pass_holder_name = update_data.get("pass_holder_name")
                if pass_holder_name is not None and str(pass_holder_name).strip() == "":
                    # If empty string provided, use partner name
                    if partner_name:
                        update_data["pass_holder_name"] = partner_name
                elif pass_holder_name is None and 'pass_holder_name' not in update_data:
                    # If pass_holder_name not in update and existing is empty, use partner name
                    if (db_pass.pass_holder_name is None or str(db_pass.pass_holder_name).strip() == "") and partner_name:
                        update_data["pass_holder_name"] = partner_name
                
                # ---------------------------- FETCH VEHICLE INFO ----------------------------
                if hasattr(partner, 'vehicle_info') and partner.vehicle_info:
                    vehicles_data = []
                    if isinstance(partner.vehicle_info, str):
                        try:
                            vehicles_data = json.loads(partner.vehicle_info)
                        except:
                            vehicles_data = []
                    else:
                        vehicles_data = partner.vehicle_info
                    
                    # Extract vehicle information
                    if isinstance(vehicles_data, list):
                        for vehicle in vehicles_data:
                            if isinstance(vehicle, dict) and vehicle.get("number"):
                                vehicles.append(VehicleInfo(
                                    type=vehicle.get("type", ""),
                                    number=vehicle.get("number", "")
                                ))
                
                # ---------------------------- FETCH FAMILY INFO ----------------------------
                if hasattr(partner, 'family_info') and partner.family_info:
                    family_data = []
                    if isinstance(partner.family_info, str):
                        try:
                            family_data = json.loads(partner.family_info)
                        except:
                            family_data = []
                    else:
                        family_data = partner.family_info
                    
                    if isinstance(family_data, list):
                        for member in family_data:
                            if isinstance(member, dict) and member.get("member"):
                                family_info.append(FamilyInfo(
                                    member=member.get("member", ""),
                                    relation=member.get("relation", "")
                                ))
        
        # Update the pass with new data
        for k, v in update_data.items():
            setattr(db_pass, k, v)
        
        db.commit()
        db.refresh(db_pass)
        
        # ---------------------------- FETCH SITE, SPACE, ZONE NAMES ----------------------------
        # Query the pass again with joins to get site/space/zone names
        pass_with_details = (
            db.query(
                ParkingPass,
                Site.name.label('site_name'),
                Space.name.label('space_name'),
                ParkingZone.name.label('zone_name')
            )
            .outerjoin(Site, ParkingPass.site_id == Site.id)
            .outerjoin(Space, ParkingPass.space_id == Space.id)
            .outerjoin(ParkingZone, ParkingPass.zone_id == ParkingZone.id)
            .filter(ParkingPass.id == data.id)
            .first()
        )
        
        if pass_with_details:
            db_pass, site_name, space_name, zone_name = pass_with_details
            # Update the db_pass object with the names
            db_pass.site_name = site_name
            db_pass.space_name = space_name
            db_pass.zone_name = zone_name
        
        # Prepare response similar to create
        db_pass_dict = {k: v for k, v in db_pass.__dict__.items() if not k.startswith("_")}
        pass_out = ParkingPassOut.model_validate(db_pass_dict)
        
        # Add partner info if available
        if partner_info_needed and partner:
            pass_out.partner_name = partner_name
            pass_out.vehicle_info = vehicles if vehicles else None
            pass_out.family_info = family_info if family_info else None
        
        parking_pass=pass_out.model_dump()
        return parking_pass
        
    except Exception as e:
        db.rollback()
        return error_response(message=str(e))
# ---------------- SOFT DELETE ----------------
def delete_parking_pass(db: Session, pass_id: UUID):
    db_pass = get_parking_pass_by_id(db, pass_id)
    if not db_pass:
        return None

    db_pass.is_deleted = True
    db.commit()
    return True

def get_parking_pass_overview(db: Session, org_id):
    today = date.today()

    total_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    active_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            func.lower(ParkingPass.status) == "active",  # Case-insensitive
            ParkingPass.valid_to >= today,
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    expired_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            ParkingPass.is_deleted == False,
            ParkingPass.valid_to < today
        )
        .scalar()
    )

    blocked_passes = (
        db.query(func.count(ParkingPass.id))
        .filter(
            ParkingPass.org_id == org_id,
            func.lower(ParkingPass.status) == "blocked",  # Case-insensitive
            ParkingPass.is_deleted == False
        )
        .scalar()
    )

    return {
        "totalPasses": total_passes or 0,
        "activePasses": active_passes or 0,
        "expiredPasses": expired_passes or 0,
        "blockedPasses": blocked_passes or 0,
    }


def parkking_pass_status_lookup(db: Session, org_id: UUID):
    return [
        Lookup(id=status.value, name=status.capitalize())
        for status in ParkingPassStatus
    ]

def parking_pass_status_filter(db: Session, org_id: str):
   rows=(
       db.query(
              func.lower(ParkingPass.status).label("id"),
              func.initcap(ParkingPass.status).label("name")
              )
        .filter(ParkingPass.org_id == org_id,ParkingPass.is_deleted == False)
        .distinct()
        .order_by(func.lower(ParkingPass.status).asc())
        .all()
    )
   return [Lookup(id=row.id, name=row.name) for row in rows]
    
        
def parking_pass_zone_filter(db: Session, org_id: str): 
    rows=(
         db.query(
                  ParkingPass.zone_id.label("id"),
                  ParkingZone.name.label("name")
                )
            .join(ParkingZone, ParkingPass.zone_id == ParkingZone.id)
          .filter(ParkingPass.org_id == org_id,ParkingPass.is_deleted == False)
          .distinct()
          .order_by(ParkingPass.zone_id.asc())
          .all()
     )
    return [Lookup(id=row.id, name=row.name) for row in rows] 





# ---------------- GET PARTNER INFO ----------------
# ---------------- GET PARTNER INFO ----------------
def get_partner_vehicle_family_info(db: Session, org_id: UUID, partner_id: UUID):
    """
    Fetch vehicle info and family info for a specific partner
    """
    try:
        # Try Tenant first
        partner = db.query(Tenant).filter(
            Tenant.id == partner_id,
            Tenant.is_deleted == False
        ).first()
        
        # If not found in Tenant, try CommercialPartner
        if not partner:
            partner = db.query(CommercialPartner).filter(
                CommercialPartner.id == partner_id,
                CommercialPartner.is_deleted == False
            ).first()
        
        if not partner:
            return error_response(message="Partner not found")
        
        # Get partner name (check all possible name fields)
        partner_name = None
        if hasattr(partner, 'name'):
            partner_name = partner.name
        elif hasattr(partner, 'legal_name'):
            partner_name = partner.legal_name
        
        # Parse vehicle_info
        vehicle_info = []  # Changed variable name
        if hasattr(partner, 'vehicle_info') and partner.vehicle_info:
            vehicles_data = []
            if isinstance(partner.vehicle_info, str):
                try:
                    vehicles_data = json.loads(partner.vehicle_info)
                except:
                    vehicles_data = []
            else:
                vehicles_data = partner.vehicle_info
            
            if isinstance(vehicles_data, list):
                for vehicle in vehicles_data:
                    if isinstance(vehicle, dict) and vehicle.get("number"):
                        vehicle_info.append(VehicleInfo(  # Changed to vehicle_info
                            type=vehicle.get("type", ""),
                            number=vehicle.get("number", "")
                        ))
        
        # Parse family_info (only if the model has this field)
        family_info = []
        if hasattr(partner, 'family_info') and partner.family_info:
            family_data = []
            if isinstance(partner.family_info, str):
                try:
                    family_data = json.loads(partner.family_info)
                except:
                    family_data = []
            else:
                family_data = partner.family_info
            
            if isinstance(family_data, list):
                for member in family_data:
                    if isinstance(member, dict) and member.get("member"):
                        family_info.append(FamilyInfo(
                            member=member.get("member", ""),
                            relation=member.get("relation", "")
                        ))
        
        return {
            "partner_id": partner.id,
            "partner_name": partner_name,
            "vehicle_info": vehicle_info,  # Changed to vehicle_info
            "family_info": family_info if family_info else None
        }
            
    except Exception as e:
        return error_response(message=str(e))
    
    
    
# ---------------- GET PARTNER VEHICLES ONLY ----------------
def get_partner_vehicles(db: Session, org_id: UUID, partner_id: UUID):
    """
    Fetch ONLY vehicle information for a specific partner
    Returns list of VehicleInfo objects
    """
    try:
        # Try Tenant first
        partner = db.query(Tenant).filter(
            Tenant.id == partner_id,
            Tenant.is_deleted == False
        ).first()
        
        # If not found in Tenant, try CommercialPartner
        if not partner:
            partner = db.query(CommercialPartner).filter(
                CommercialPartner.id == partner_id,
                CommercialPartner.is_deleted == False
            ).first()
        
        if not partner:
            return error_response(message="Partner not found")
        
        # Parse vehicle_info ONLY
        vehicles = []
        if hasattr(partner, 'vehicle_info') and partner.vehicle_info:
            vehicles_data = []
            if isinstance(partner.vehicle_info, str):
                try:
                    vehicles_data = json.loads(partner.vehicle_info)
                except:
                    vehicles_data = []
            else:
                vehicles_data = partner.vehicle_info
            
            if isinstance(vehicles_data, list):
                for vehicle in vehicles_data:
                    if isinstance(vehicle, dict):
                        # Handle both key formats
                        vehicle_number = vehicle.get("number")
                        vehicle_type = vehicle.get("type")
                        
                        if vehicle_number:
                            vehicles.append(VehicleInfo(
                                type=vehicle_type or "",
                                number=vehicle_number or  ""
                            ))
        
        return vehicles  # ✅ Return list directly
            
    except Exception as e:
        return error_response(message=str(e))