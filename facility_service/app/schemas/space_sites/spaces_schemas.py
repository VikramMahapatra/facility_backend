from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, model_validator
from typing import List, Literal, Optional, Any
from decimal import Decimal

from ...enum.space_sites_enum import APARTMENT_SUB_KINDS, KIND_TO_CATEGORY, SPACE_KINDS, SpaceCategory
from ...schemas.parking_access.parking_slot_schemas import AssignedParkingSlot
from shared.utils.enums import OwnershipStatus
from shared.wrappers.empty_string_model_wrapper import EmptyStringModel
from shared.core.schemas import CommonQueryParams


class SpaceAccessoryCreate(BaseModel):
    accessory_id: UUID
    quantity: int
    name: Optional[str] = None


class SpaceBase(EmptyStringModel):
    org_id: Optional[UUID] = None
    site_id: UUID
    name: Optional[str] = None
    kind: str
    sub_kind: Optional[str] = None
    category: SpaceCategory
    floor: Optional[int] = None
    building_block_id: Optional[UUID] = None
    building_block: Optional[str] = None
    area_sqft: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[int] = None
    balconies: Optional[int] = None
    attributes: Optional[Any] = None
    status: Optional[str] = "available"
    accessories: Optional[list[SpaceAccessoryCreate]] = None
    parking_slot_ids: Optional[List[UUID]] = None
    maintenance_template_id: Optional[UUID] = None


class SpaceCreate(SpaceBase):
    pass

    @model_validator(mode="after")
    def validate_kind_category(self):

        # Validate kind exists
        if self.kind not in SPACE_KINDS:
            raise ValueError(f"Invalid space kind: {self.kind}")

        expected_category = KIND_TO_CATEGORY[self.kind]

        # Validate category matches kind
        if self.category != expected_category:
            raise ValueError(
                f"Category '{self.category}' does not match kind '{self.kind}'. "
                f"Expected '{expected_category}'."
            )

        return self

    @model_validator(mode="after")
    def validate_sub_kind(self):

        # ⭐ If apartment → sub_kind required & validated
        if self.kind == "apartment":

            if not self.sub_kind:
                raise ValueError(
                    "sub_kind is required when kind is 'apartment'"
                )

            if self.sub_kind not in APARTMENT_SUB_KINDS:
                raise ValueError(
                    f"Invalid apartment sub_kind '{self.sub_kind}'"
                )

        # ⭐ Non-apartment → sub_kind must be empty
        else:
            self.sub_kind = None

        return self


class SpaceUpdate(SpaceBase):
    id: str
    pass

    @model_validator(mode="after")
    def validate_kind_category(self):

        # Validate kind exists
        if self.kind not in SPACE_KINDS:
            raise ValueError(f"Invalid space kind: {self.kind}")

        expected_category = KIND_TO_CATEGORY[self.kind]

        # Validate category matches kind
        if self.category != expected_category:
            raise ValueError(
                f"Category '{self.category}' does not match kind '{self.kind}'. "
                f"Expected '{expected_category}'."
            )

        return self

    @model_validator(mode="after")
    def validate_sub_kind(self):

        # ⭐ If apartment → sub_kind required & validated
        if self.kind == "apartment":

            if not self.sub_kind:
                raise ValueError(
                    "sub_kind is required when kind is 'apartment'"
                )

            if self.sub_kind not in APARTMENT_SUB_KINDS:
                raise ValueError(
                    f"Invalid apartment sub_kind '{self.sub_kind}'"
                )

        # ⭐ Non-apartment → sub_kind must be empty
        else:
            self.sub_kind = None

        return self


class SpaceOut(SpaceBase):
    id: UUID
    site_name: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    owner_name: Optional[str] = None
    maintenance_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    parking_slots: Optional[List[AssignedParkingSlot]] = None
    parking_slot_ids: Optional[List[UUID]] = None

    model_config = {"from_attributes": True}


class ActiveOwnerResponse(BaseModel):
    id: UUID
    owner_type: str
    user_id: UUID
    full_name: str
    ownership_percentage: Decimal
    start_date: date
    end_date: Optional[date] = None


class SpaceRequest(CommonQueryParams):
    site_id: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None


class SpaceListResponse(BaseModel):
    spaces: List[SpaceOut]
    total: int

    model_config = {"from_attributes": True}


class SpaceOverview(BaseModel):
    totalSpaces: int
    availableSpaces: int
    occupiedSpaces: int
    outOfServices: int

    model_config = {"from_attributes": True}


class AssignSpaceOwnerOut(BaseModel):
    space_id: UUID
    owners: List[ActiveOwnerResponse]

    model_config = {"from_attributes": True}


class AssignSpaceOwnerIn(BaseModel):
    space_id: UUID
    owner_user_id: UUID


class AssignSpaceTenantIn(BaseModel):
    space_id: UUID
    tenant_user_id: UUID


class OwnershipHistoryOut(BaseModel):
    id: UUID
    owner_user_id: Optional[UUID]
    owner_name: Optional[str]
    ownership_type: Optional[str] = None
    ownership_percentage: Optional[Decimal] = None
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class TenantHistoryOut(BaseModel):
    id: UUID
    tenant_user_id: Optional[UUID]
    tenant_name: Optional[str]
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    space_id: Optional[UUID] = None
    space_name: Optional[str] = None
    status: str
    lease_no: Optional[str] = None

    model_config = {"from_attributes": True}


class OwnershipApprovalRequest(BaseModel):
    action: OwnershipStatus
    request_id: str


class OwnershipApprovalListResponse(BaseModel):
    requests: List[OwnershipHistoryOut]
    total: int

    model_config = {"from_attributes": True}


class RemoveOwnerRequest(BaseModel):
    space_id: UUID
    owner_id: UUID


class RemoveSpaceTenantRequest(BaseModel):
    space_id: UUID
    tenant_user_id: UUID
