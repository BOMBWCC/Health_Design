from datetime import datetime

from pydantic import BaseModel


class SleepRecordItem(BaseModel):
    id: int
    value: str
    unit: str | None = None
    start_time: datetime
    end_time: datetime
    duration_hours: float
    source: str | None = None


class SleepRecordsResponse(BaseModel):
    status: str
    count: int
    data: list[SleepRecordItem]
