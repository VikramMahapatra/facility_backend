from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from shared.core.database import get_auth_db, get_facility_db as get_db
from shared.helpers.json_response_helper import error_response, success_response
from shared.utils.app_status_code import AppStatusCode
from ...schemas.space_sites.spaces_schemas import ActiveOwnerResponse, AssignSpaceOwnerIn, AssignSpaceOwnerOut, AssignSpaceTenantIn, OwnershipApprovalListResponse, OwnershipApprovalRequest, OwnershipHistoryOut, SpaceListResponse, SpaceOut, SpaceCreate, SpaceOverview, SpaceRequest, SpaceUpdate, TenantHistoryOut
from ...crud.space_sites import spaces_crud as crud
from shared.core.auth import allow_admin,  validate_current_token  # for dependicies
from shared.core.schemas import CommonQueryParams, Lookup, UserToken
from uuid import UUID
router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------


@router.get("/all", response_model=SpaceListResponse)
def get_spaces(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces(db=db, user=current_user, params=params)


@router.get("/overview", response_model=SpaceOverview)
def get_space_overview(
        params: SpaceRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_spaces_overview(db=db, user=current_user, params=params)


@router.post("/", response_model=None)
def create_space(
    space: SpaceCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)
):
    space.org_id = current_user.org_id
    return crud.create_space(db, space)


@router.put("/", response_model=None)
def update_space(
    space: SpaceUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token),
    _: UserToken = Depends(allow_admin)
):

    return crud.update_space(db, space)


@router.delete("/{space_id}", response_model=SpaceOut)
def delete_space(space_id: str, db: Session = Depends(get_db)):
    return crud.delete_space(db, space_id)


@router.get("/lookup", response_model=List[Lookup])
def space_lookup(site_id: Optional[str] = Query(None),
                 building_id: Optional[str] = Query(None),
                 db: Session = Depends(get_db),
                 current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_lookup(db=db, site_id=site_id, building_id=building_id, user=current_user)


@router.get("/space-building-lookup", response_model=List[Lookup])
def space_building_lookup(
        site_id: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_space_with_building_lookup(db, site_id, current_user.org_id)


@router.get("/detail/{space_id:str}", response_model=SpaceOut)
def get_space_details(
        space_id: str,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)
):
    db_space = crud.get_space_details_by_id(db, space_id, current_user)
    return db_space


@router.get("/active-owners/{space_id:str}", response_model=List[ActiveOwnerResponse])
def get_active_space_owners(
    space_id: str,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    owners = crud.get_active_owners(db, auth_db, space_id)
    return owners


@router.post("/assign-owner", response_model=None)
def assign_owner(
    payload: AssignSpaceOwnerIn,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):

    return crud.assign_space_owner(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        payload=payload
    )


@router.post("/assign-tenant", response_model=None)
def assign_space_tenant(
    payload: AssignSpaceTenantIn,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):

    return crud.assign_space_tenant(
        db=db,
        auth_db=auth_db,
        org_id=current_user.org_id,
        payload=payload
    )


@router.get("/ownership-history/{space_id:uuid}", response_model=List[OwnershipHistoryOut])
def ownership_history(
    space_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_space_ownership_history(
        db=db,
        auth_db=auth_db,
        space_id=space_id,
        org_id=current_user.org_id
    )


@router.get("/tenant-history/{space_id:uuid}", response_model=List[TenantHistoryOut])
def tenant_history(
    space_id: UUID,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_space_tenant_history(
        db=db,
        auth_db=auth_db,
        space_id=space_id,
        org_id=current_user.org_id
    )


@router.get("/pending-owner-request", response_model=OwnershipApprovalListResponse)
def get_pending_space_owner_requests(
    params: CommonQueryParams = Depends(),
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_pending_space_owner_requests(db, auth_db, current_user.org_id, params)


@router.post("/update-owner-approval", response_model=OwnershipHistoryOut)
def update_space_owner_approval(
    params: OwnershipApprovalRequest,
    db: Session = Depends(get_db),
    auth_db: Session = Depends(get_auth_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_space_owner_approval(db, auth_db, params.request_id, params.action, current_user.org_id)
