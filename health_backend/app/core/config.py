from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # 1. 数据库配置
    DB_URL: str
    
    # 2. 安全配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5256000  # 约 10 年
    
    # 3. 初始管理员配置
    INITIAL_ADMIN_USER: str
    INITIAL_ADMIN_PASS: str
    INITIAL_ADMIN_FULLNAME: str = "Admin"
    
    # 4. ETL 调度配置
    AGGREGATION_FREQUENCY: str = "DAILY"
    AGGREGATION_START_TIME: str = "2026-04-01T00:00:00Z"
    DISPLAY_TIMEZONE: str = "Asia/Shanghai"

    # 读取 .env 文件
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# 实例化全局配置对象
settings = Settings()
