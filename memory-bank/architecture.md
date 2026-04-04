# Architecture

## 1. Current System State

项目当前已经基本完成，整体采用固定链路：

`iOS Shortcuts -> FastAPI Upload API -> ODS Raw Tables -> ETL Aggregation -> DWS Summary Table -> Query API / AI Consumer`

核心设计目标有三点：

1. ODS 层按健康维度分表，负责原始数据落库与去重。
2. DWS 层固定写入 `daily_metrics_summary`，负责按日输出可查询结果。
3. 新增维度时尽量不改主链路，只补充“表 + 元数据 + ETL 映射”。

这意味着后续新增和维护应当是低成本、可重复的工作，而不是重新设计系统。

## 2. Module Responsibilities

### 2.1 API Layer

- `health_backend/app/api/v1/upload.py`
  负责接收 iOS 快捷指令上传的数据，根据 `data_category_registry` 把数据写入对应 ODS 表。
- `health_backend/app/api/v1/query.py`
  负责从 `daily_metrics_summary` 查询聚合结果，并按需关联 `metric_definitions` 返回元数据。
- `health_backend/app/api/v1/auth.py`
  负责登录和身份验证。
- `health_backend/app/api/v1/tasks.py`
  负责触发 ETL 聚合任务。

### 2.2 DB Layer

- `health_backend/app/db/models.py`
  定义核心元数据表、DWS 表、任务日志表等 ORM 模型。
- `health_backend/app/db/ods_manager.py`
  根据 ODS 模板自动创建注册过的原始表。
- `health_backend/app/db/init_db.py`
  初始化核心表、默认用户、默认 registry、默认 metric definitions，并同步 ODS 物理表。

### 2.3 ETL Layer

- `health_backend/app/tasks/aggregate.py`
  当前通用 ETL 入口。按用户、按分类扫描 ODS 表，按 UTC 日期聚合，再 UPSERT 到 `daily_metrics_summary`。

## 3. Core Data Model

### 3.1 Fixed Core Tables

这些表属于系统骨架，后续一般不会频繁变化：

- `users`
- `user_api_keys`
- `data_category_registry`
- `metric_definitions`
- `daily_metrics_summary`
- `task_execution_logs`

其中最关键的两个“配置表”如下：

#### `data_category_registry`

作用：定义“业务维度 -> ODS 物理表”的映射。

例如：

- `heart_rate -> raw_heart_rate`
- `step_count -> raw_step_count`
- `sleep_analysis -> raw_sleep_analysis`

`upload.py` 不直接写死表名，而是先查这个表，再决定写哪张 ODS 表。

#### `metric_definitions`

作用：定义某个分类在 DWS 层需要输出哪些指标，以及这些指标的语义。

例如：

- `heart_rate / avg`
- `heart_rate / max`
- `heart_rate / min`
- `step_count / sum`

`query.py` 会用它补充 `display_name`、`unit`、`description`。

### 3.2 Fixed DWS Table

#### `daily_metrics_summary`

这是当前唯一的日级汇总输出表，也是查询层固定依赖的结果表。

后续即使新增维度，原则上仍然写入这张表，而不是为每个维度再建新的 DWS 表。

唯一键：

- `(user_id, record_date, category, metric_name)`

因此 ETL 可以安全使用 UPSERT 覆盖旧结果，支持迟到数据重算。

### 3.3 ODS Table Pattern

当前多数 ODS 表遵循统一结构：

- `id`
- `user_id`
- `value`
- `unit`
- `start_time`
- `end_time`
- `source`
- `batch_id`
- `created_at`
- `updated_at`

并统一具备两个索引：

- 去重唯一索引：`(user_id, start_time, end_time, value, source)`
- 查询索引：`(user_id, start_time)`

这套结构适合绝大多数数值型维度，例如：

- `raw_step_count`
- `raw_stand_hours`
- `raw_active_energy`
- `raw_resting_heart_rate`
- `raw_walking_heart_rate`
- `raw_hrv`

### 3.4 Special ODS Case

`raw_sleep_analysis` 是当前已知的特殊情况：

- 其 `value` 表示状态枚举，而不是数值。
- 这种表不适合直接复用当前 `AVG/MAX/MIN/SUM` 的通用数值聚合逻辑。

因此，后续新增维度时要先判断它属于哪一类：

1. 数值型原始数据：尽量复用通用 ODS 模板和通用 ETL。
2. 状态型、区间型、组合型原始数据：需要单独设计 ETL 计算逻辑。

## 4. Current Data Flow

### 4.1 Upload Path

1. 客户端调用 `/api/v1/upload`
2. 服务端根据 `payload.category` 查询 `data_category_registry`
3. 找到对应 ODS 表名
4. 将上传数据补齐 `user_id`、`batch_id`
5. 写入对应 ODS 表
6. 通过唯一索引实现幂等去重

这里的关键点是：

- 上传链路只依赖 registry，不依赖硬编码分类判断。
- 所有写入都必须绑定当前登录用户的 `user_id`。

### 4.2 Aggregation Path

1. ETL 任务读取所有启用中的 `data_category_registry`
2. 对每个 category 读取对应 ODS 表
3. 按 UTC 日期聚合
4. 读取该分类下所有 `metric_definitions`
5. 把聚合结果映射为 `avg/max/min/sum` 等指标
6. UPSERT 到 `daily_metrics_summary`
7. 写入 `task_execution_logs`

### 4.3 Query Path

1. 客户端调用 `/api/v1/query/metrics`
2. 查询 `daily_metrics_summary`
3. 强制按 `current_user.id` 过滤
4. 按需关联 `metric_definitions`
5. 返回最终结果给 AI 或前端调用方

## 5. Legacy Note: `raw_heart_rate`

`raw_heart_rate` 在当前代码中仍然存在，并且现有初始化逻辑和 ETL 设计是围绕它建立的。

虽然它已从最新 `datamodel.md` 中删除，不再作为文档主事实来源，但它仍然可以作为“标准数值型维度”的参考实现：

- ODS 表结构标准
- registry 注册方式
- metric definitions 配置方式
- `avg/max/min` 聚合模式
- DWS 写入方式

后续新增数值型维度时，可以把它视作实现模板，而不需要把它重新写回数据模型文档。

## 6. How To Add A New Dimension

后续新增维度，默认按下面顺序处理。

### 6.1 Step 1: Decide the ODS Shape

先判断新增维度是否适合标准 ODS 模板。

适合标准模板的情况：

- 原始数据是单值数值
- 可以基于 `AVG/MAX/MIN/SUM/COUNT` 等聚合得到日汇总
- 上传粒度仍然是 `(value, start_time, end_time, source)`

如果不适合，例如：

- `value` 是状态字符串
- 需要按区间时长计算
- 需要从多个字段联合推导

则应该新建专用 ODS 表结构和专用 ETL 逻辑。

### 6.2 Step 2: Create or Register the ODS Table

如果是标准数值型维度：

1. 在 `data_category_registry` 新增映射
2. 保证 `table_name` 命名遵循 `raw_<category>` 形式
3. 通过 `ods_manager.py` 的模板创建物理表

如果是特殊维度：

1. 用 Alembic 创建新表
2. 保留必须字段：`user_id`、时间字段、来源字段、审计字段
3. 为去重和查询建立合适索引

注意：根据仓库规则，未来 schema 变更应优先走 Alembic，而不是长期依赖手写 SQL 初始化。

### 6.3 Step 3: Register Semantic Metadata

无论是标准维度还是特殊维度，都要补：

1. `data_category_registry`
2. `metric_definitions`

其中：

- `data_category_registry` 决定上传写入哪里
- `metric_definitions` 决定 DWS 产出哪些指标、查询时显示什么语义

如果只建表，不补这两个配置，系统链路是不完整的。

### 6.4 Step 4: Add ETL Logic

如果是标准数值型维度，并且只需要：

- `avg`
- `max`
- `min`
- `sum`

那么通常不需要新增一整套 ETL 文件，只需要：

1. 确保该 category 已在 registry 注册
2. 确保 `metric_definitions` 补齐对应 metric
3. 让 `aggregate.py` 可以扫到该 category

如果新增维度需要特殊计算，例如：

- 睡眠总时长
- 各睡眠状态占比
- 特定区间内最大/最小值
- 多条原始记录合并成一个业务指标

则应在 `aggregate.py` 中增加该 category 的专用分支，或者拆出独立聚合函数。

建议模式：

- 通用数值型维度：走统一聚合 SQL
- 特殊维度：写独立函数，最终仍统一写入 `daily_metrics_summary`

### 6.5 Step 5: Keep DWS Contract Stable

新增维度时，尽量不要改变查询层协议，而是复用已有 DWS 输出模型：

- `record_date`
- `category`
- `metric_name`
- `value`
- `sample_count`

这样 `query.py` 和上层 AI 使用方式可以保持稳定。

## 7. ETL Design Guidelines

### 7.1 For Standard Numeric Dimensions

推荐直接复用当前模式：

- 按 `start_time AT TIME ZONE 'UTC'` 取日期
- 按 `user_id` 和时间窗口过滤
- 按日期分组
- 计算 `COUNT/AVG/MAX/MIN/SUM`
- 根据 `metric_definitions.metric_name` 做映射
- 统一 UPSERT 到 `daily_metrics_summary`

这类维度的开发成本最低。

### 7.2 For Special Dimensions

如果维度是状态型或逻辑更复杂，ETL 设计应先回答三个问题：

1. ODS 原始记录表达的是什么事实。
2. DWS 需要输出什么日级指标。
3. 每个指标能否稳定映射到 `metric_name + value`。

只要最后仍然能收敛为：

- 一个 `record_date`
- 一个 `category`
- 一个 `metric_name`
- 一个数值结果

就可以继续沿用现有查询层和 AI 层。

## 8. Development Constraints

后续继续开发时，必须维持以下约束：

- 所有数据操作必须带 `user_id` 过滤，保证多租户隔离。
- 全链路使用 UTC，代码中使用 `datetime.now(timezone.utc)`。
- Pydantic schema 与 SQLAlchemy model 必须分离。
- 新的 schema 变更应通过 Alembic 管理。
- 不要让新增维度破坏现有 `upload -> aggregate -> query` 主链路。

## 9. Practical Rule Of Thumb

后续如果要新增一个健康维度，优先按下面判断：

1. 能不能复用标准数值型 ODS 表结构。
2. 能不能最终写回 `daily_metrics_summary`。
3. 能不能只通过补 `registry + metric_definitions` 完成接入。
4. 如果不能，再为该维度补专用 ETL。

简化理解就是：

- 新增维度的难点通常不在 API。
- 真正需要确认的是 ODS 结构和 ETL 计算方式。
- 只要 DWS 输出契约不变，后续维护成本就会很低。
