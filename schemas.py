from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
import re

class HousePredictionRequest(BaseModel):
    sqft: int = Field(default=1800, ge=300, le=30000, description="Total living area in square feet")
    bedrooms: int = Field(default=3, ge=1, le=10, description="Count of bedrooms")
    bathrooms: float = Field(default=2.0, ge=1.0, le=8.0, description="Count of bathrooms")
    location_tier: Literal['Budget', 'Suburban', 'Urban', 'Prime', 'Luxury'] = Field(
        default='Urban', 
        description="Market valuation locality tier"
    )
    year_built: int = Field(default=2018, ge=1920, le=2026, description="Construction year")
    school_rating: float = Field(default=8.0, ge=1.0, le=10.0, description="Local school rating")
    distance_to_city_center_km: float = Field(default=12.0, ge=0.1, le=60.0, description="Distance to CBD in km")
    garage_cars: int = Field(default=1, ge=0, le=6, description="Garage parking capacity")
    lot_size_sqft: int = Field(default=3500, ge=300, le=50000, description="Total plot/lot area in square feet")
    renovated: int = Field(default=0, ge=0, le=1, description="1 if renovated in last 10 years, else 0")
    locality: Optional[str] = Field(default=None, max_length=120, description="Optional Bengaluru locality name")

    @field_validator('bathrooms')
    @classmethod
    def validate_bathrooms(cls, v, info):
        # Business logic: Bathrooms shouldn't wildly exceed bedrooms
        return round(float(v), 1)

class LeadCaptureRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full customer name")
    phone: str = Field(..., min_length=10, max_length=15, description="Contact phone number")
    email: str = Field(..., min_length=5, max_length=120, description="Contact email address")
    locality: Optional[str] = Field(default='Bengaluru', max_length=100)
    property_sqft: Optional[int] = Field(default=None, ge=100, le=50000)
    estimated_price: Optional[float] = Field(default=None, ge=0)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return digits[-10:]

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        email_clean = v.strip().lower()
        if '@' not in email_clean or '.' not in email_clean:
            raise ValueError("Invalid email format")
        return email_clean
