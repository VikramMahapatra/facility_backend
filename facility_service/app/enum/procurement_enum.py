from enum import Enum

class VendorStatus (str , Enum):

    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class VendorCategories(str, Enum):
    books = "books"
    agriculture = "agriculture"
    stationery = "stationery"
    beverages = "beverages"
    toys = "toys"
    software = "software"
    textiles = "textiles"
    hardware = "hardware"
    oils = "oils"
    furniture = "furniture"
    electrical = "Electrical"
    healthcare = "healthcare"
    hvac = "HVAC"
    clothing = "clothing"
    seeds = "seeds"
    fertilizers = "fertilizers"
    food_products = "food products"
    construction = "construction"
    fashion = "fashion"
    fishing = "fishing"
    civil_works = "civil works"
    cooking = "cooking"
    office_supplies = "office supplies"
    renewable_energy = "renewable energy"
    home_appliances = "home appliances"
    solar_panels = "solar panels"
    seafood = "seafood"
    groceries = "groceries"
    electronics = "electronics"
    home_decor = "home decor"
    eco_products = "eco products"
    appliances = "appliances"
    packaging = "packaging"
    consulting = "consulting"
    it_services = "IT services"
    games = "games"
    plastics = "plastics"
    pharmaceuticals = "pharmaceuticals"

class ContractType(str, Enum) :

    AMC ="AMC"
    SLA = "SLA"
    cleaning = "cleaning"
    security = "security"
    rent_share = "rent share"
    
class ContractStatus (str , Enum):

    active = "active"
    expired = "expired"
    terminated = "terminated"