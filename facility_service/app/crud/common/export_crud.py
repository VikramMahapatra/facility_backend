from typing import Any, Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from uuid import UUID
from datetime import datetime
from shared.exporthelper import export_to_excel
from shared.schemas import ExportResponse
from ...crud.energy_iot import meters_crud, meter_readings_crud


def get_export_data(db: Session, org_id: UUID, type: str, params: Any) -> ExportResponse:

    if type == "meters":
        export_data = meters_crud.get_list(db, org_id, params, is_export=True)
        data = [row.model_dump() for row in export_data[type]]

        column_map = {
            "code": "Code",
            "kind": "Type",
            "site_name": "Site",
            "space_name": "Location",
            "unit": "Unit",
            "last_reading": "Last Reading",
            "last_reading_date": "Last Reading Date",
            "status": "Status"
        }
    elif type == "readings":
        export_data = meter_readings_crud.get_list(
            db, org_id, params, is_export=True)
        data = [row.model_dump() for row in export_data[type]]
        column_map = {
            "meter_code": "Meter",
            "meter_kind": "Type",
            "reading": "Reading",
            "delta": "Delta",
            "source": "Source",
            "ts": "Timestamp",
        }
    else:
        raise ValueError(f"Unknown export type: {type}")

    filename = f"{type}_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return export_to_excel(data, filename, column_map)
