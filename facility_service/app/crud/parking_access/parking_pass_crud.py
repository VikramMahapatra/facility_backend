
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
        filters.append( or_(ParkingPass.vehicle_no.ilike(f"%{params.search}%"),
                       ParkingPass.pass_no.ilike(f"%{params.search}%")))

    return filters


# ---------------- LIST ----------------
def get_parking_passes(db: Session, org_id: UUID, params: ParkingPassRequest):
    filters = build_pass_filters(org_id, params)

    # Create a subquery to get all residential tenant IDs for family_info
    residential_passes = db.query(ParkingPass).filter(
        *filters,
        ParkingPass.tenant_type == 'residential'
    ).subquery()

    # Get family_info in a separate query
    residential_ids = [p.partner_id for p in db.query(residential_passes.c.partner_id).distinct().all() if p.partner_id]
    
    tenants_family_info = {}
    if residential_ids:
        tenants = db.query(Tenant.id, Tenant.family_info).filter(
            Tenant.id.in_(residential_ids),
            Tenant.is_deleted == False
        ).all()
        
        for tenant_id, family_info in tenants:
            if family_info:
                if isinstance(family_info, str):
                    try:
                        import json
                        tenants_family_info[str(tenant_id)] = json.loads(family_info)
                    except:
                        tenants_family_info[str(tenant_id)] = []
                else:
                    tenants_family_info[str(tenant_id)] = family_info
            else:
                tenants_family_info[str(tenant_id)] = []

    # Main query with joins
    base_query = (
        db.query(
            ParkingPass,
            Site.name.label('site_name'),
            Space.name.label('space_name'),
            ParkingZone.name.label('zone_name'),
        case(
            (ParkingPass.tenant_type == 'residential', Tenant.name),
            (ParkingPass.tenant_type == 'commercial', CommercialPartner.legal_name),
            else_=None
        ).label('partner_name')

        )
        .outerjoin(Site, ParkingPass.site_id == Site.id)
        .outerjoin(Space, ParkingPass.space_id == Space.id)
        .outerjoin(ParkingZone, ParkingPass.zone_id == ParkingZone.id)
        .outerjoin(Tenant, 
            and_(
                ParkingPass.tenant_type == 'residential',
                ParkingPass.partner_id == Tenant.id,
                Tenant.is_deleted == False
            )
        )
        .outerjoin(CommercialPartner, 
            and_(
                ParkingPass.tenant_type == 'commercial',
                ParkingPass.partner_id == CommercialPartner.id,
                CommercialPartner.is_deleted == False
            )
        )
        .filter(*filters)
    )

    total = base_query.with_entities(func.count(ParkingPass.id)).scalar()

    results = (
        base_query
        .order_by(ParkingPass.valid_to.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Convert results
    passes_out = []
    for pass_obj, site_name, space_name, zone_name, partner_name in results:
        pass_dict = {
            **{k: v for k, v in pass_obj.__dict__.items() if not k.startswith("_")},
            "site_name": site_name,
            "space_name": space_name,
            "zone_name": zone_name,
            "partner_name": partner_name,
            "family_info": tenants_family_info.get(str(pass_obj.partner_id)) if pass_obj.tenant_type == 'residential' else None
        }
        
        passes_out.append(ParkingPassOut.model_validate(pass_dict))

    return {"passes": passes_out, "total": total}


# ---------------- GET BY ID ----------------
def get_parking_pass_by_id(db: Session, pass_id: UUID):
    return (
        db.query(ParkingPass)
        .filter(ParkingPass.id == pass_id, ParkingPass.is_deleted == False)
        .first()
    )


# ---------------- CREATE ----------------
def create_parking_pass(db: Session, data: ParkingPassCreate):
    payload = data.model_dump()
    tenant_type = payload.get("tenant_type")

    try:
        # ---------------------------- RESIDENTIAL ----------------------------
        if tenant_type == "residential":
            tenant_id = payload.get("partner_id")
            if not tenant_id:
                return error_response(message="partner_id is required for residential parking pass")

            tenant = db.query(Tenant).filter(
                Tenant.id == tenant_id,
                Tenant.is_deleted == False
            ).first()
            if not tenant:
                return error_response(message="Tenant not found")

            tenant_vehicles = [v.get("number") for v in (tenant.vehicle_info or []) if v.get("number")]
            if not tenant_vehicles:
                return error_response(message="No valid vehicles found for tenant")

            # 1. Check ALL duplicates FIRST (before adding anything to session)
            duplicate_vehicles = []
            for vehicle_no in tenant_vehicles:
                exists = db.query(ParkingPass).filter(
                    ParkingPass.vehicle_no == vehicle_no,
                    ParkingPass.is_deleted == False,
                    func.lower(ParkingPass.status) != 'expired'
                ).first()
                if exists:
                    duplicate_vehicles.append(vehicle_no)
            
            if duplicate_vehicles:
                return error_response(
                    message=f"Duplicate parking pass detected for vehicles"
                )

            # 2. Create all passes (only if no duplicates)
            passes_out = []
            created_passes = []
            
            for vehicle_no in tenant_vehicles:
                db_pass = ParkingPass(**{**payload, "vehicle_no": vehicle_no})
                db.add(db_pass)
                created_passes.append(db_pass)
            
            # 3. Commit once for all passes
            db.commit()
            
            for db_pass in created_passes:
                db.refresh(db_pass)
                db_pass_dict = {k: v for k, v in db_pass.__dict__.items() if not k.startswith("_")}
                
                # Create Pydantic object
                pass_out = ParkingPassOut.model_validate(db_pass_dict)
                
                # Set family_info from tenant (parsing JSON if needed)
                if tenant.family_info:
                    if isinstance(tenant.family_info, str):
                        try:
                            pass_out.family_info = json.loads(tenant.family_info)
                        except:
                            pass_out.family_info = []
                    else:
                        pass_out.family_info = tenant.family_info
                else:
                    pass_out.family_info = []
                
                passes_out.append(pass_out)

            return {
                "passes": [p.model_dump() for p in passes_out],
                "family_info": tenant.family_info or []
            }

        # ---------------------------- COMMERCIAL ----------------------------
        elif tenant_type == "commercial":
            vehicle_no = payload.get("vehicle_no")
            if not vehicle_no:
                return error_response(message="vehicle_no is mandatory for commercial parking pass")

            partner_id = payload.get("partner_id")
            # Check duplicate first
            exists = db.query(ParkingPass).filter(
                ParkingPass.vehicle_no == vehicle_no,
                ParkingPass.is_deleted == False,
                func.lower(ParkingPass.status) != 'expired'
            ).first()
            if exists:
                return error_response(message=f"Duplicate parking pass detected for {vehicle_no}")

            # Only create if no duplicate
            db_pass = ParkingPass(**payload)
            db.add(db_pass)
            db.commit()
            db.refresh(db_pass)

            db_pass_dict = {k: v for k, v in db_pass.__dict__.items() if not k.startswith("_")}
            pass_out = ParkingPassOut.model_validate(db_pass_dict)

            return {"passes": [pass_out.model_dump()]}

        # ---------------------------- INVALID TYPE ----------------------------
        else:
            return error_response(message="Invalid tenant_type. Allowed values: residential | commercial")

    except Exception as e:
        # Ensure rollback on any exception
        db.rollback()
        return error_response(message=str(e))



# ---------------- UPDATE ----------------
def update_parking_pass(db: Session, data: ParkingPassUpdate):
    db_pass = get_parking_pass_by_id(db, data.id)
    if not db_pass:
        return None

    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(db_pass, k, v)

    db.commit()
    db.refresh(db_pass)
    return db_pass


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
def get_partner_vehicle_family_info(db: Session, org_id: UUID, partner_id: UUID, tenant_type: str = None):
    """
    Fetch vehicle info and family info for a specific partner
    """
    try:
        # If tenant_type is specified, search in that specific table
        if tenant_type == "commercial":
            # Check CommercialPartner table
            partner = db.query(CommercialPartner).filter(
                CommercialPartner.id == partner_id,
                CommercialPartner.is_deleted == False
            ).first()
            
            if not partner:
                return error_response(message="Commercial partner not found")
            
            # Parse vehicle_info for commercial
            vehicles = []
            if partner.vehicle_info:
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
                            vehicles.append(VehicleInfo(
                                type=vehicle.get("type"),
                                number=vehicle.get("number")
                            ))
            
            # Commercial partners don't have family_info
            return {
                "partner_id": partner.id,
                "partner_name": partner.name,
                "vehicles": vehicles,
                "family_info": None,
                "partner_type": "commercial"
            }
            
        elif tenant_type == "residential" or tenant_type is None:
            # Check Tenant table (default to residential if not specified)
            partner = db.query(Tenant).filter(
                Tenant.id == partner_id,
                Tenant.is_deleted == False
            ).first()
            
            if not partner:
                # If tenant_type not specified, also check commercial
                if tenant_type is None:
                    commercial_partner = db.query(CommercialPartner).filter(
                        CommercialPartner.id == partner_id,
                        CommercialPartner.is_deleted == False
                    ).first()
                    
                    if commercial_partner:
                        # Parse vehicle_info for commercial
                        vehicles = []
                        if commercial_partner.vehicle_info:
                            if isinstance(commercial_partner.vehicle_info, str):
                                try:
                                    vehicles_data = json.loads(commercial_partner.vehicle_info)
                                except:
                                    vehicles_data = []
                            else:
                                vehicles_data = commercial_partner.vehicle_info
                            
                            if isinstance(vehicles_data, list):
                                for vehicle in vehicles_data:
                                    if isinstance(vehicle, dict) and vehicle.get("number"):
                                        vehicles.append(VehicleInfo(
                                            type=vehicle.get("type"),
                                            number=vehicle.get("number")
                                        ))
                        
                        return {
                            "partner_id": commercial_partner.id,
                            "partner_name": commercial_partner.name,
                            "vehicles": vehicles,
                            "family_info": None,
                            "partner_type": "commercial"
                        }
                
                return error_response(message="Partner not found")
            
            # Parse vehicle_info for residential
            vehicles = []
            if partner.vehicle_info:
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
                            vehicles.append(VehicleInfo(
                                type=vehicle.get("type"),
                                number=vehicle.get("number")
                            ))
            
            # Parse family_info for residential
            family_info = []
            if partner.family_info:
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
                                member=member.get("member"),
                                relation=member.get("relation", "")
                            ))
            
            return {
                "partner_id": partner.id,
                "partner_name": partner.name,
                "vehicles": vehicles,
                "family_info": family_info,
                "partner_type": "residential"
            }
        
        else:
            return error_response(
                message="Invalid tenant_type. Allowed values: residential or commercial"
            )
            
    except Exception as e:
        return error_response(message=str(e))