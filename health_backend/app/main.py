from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import os

from app.api.v1 import health, auth, upload, query, tasks
from app.core.config import settings
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
    """
    logger.info("Simple Scheduler started.")
    await asyncio.sleep(60) 
    
    while True:
        try:
            logger.info("Scheduler: Triggering automated aggregation for all users...")
            run_all_users_aggregation()
            logger.info("Scheduler: Aggregation cycle completed.")
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
        
        await asyncio.sleep(43200)

# --- 3. 生命周期管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Application starting: Initializing DB...")
        init_db()
    except Exception as e:
        logger.warning(f"DB Initialization skipped or failed: {e}. (This is normal in test environments)")
    
    scheduler_task = asyncio.create_task(simple_scheduler())
    yield
    logger.info("Application shutting down: Cleaning up tasks...")
    scheduler_task.cancel()

def create_app() -> FastAPI:
    docs_url = "/docs" if settings.ENABLE_API_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_API_DOCS else None
    openapi_url = "/openapi.json" if settings.ENABLE_API_DOCS else None

    app = FastAPI(
        title="Personal Health Data Hub",
        description="Automated collection and analysis hub for Apple Health data.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # --- 5. 中间件与静态文件 ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # --- 6. 注册路由 (v1) ---
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(upload.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")

    @app.get("/")
    async def root():
        """Serve the frontend index page."""
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {
            "message": "Welcome to Health Data Hub API",
            "docs": docs_url,
            "version": "v1"
        }

    return app


app = create_app()
