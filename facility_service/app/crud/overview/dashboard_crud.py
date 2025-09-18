def overview():
    return {
        "total_properties": 24,
        "occupancy_rate": "75.4%",
        "monthly_revenue": "$566.4k",
        "work_orders": 28,
        "rent_collections": "94.2%",
        "energy_usage": "45.7K kWh"
    }

def lease_overview():
    return {
        "active_leases": 187,
        "renewals": {
            "30_days": 12,
            "60_days": 8,
            "90_days": 15
        },
        "collection_rate": "94.2%"
    }

def maintenance_status():
    return {
        "open": 28,
        "closed": 156,
        "upcoming_pm": 23,
        "service_requests": 14,
        "assets_at_risk": 7
    }

def access_and_parking():
    return {
        "todays_visitors": 142,
        "parking_occupancy": {
            "percentage": "78.5%",
            "occupied": 94,
            "total_spaces": 120
        },
        "recent_access_events": [
            {"time": "09:45", "event": "Entry", "location": "Main Gate"},
            {"time": "10:12", "event": "Exit", "location": "Parking Gate"},
            {"time": "10:30", "event": "Entry", "location": "Service Entry"}
        ]
    }

def financial_summary():
    return {
        "monthly_income" : "$487.5k",
        "overdue" : "$125.4k",
        "pending_invoices" : 45,
        "oustanding_CAM" : "$78.9k",
    }
def monthly_revenue_trend():
    return [
        {"month": "Oct", "revenue": 520000},
        {"month": "Nov", "revenue": 540000},
        {"month": "Dec", "revenue": 560000},
        {"month": "Jan", "revenue": 580000},
    ]

def space_occupancy():
    return {
        "occupied": 65,
        "available": 25,
        "out_of_service": 10,
    }
    
def work_orders_priority():
    return {
        "critical": 3,
        "high": 8,
        "medium": 12,
        "low": 5,
    }
def get_energy_consumption_trend():
    return [
        {"month": "Sep", "consumption": 44000},
        {"month": "Oct", "consumption": 45000},
        {"month": "Nov", "consumption": 47000},
        {"month": "Dec", "consumption": 46000},
    ]
