from enum import Enum


class RevenueMonth(str, Enum):
    LAST_MONTH = "1"
    LAST_3_MONTHS = "2"
    LAST_6_MONTHS = "3"
    LAST_YEAR = "4"


class InvoicePayementMethod(str, Enum):
    cheque = "cheque"
    cash = "chash"
    card = "card"
    upi = "upi"


class InvoiceType(str, Enum):
    rent = "rent"
    work_order = "work_order"
    owner_maintenance = "owner_maintenance"
    parking_pass = "parking_pass"
