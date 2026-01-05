from sqlalchemy import (Column,String,Boolean,Integer,DateTime)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from shared.core.database import Base

from fastapi import Request, Response
from datetime import datetime
from typing import Any
import json
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ---------- General ----------
    system_name = Column(String(100), nullable=False)
    time_zone = Column(String(50), nullable=False)
    date_format = Column(String(20), nullable=False, default="MM/DD/YYYY")
    currency = Column(String(10), nullable=False)

    auto_backup = Column(Boolean, default=True)
    maintenance_mode = Column(Boolean, default=False)

    # ---------- Security ----------
    password_expiry_days = Column(Integer, default=90)
    session_timeout_minutes = Column(Integer, default=30)
    api_rate_limit_per_hour = Column(Integer, default=1000)

    two_factor_auth_enabled = Column(Boolean, default=False)
    audit_logging_enabled = Column(Boolean, default=True)
    data_encryption_enabled = Column(Boolean, default=True)
    
    # ---------- Integrations ----------
    email_service_enabled = Column(Boolean, default=False)
    weather_api_enabled = Column(Boolean, default=False)
    energy_monitoring_enabled = Column(Boolean, default=False)
    sms_service_enabled = Column(Boolean, default=False)
    accounting_system_enabled = Column(Boolean, default=False)
    can_sync_to_hrms = Column(Boolean, default=False)


    # ---------- Meta ----------
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

 
 
 
 

    @staticmethod
    def get_current_date_format(db: Session) -> str:
        """Get current system date format from database"""
        try:
            setting = db.query(SystemSetting).first()
            return setting.date_format if setting else "MM/DD/YYYY"
        except Exception as e:
            print(f"Error getting date format: {e}")
            return "MM/DD/YYYY"

    @staticmethod
    def create_date_format_middleware():
        """Middleware that REPLACES date values with formatted ones"""
        
        async def middleware(request: Request, call_next):
            # Process request
            response = await call_next(request)
            
            # Only format JSON responses
            if "application/json" not in response.headers.get("content-type", ""):
                return response
            
            # Get response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Parse JSON
                data = json.loads(body.decode('utf-8'))
                
                # Import get_facility_db
                from shared.core.database import get_facility_db
                
                # Get database session
                db_gen = get_facility_db()
                db = next(db_gen)
                
                try:
                    # Get current date format
                    setting = db.query(SystemSetting).first()
                    date_format = setting.date_format if setting else "MM/DD/YYYY"
                    
                    # Convert to Python format
                    python_format = date_format \
                        .replace("DD", "%d") \
                        .replace("MM", "%m") \
                        .replace("YYYY", "%Y") \
                        .replace("YY", "%y")
                    
                    # Function to REPLACE dates (not add new fields)
                    def replace_dates(obj):
                        if isinstance(obj, dict):
                            result = {}
                            for key, value in obj.items():
                                if isinstance(value, str):
                                    # Try to parse as date
                                    try:
                                        if "T" in value and ":" in value:  # ISO datetime
                                            date_str = value.replace('Z', '+00:00')
                                            date_obj = datetime.fromisoformat(date_str)
                                            # ✅ REPLACE with formatted date
                                            result[key] = date_obj.strftime(python_format)
                                        elif len(value) == 10 and value.count("-") == 2:  # YYYY-MM-DD
                                            date_obj = datetime.strptime(value, "%Y-%m-%d")
                                            # ✅ REPLACE with formatted date
                                            result[key] = date_obj.strftime(python_format)
                                        else:
                                            result[key] = value
                                    except:
                                        result[key] = value
                                elif isinstance(value, (list, dict)):
                                    result[key] = replace_dates(value)
                                else:
                                    result[key] = value
                            return result
                        elif isinstance(obj, list):
                            return [replace_dates(item) for item in obj]
                        return obj
                    
                    # Replace dates in response
                    if isinstance(data, dict) and "data" in data:
                        data["data"] = replace_dates(data["data"])
                    else:
                        data = replace_dates(data)
                    
                    # Return response with REPLACED dates
                    return Response(
                        content=json.dumps(data, default=str).encode('utf-8'),
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json"
                    )
                    
                finally:
                    # Close database session
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass
                    
            except Exception as e:
                print(f"Date middleware error: {e}")
                # Return original response on error
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
        
        return middleware