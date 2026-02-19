from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from facility_service.app.enum.space_sites_enum import APARTMENT_SUB_KINDS, KIND_TO_CATEGORY, SPACE_KINDS
from shared.core.schemas import CommonQueryParams


# ======================
# Base Schema
# ======================

class MaintenanceTemplateBase(BaseModel):
    name: str = Field(..., max_length=100)
    calculation_type: str
    amount: Decimal

    category: Optional[str] = None
    kind: Optional[str] = None
    sub_kind: Optional[str] = None
    site_id: Optional[UUID] = None
    tax_code_id: Optional[UUID] = None


# ======================
# Create Schema
# ======================

class MaintenanceTemplateCreate(MaintenanceTemplateBase):
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


# ======================
# Update Schema
# ======================

class MaintenanceTemplateUpdate(MaintenanceTemplateBase):
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


# ======================
# Response Schema
# ======================

class MaintenanceTemplateResponse(MaintenanceTemplateBase):
    id: UUID
    org_id: UUID
    site_name: Optional[str] = None
    tax_rate: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ======================
# List Response
# ======================

class MaintenanceTemplateListResponse(BaseModel):
    templates: List[MaintenanceTemplateResponse]
    total: int


class MaintenanceTemplateRequest(CommonQueryParams):
    site_id: Optional[str] = None
    category: Optional[str] = None
    kind: Optional[str] = None
    sub_kind: Optional[str] = None
