from enum import Enum

class ConsumptionMonth(str, Enum):
    January_2024 = "1"
    Decemeber_2023 = "2" 
    November_2023 = "3"
    
class ConsumptionType(str, Enum):

    Electricity = "Electricity"
    Water = "Water"
    Gas = "Gas"
    Footfall = "Footfall"

    