"""Pydantic response/request models."""

from typing import Optional

from pydantic import BaseModel


class PriceObservationOut(BaseModel):
    id: int
    origin: str
    destination: str
    cabin: str
    trip_type: str
    price: float
    airline: Optional[str] = None
    outbound_date: Optional[str] = None
    return_date: Optional[str] = None
    duration_mins: Optional[int] = None
    stops: Optional[int] = None
    checked_at: str

    model_config = {"from_attributes": True}


class MonitoredRouteCreate(BaseModel):
    origin: str
    destination: str = "ANYWHERE"
    cabin: str = "economy"
    trip_type: str = "return"


class MonitoredRouteOut(BaseModel):
    id: int
    origin: str
    destination: str
    cabin: str
    trip_type: str
    active: bool
    created_at: str

    model_config = {"from_attributes": True}


class DealOut(BaseModel):
    id: int
    origin: str
    destination: str
    cabin: str
    trip_type: str
    price: float
    avg_price: float
    discount_pct: float
    airline: Optional[str] = None
    outbound_date: Optional[str] = None
    return_date: Optional[str] = None
    booking_url: Optional[str] = None
    found_at: str
    is_dismissed: bool

    model_config = {"from_attributes": True}


class SettingsOut(BaseModel):
    origins: list[str]
    deal_threshold: float
    scan_interval_hours: int
    lookahead_days: int
    min_observations: int


class SettingsUpdate(BaseModel):
    origins: Optional[list[str]] = None
    deal_threshold: Optional[float] = None
    scan_interval_hours: Optional[int] = None
    lookahead_days: Optional[int] = None
    min_observations: Optional[int] = None


class StatsOut(BaseModel):
    total_observations: int
    total_deals: int
    active_routes: int
    avg_discount: Optional[float] = None


class ScanResult(BaseModel):
    routes_scanned: int
    observations_added: int
    deals_found: int
    errors: int


class ScanStatus(BaseModel):
    running: bool
    progress: float
    current_route: str
    routes_scanned: int
    total_routes: int
    observations_added: int
    deals_found: int
