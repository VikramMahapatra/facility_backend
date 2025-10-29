from typing import Any, Dict, List, Optional, get_args, get_origin
from pydantic import BaseModel, model_validator


class EmptyStringModel(BaseModel):

    @model_validator(mode="after")
    def remove_nulls(self):
        for field_name, field in self.model_fields.items():
            value = getattr(self, field_name)

            if value is None:
                if hasattr(field.annotation, "__fields__"):
                    setattr(self, field_name, {})         # Object field -> {}
                elif field.annotation in (list, List, list[Any]):
                    setattr(self, field_name, [])         # List -> []
                else:
                    setattr(self, field_name, "")         # String/others -> ""

        return self
