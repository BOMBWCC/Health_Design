from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime

# --- 1. 捷径数组内部单条记录 ---
class HealthDataItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    v: str = Field(..., alias="value")
    s: datetime = Field(..., alias="start_time")
    e: datetime = Field(..., alias="end_time")

    @field_validator("s", "e", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v):
        """
        Issue 3 增强：强制要求输入带时区信息的 ISO8601 字符串。
        拒绝 '2026-04-01T00:00:00' 这种模糊输入。
        """
        if isinstance(v, str):
            # 处理结尾的 Z (UTC)
            v_norm = v.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(v_norm)
                if dt.tzinfo is None:
                    raise ValueError("Timezone offset is required (e.g., +08:00 or Z)")
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid ISO8601 format or missing timezone: {str(e)}")
        return v

# --- 2. 核心上传请求载荷 ---
class HealthUploadRequest(BaseModel):
    category: str
    source: str
    unit: str
    data: List[HealthDataItem]

# --- 3. 响应模型 ---
class UploadResponse(BaseModel):
    status: str
    inserted: int
    batch_id: str
    table: str
    skipped: Optional[int] = 0
