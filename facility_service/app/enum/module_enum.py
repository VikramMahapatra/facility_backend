from enum import Enum


class ModuleName(str, Enum):
    invoices = "invoices"
    leases = "leases"
    tenants = "tenants"
    bills = "bills"
