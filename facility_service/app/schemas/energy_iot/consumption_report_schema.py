
from pydantic import BaseModel
from typing import Optional
from ...enum.consumption_enum import ConsumptionMonth, ConsumptionType



class ConsumptionReportParams (BaseModel):
    consumption_type: Optional[ConsumptionType] = None
    month: Optional[ConsumptionMonth] = None
