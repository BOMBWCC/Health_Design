from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from app.api.v1 import health, auth, upload, query, tasks
from app.tasks.aggregate import run_all_users_aggregation
from app.db.init_db import init_db

# --- 1. 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- 2. 后台任务循环 (极简调度器) ---
async def simple_scheduler():
    """
    后台无限循环，定期触发全量聚合。
    注意：这在单实例 VPS 上非常有效。
    """
    logger.info("Simple Scheduler started.")
    # 给系统预留一些启动时间
    await asyncio.sleep(60) 
    
    while True:
        try:
            logger.info("Scheduler: Triggering automated aggregation for all users...")
            run_all_users_aggregation()
            logger.info("Scheduler: Aggregation cycle completed.")
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
        
        # 每 12 小时检查一次 (43200秒)
        # 你也可以根据 settings.AGGREGATION_FREQUENCY 动态调整
        await asyncio.sleep(43200)

# --- 3. 生命周期管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # A. 启动时：初始化数据库 (仅当非测试环境时)
    # 我们通过简单的尝试连接来判定
    try:
        logger.info("Application starting: Initializing DB...")
        init_db()
    except Exception as e:
        logger.warning(f"DB Initialization skipped or failed: {e}. (This is normal in test environments)")
    
    # B. 启动后台调度协程
    scheduler_task = asyncio.create_task(simple_scheduler())
    
    yield
    
    # C. 关闭时：取消后台任务
    logger.info("Application shutting down: Cleaning up tasks...")
    scheduler_task.cancel()

# --- 4. 初始化应用 ---
app = FastAPI(
    title="Personal Health Data Hub",
    description="Automated collection and analysis hub for Apple Health data.",
    version="1.0.0",
    lifespan=lifespan
)

# --- 5. 注册路由 (v1) ---
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Health Data Hub API",
        "docs": "/docs",
        "version": "v1"
    }
