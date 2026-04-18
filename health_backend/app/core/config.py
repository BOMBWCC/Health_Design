import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BootstrapUserConfig(BaseModel):
    username: str
    password: str
    full_name: str = "User"
    ai_query_api_key: str
    is_active: bool = True

class Settings(BaseSettings):
    # 1. 数据库配置
    DB_URL: str
    
    # 2. 安全配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5256000  # 约 10 年
    ENABLE_API_DOCS: bool = True
    
    # 3. 初始管理员配置
    INITIAL_ADMIN_USER: str
    INITIAL_ADMIN_PASS: str
    INITIAL_ADMIN_FULLNAME: str = "Admin"

    # 3.1 多用户引导配置
    BOOTSTRAP_USERS_FILE: str | None = None
    BOOTSTRAP_USERS_JSON: list[BootstrapUserConfig] = Field(default_factory=list)
    
    # 4. ETL 调度与聚合配置
    # 默认统计粒度: '1d', '12h', '1h'
    DEFAULT_AGG_WINDOW: str = "1d"
    # 默认回溯窗口 (单位: 天)
    DEFAULT_LOOKBACK_DAYS: int = 3
    # 默认任务执行周期 (单位: 分钟)
    DEFAULT_EXEC_INTERVAL_MINUTES: int = 1440 # 24小时
    
    AGGREGATION_START_TIME: str = "2026-04-01T00:00:00Z"
    DISPLAY_TIMEZONE: str = "Asia/Shanghai"

    @field_validator("BOOTSTRAP_USERS_JSON", mode="before")
    @classmethod
    def parse_bootstrap_users(cls, value):
        if value in (None, "", []):
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError("BOOTSTRAP_USERS_JSON must decode to a JSON array.")
            return parsed

        raise ValueError("BOOTSTRAP_USERS_JSON must be a JSON array or JSON string.")

    def load_bootstrap_users(self) -> list[BootstrapUserConfig]:
        if self.BOOTSTRAP_USERS_FILE:
            file_path = Path(self.BOOTSTRAP_USERS_FILE)
            if not file_path.is_absolute():
                file_path = Path.cwd() / file_path

            file_contents = file_path.read_text(encoding="utf-8")
            parsed = json.loads(file_contents)
            if not isinstance(parsed, list):
                raise ValueError("BOOTSTRAP_USERS_FILE must contain a JSON array.")
            return [BootstrapUserConfig.model_validate(item) for item in parsed]

        return self.BOOTSTRAP_USERS_JSON

    # 读取 .env 文件
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# 实例化全局配置对象
settings = Settings()
