from typing import List, Dict
from fastapi.responses import StreamingResponse
from io import BytesIO
import pandas as pd

from shared.schemas import ExportResponse


def export_to_excel(
    data: List[Dict],
    filename: str = "export.xlsx",
    column_map: Dict[str, str] | None = None,
) -> ExportResponse:
    """
    Export a list of dictionaries to Excel with proper headers and safe handling of missing keys.

    Args:
        data: List of dictionaries (each dict = row)
        filename: Name of the Excel file
        column_map: Mapping of data keys -> friendly column names
    """
    if not data:
        # Avoid empty DataFrame error
        data = [{}]

    # Fill missing keys to avoid KeyError
    if column_map:
        for key in column_map.keys():
            for row in data:
                if key not in row:
                    row[key] = None

    # Create DataFrame
    df = pd.DataFrame(data)

    # Rename columns if mapping provided
    if column_map:
        df = df.rename(columns=column_map)
        # Keep only columns that exist in df (safe)
        existing_columns = [
            col for col in column_map.values() if col in df.columns]
        df = df[existing_columns]
        data = df.to_dict(orient="records")  # convert back to list of dicts

    return ExportResponse(filename=filename, data=data)

    # # Create Excel in-memory
    # output = BytesIO()
    # with pd.ExcelWriter(output, engine="openpyxl") as writer:
    #     df.to_excel(writer, index=False, sheet_name="Data")

    # output.seek(0)

    # headers = {
    #     "Content-Disposition": f'attachment; filename="{filename}"'
    # }

    # return StreamingResponse(
    #     output,
    #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    #     headers=headers
    # )
