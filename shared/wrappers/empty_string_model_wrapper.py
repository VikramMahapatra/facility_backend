from datetime import date, datetime
import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, model_validator
from typing import Any, List, Union, get_args, get_origin

# Regex to remove invisible Unicode chars like \u202c, \u200e, etc.
INVISIBLE_CHARS_PATTERN = re.compile(
    r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]')


def deep_clean(value: Any):
    """Recursively clean invisible Unicode chars and empty strings."""
    if isinstance(value, dict):
        return {k: deep_clean(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [deep_clean(v) for v in value]
    elif isinstance(value, str):
        cleaned = INVISIBLE_CHARS_PATTERN.sub('', value).strip()
        return None if cleaned == "" else cleaned
    return value


class EmptyStringModel(BaseModel):
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "exclude_none": False,
    }

    # STEP 1️⃣: Clean before validation
    @model_validator(mode="before")
    @classmethod
    def clean_input(cls, values):
        if isinstance(values, dict):
            return deep_clean(values)
        return values

    # STEP 2️⃣: Run remove_nulls after validation
    @model_validator(mode="after")
    def remove_nulls(self):
        """Replace None fields with sensible defaults for frontend consistency."""
        for field_name, field in self.model_fields.items():
            value = getattr(self, field_name)
            if value is None:
                annotation = field.annotation
                origin = get_origin(annotation)
                args = get_args(annotation)

                # ✅ Nested models (direct or Optional[Model])
                nested_model_type = None
                if hasattr(annotation, "__fields__"):
                    nested_model_type = annotation
                elif origin is Union:
                    for a in args:
                        if hasattr(a, "__fields__"):
                            nested_model_type = a
                            break

                if nested_model_type:
                    object.__setattr__(self, field_name, {})
                    continue

                # Lists
                if origin in (list, List) or annotation in (list, List):
                    object.__setattr__(self, field_name, [])
                    continue

                # Strings / Email / Optional[str]
                if (
                    annotation == str
                    or (origin is Union and any(a == str for a in args))
                ):
                    object.__setattr__(self, field_name, "")
                    continue

                # UUID or Optional[UUID]
                if (
                    annotation == UUID
                    or (origin is Union and any(a == UUID for a in args))
                ):
                    object.__setattr__(self, field_name, "")
                    continue

                # Dates
                if (
                    annotation in (date, datetime)
                    or (origin is Union and any(a in (date, datetime) for a in args))
                ):
                    object.__setattr__(self, field_name, "")
                    continue

        return self
