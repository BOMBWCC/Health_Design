# 项目测试规范 (Testing Standards)

## 1. 测试工具栈
- **测试框架**: `pytest`
- **异步支持**: `pytest-asyncio`
- **Mocking**: `unittest.mock` (Python 3.10+)
- **HTTP 测试**: `httpx` (推荐配合 FastAPI)

## 2. 测试分类与目标

### 2.1 单元测试 (Unit Tests)
- **目标**: 针对核心算法和独立函数。
- **重点**:
    - `app/core/security.py`: JWT 加密与解密是否正确。
    - `app/schemas/payload.py`: 数据验证逻辑（如: 字符串转浮点）。

### 2.2 集成测试 (Integration Tests)
- **目标**: 针对 API 路由和数据库交互。
- **重点**:
    - `GET /api/v1/health`: 状态自检。
    - `POST /api/v1/auth/login`: 登录流程及 Token 生成。
    - `POST /api/v1/upload`: 数据批量入库及幂等去重校验。

### 2.3 数据聚合测试 (ETL Tests)
- **目标**: 验证 ODS 原始数据聚合为 DWS 汇总数据的准确性。
- **重点**: `app/tasks/aggregate.py` 的算法校验。

## 3. 执行测试 (Commands)
```bash
# 进入后端目录
cd health_backend

# 运行所有测试
poetry run pytest

# 运行并生成覆盖率报告
poetry run pytest --cov=app --cov-report=term-missing
```

---

## 4. 注意事项
- **测试数据库**: 建议在 Docker 环境中使用独立的 `health_hub_test` 数据库进行集成测试。
- **忽略项**: 所有本地生成的 `.coverage` 文件及 `__pycache__/` 必须在 `.gitignore` 中被过滤。
