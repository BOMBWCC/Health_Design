### 个人健康数据中台 - Vibe Coding 操作指南 (v1.2)

Vibe Coding 的核心在于“规划就是一切”和“构建记忆库 (Memory Bank)”。请在编辑器中确保项目根目录存在 `memory-bank` 文件夹，作为 AI 的单一真相源。

#### 第一步：初始化项目上下文 (Memory Bank)
将以下核心文档交由 AI 消化，并持久化到 `memory-bank/` 文件夹中：

**1. 产品需求文档 (`prd.md`)**
*   **目标**: 全自动化的个人健康数据采集、存储与分析中台。
*   **核心模块**: 鉴权隔离 (JWT + API Key)、数据批量写入 (ODS 层)、定时聚合 (DWS 层)、AI 语义化查询。
*   **多租户隔离**: 强制在所有 Query/Insert 中追加 `WHERE user_id = {current_user_id}`。

**2. 技术栈申明 (`tech-stack.md`)**
*   **API**: FastAPI (Python 3.10+)。
*   **DB**: PostgreSQL (异步支持, TIMESTAMPTZ 存储)。
*   **ORM**: SQLAlchemy 2.0 (适配异步引擎)。
*   **管理**: Poetry (`pyproject.toml`, `package-mode = false`)。
*   **部署**: Docker Compose (API + DB)。

**3. 架构规范与系统模式 (`system-patterns.md`)**
*   **解耦铁律**: **Pydantic 模型 (API 层) 必须与 SQLAlchemy 模型 (DB 层) 严格分离**。严禁将数据库实体直接暴露给 API 响应。
*   **时区中转站**: 
    *   入库: `ISO8601 String` -> `Aware Datetime (UTC)` -> `PostgreSQL TIMESTAMPTZ`。
    - 聚合: 基于 `DISPLAY_TIMEZONE` 计算窗口，但 `record_date` 存储为严格 UTC 零点对齐的 `DATE` 类型。
*   **目录稳定性**: AI 严禁在未经许可下修改 `README.md` 中定义的 `health_backend/` 骨架。

**4. AI 系统规则 (`AGENTS.md`)**
在项目根目录创建此文件，并标记为 **"Always Apply"**:
```markdown
# 始终应用的规则
1. 写代码前必读 `memory-bank/` 所有文档，尤其是 `prd.md`。
2. 数据库变更必须通过 Alembic 生成迁移脚本，禁止手动执行原始 SQL。
3. 任何逻辑变更后，必须同步更新 `memory-bank/architecture.md` 解释文件作用。
4. 严禁使用 Emoji。所有注释与日志需保持专业、严谨。
5. 每次执行 Migration 后，必须核对 Python 模型与数据库 Schema 是否一致，防止“Schema 漂移”。
```

#### 第二步：生成分步实施计划 (`implementation-plan.md`)
生成计划时，必须遵循“小步快跑”原则，每一步都包含明确的验证方法 (TDD)。

---

#### 第三步：启动 Vibe Coding 循环 (TDD 版)
1. **确认启动**: "阅读 `/memory-bank` 里的所有文档，计划是否清晰？有哪些潜在的技术坑需要我提前规避？"
2. **测试先行**: "执行第 X 步。请先编写 `pytest` 测试用例（覆盖正常流与异常流），然后再编写业务逻辑代码。"
3. **存档进度**: 测试通过后，更新 `progress.md` 和 `architecture.md`。

#### 第四步：Debug 与上下文管理
* **只读点菜**: 遇到复杂逻辑时，先问 AI 需要哪些文件的上下文，再精准提供。
* **数据护航**: 尽早编写 `scripts/generate_mock_data.py`，确保 ETL 和查询逻辑有充足的真实样本（带时区）支撑。
