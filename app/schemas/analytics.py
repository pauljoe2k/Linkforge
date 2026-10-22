from datetime import date

from pydantic import BaseModel, Field


class DeviceBreakdown(BaseModel):
    desktop: int = 0
    mobile: int = 0
    tablet: int = 0
    other: int = 0


class SummaryOut(BaseModel):
    total_clicks: int
    devices: DeviceBreakdown


class DailyPoint(BaseModel):
    day: date
    clicks: int


class DailyOut(BaseModel):
    days: list[DailyPoint]


class ReferrerPoint(BaseModel):
    # NULL referrer means "user typed / came from a bookmark":
    # surfaced as the literal string "direct".
    referrer: str = Field(..., examples=["https://news.ycombinator.com"])
    clicks: int


class ReferrersOut(BaseModel):
    referrers: list[ReferrerPoint]
