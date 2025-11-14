from datetime import date, datetime
import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, model_validator
from typing import Any, List, Union, get_args, get_origin

INVISIBLE_CHARS_PATTERN = re.compile(
    r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]')


def deep_clean(value: Any):
    """Recursively convert empty strings to None, clean invisible chars, and handle nested models."""

    # 1️⃣ Handle Pydantic models
    if isinstance(value, BaseModel):
        data = value.model_dump()
        cleaned = deep_clean(data)
        return type(value)(**cleaned)

    # 2️⃣ Handle dictionaries
    if isinstance(value, dict):
        return {k: deep_clean(v) for k, v in value.items()}

    # 3️⃣ Handle lists
    if isinstance(value, list):
        return [deep_clean(v) for v in value]

    # 4️⃣ Handle strings
    if isinstance(value, str):
        cleaned = value.strip()
        return None if cleaned == "" else cleaned

    # 5️⃣ If the value is UUID but empty string passed somehow
    if isinstance(value, UUID):
        return value  # valid UUID stays UUID

    # Default return
    return value


def safe_parse_date(value: Any):
    """Convert date strings to date/datetime, return None if invalid."""
    if value is None or value == "":
        return None

    # Already a date/datetime
    if isinstance(value, (date, datetime)):
        return value

    # Try parsing ISO formats automatically
    try:
        return datetime.fromisoformat(value).date()
    except:
        pass

    return None  # invalid → None


class EmptyStringModel(BaseModel):
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "exclude_none": False,
    }

    # STEP 1: Pre-clean input
    @model_validator(mode="before")
    @classmethod
    def clean_input(cls, values):
        if isinstance(values, dict):
            return deep_clean(values)
        return values

    # STEP 2: Convert invalid date strings into None
    @model_validator(mode="before")
    @classmethod
    def fix_dates(cls, values):
        if not isinstance(values, dict):
            return values

        for field_name, field in cls.model_fields.items():
            annotation = field.annotation
            raw_value = values.get(field_name)

            origin = get_origin(annotation)
            args = get_args(annotation)

            is_date_field = (
                annotation in (date, datetime)
                or (origin is Union and any(a in (date, datetime) for a in args))
            )

            if is_date_field:
                values[field_name] = safe_parse_date(raw_value)

        return values

    # STEP 3: After validation – format final values for frontend
    @model_validator(mode="after")
    def finalize_nulls(self):
        """Convert None → default UI friendly values (except dates!)."""
        for field_name, field in self.model_fields.items():
            value = getattr(self, field_name)
            annotation = field.annotation
            origin = get_origin(annotation)
            args = get_args(annotation)

            # Nested Model
            nested_model_type = None
            if hasattr(annotation, "__fields__"):
                nested_model_type = annotation
            elif origin is Union:
                for a in args:
                    if hasattr(a, "__fields__"):
                        nested_model_type = a
                        break

            if nested_model_type and value is None:
                object.__setattr__(self, field_name, {})
                continue

            # Lists
            if (origin in (list, List) or annotation in (list, List)) and value is None:
                object.__setattr__(self, field_name, [])
                continue

            # Strings
            if (
                annotation == str
                or (origin is Union and any(a == str for a in args))
            ) and value is None:
                object.__setattr__(self, field_name, "")
                continue

            # UUID
            if (
                annotation == UUID
                or (origin is Union and any(a == UUID for a in args))
            ) and value is None:
                object.__setattr__(self, field_name, "")
                continue

            # Dates (⛔ DO NOT convert to empty string)
            if (
                annotation in (date, datetime)
                or (origin is Union and any(a in (date, datetime) for a in args))
            ):
                # Value is already parsed in fix_dates()
                # If None → keep None so DB receives NULL
                continue

        return self
