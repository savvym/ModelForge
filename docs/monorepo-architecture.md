# NTA Platform 单仓落地方案

基于约束：

- 单仓
- `frontend / backend / infra` 三层
- 前端：`Next.js + shadcn/ui`
- 后端：`Python + PostgreSQL + Redis + S3/RustFS + REST + SSE/WebSocket + Temporal`
- `infra` 里的依赖通过 Docker 启动

---

## 1. 总体判断

这类控制台不是简单 CRUD 项目，而是“管理台 + 任务系统 + 文件系统 + 实时状态系统”。

因此最稳的切法不是很多微服务一开始全拆开，而是：

- 1 个前端应用
- 1 个 Python API 服务
- 1 个 Temporal Worker 服务
- 1 套 Docker 化基础设施

也就是说，应用层先保持 **2 个运行时服务**：

- `backend/apps/api`
- `backend/apps/worker`

这样既满足单仓和可维护性，也不会在第一阶段把复杂度抬得过高。

---

## 2. 推荐目录结构

```text
nta-platform/
├─ frontend/
│  ├─ app/
│  │  ├─ (console)/
│  │  │  ├─ overview/
│  │  │  ├─ model-square/
│  │  │  ├─ app-lab/
│  │  │  ├─ experience/
│  │  │  ├─ promptpilot/
│  │  │  ├─ endpoint/
│  │  │  ├─ batch-inference/
│  │  │  ├─ model/
│  │  │  │  ├─ finetune/
│  │  │  │  ├─ warehouse/
│  │  │  │  ├─ eval/
│  │  │  │  ├─ eval-create/
│  │  │  │  └─ eval-detail/[id]/
│  │  │  ├─ dataset/
│  │  │  ├─ dataset-create/
│  │  │  ├─ knowledge/
│  │  │  ├─ open-management/
│  │  │  ├─ security/
│  │  │  ├─ api-key/
│  │  │  ├─ usage/
│  │  │  ├─ project/
│  │  │  ├─ network/
│  │  │  └─ token-calculator/
│  │  ├─ api/
│  │  │  └─ bff/
│  │  ├─ layout.tsx
│  │  ├─ loading.tsx
│  │  └─ globals.css
│  ├─ components/
│  │  ├─ ui/
│  │  ├─ console/
│  │  ├─ table/
│  │  ├─ charts/
│  │  └─ forms/
│  ├─ features/
│  │  ├─ auth/
│  │  ├─ project/
│  │  ├─ dataset/
│  │  ├─ model/
│  │  ├─ endpoint/
│  │  ├─ eval/
│  │  ├─ usage/
│  │  └─ security/
│  ├─ lib/
│  │  ├─ api-client/
│  │  ├─ sse/
│  │  ├─ websocket/
│  │  ├─ auth/
│  │  └─ utils/
│  ├─ hooks/
│  ├─ store/
│  ├─ types/
│  ├─ public/
│  ├─ package.json
│  └─ tsconfig.json
│
├─ backend/
│  ├─ apps/
│  │  ├─ api/
│  │  │  ├─ main.py
│  │  │  └─ routers/
│  │  └─ worker/
│  │     ├─ main.py
│  │     └─ workers/
│  ├─ src/
│  │  └─ nta_backend/
│  │     ├─ core/
│  │     │  ├─ config.py
│  │     │  ├─ db.py
│  │     │  ├─ redis.py
│  │     │  ├─ temporal.py
│  │     │  ├─ s3.py
│  │     │  └─ security.py
│  │     ├─ models/
│  │     ├─ schemas/
│  │     ├─ repositories/
│  │     ├─ services/
│  │     ├─ api/
│  │     │  ├─ deps.py
│  │     │  ├─ middleware.py
│  │     │  └─ routers/
│  │     ├─ workflows/
│  │     ├─ activities/
│  │     ├─ integrations/
│  │     ├─ events/
│  │     └─ telemetry/
│  ├─ migrations/
│  ├─ tests/
│  │  ├─ unit/
│  │  ├─ integration/
│  │  └─ e2e/
│  ├─ pyproject.toml
│  └─ alembic.ini
│
├─ infra/
│  ├─ docker/
│  │  ├─ postgres/
│  │  ├─ redis/
│  │  ├─ temporal/
│  │  └─ rustfs/
│  ├─ temporal/
│  │  ├─ dynamicconfig/
│  │  └─ namespaces/
│  ├─ scripts/
│  │  ├─ init-buckets.sh
│  │  ├─ init-db.sql
│  │  └─ create-temporal-namespace.sh
│  ├─ compose/
│  │  ├─ docker-compose.dev.yml
│  │  └─ .env.example
│  └─ README.md
│
├─ docs/
├─ Makefile
├─ .editorconfig
├─ .env.example
└─ README.md
```

---

## 3. 三层职责

### frontend

职责：

- 控制台页面
- 交互组件
- 表单和表格
- 首屏数据获取
- SSE / WebSocket 前端接入
- 上传直传对象存储

边界：

- 不直接处理长任务编排
- 不中转大文件
- 不做复杂权限决策，权限判断以后端为准

### backend

职责：

- 业务 API
- 鉴权
- 元数据读写
- 签名上传 / 下载链接
- Temporal workflow 启动
- 日志聚合与状态流
- 使用量写入与读取

边界：

- API 进程不执行重 CPU / 重 IO 的长任务
- Temporal Worker 与 API 分离部署

### infra

职责：

- 本地开发依赖
- 初始化脚本
- Docker Compose
- Temporal / RustFS / Postgres / Redis 配置

边界：

- `infra` 只放依赖和启动编排
- 不把应用代码 Docker 化作为第一优先级
- 本地开发先保证“应用进程本地跑，依赖 Docker 跑”

---

## 4. 后端服务拆分

### A. API 服务

建议框架：

- `FastAPI`
- `Pydantic v2`
- `SQLAlchemy 2.0`

主要职责：

- CRUD API
- 详情页聚合 API
- 登录态 / API Key / 项目鉴权
- 生成上传 URL
- 启动 Temporal Workflow
- SSE 日志流
- WebSocket 试玩会话

### B. Worker 服务

建议依赖：

- `Temporal Python SDK`

主要职责：

- 数据集导入
- 数据集版本处理
- 评测任务执行
- 批量推理触发
- 用量聚合
- 导出报告
- 清理临时文件

### C. 是否继续拆服务

第一阶段不建议拆成很多独立服务。  
推荐先按 **领域模块化单体 + 独立 Worker**。

什么时候再拆：

- 评测量特别大
- 批量推理和普通 CRUD 明显争抢资源
- 不同团队分别维护 Dataset / Eval / Endpoint

再拆时优先拆：

- `evaluation`
- `batch-inference`
- `usage-billing`

---

## 5. Docker 化 infra 组件

建议放进 `docker-compose.dev.yml` 的组件：

- `postgres`
- `redis`
- `temporal`
- `temporal-ui`
- `rustfs`

可选：

- `adminer` 或 `pgadmin`
- `redisinsight`
- `mailpit`

### 推荐端口

- `postgres: 5432`
- `redis: 6379`
- `temporal-frontend: 7233`
- `temporal-ui: 8088`
- `rustfs/s3: 9001`

### 本地开发启动方式

```bash
make infra-up
make backend-dev
make frontend-dev
```

也就是说：

- `infra` 组件走 Docker
- `frontend/backend` 本地开发模式启动
- `backend-dev` 会同时拉起 API 和 Worker，并让 Worker 跟随 Python 代码变更自动重启

这比把所有应用也塞进 Docker 更适合调试。

---

## 6. 前后端通信设计

### REST

用在：

- 列表
- 详情
- 创建 / 编辑 / 删除
- 项目配置
- API Key
- 配额
- 上传凭证

### SSE

优先用在：

- 评测任务进度
- 批量推理进度
- 任务日志流
- 导入任务状态
- 详情页状态追踪

原因：

- 这些大多是单向流
- SSE 比 WebSocket 更简单
- 对控制台详情页非常合适

### WebSocket

只用在：

- Prompt / 体验中心实时对话
- 需要双向消息的调试台
- 长连接交互会话

不要把普通任务进度也全做成 WebSocket。

---

## 7. 对象存储设计

推荐策略：

- 所有大文件直接进 S3 / RustFS
- 前端拿签名 URL 直传
- 后端只存对象 key 和元数据

建议桶划分：

- `dataset-raw`
- `dataset-processed`
- `eval-artifacts`
- `batch-artifacts`
- `exports`
- `tmp`

对象 key 规范：

```text
projects/{project_id}/datasets/{dataset_id}/versions/{version_id}/source/{filename}
projects/{project_id}/eval-jobs/{job_id}/input/{filename}
projects/{project_id}/eval-jobs/{job_id}/output/{filename}
projects/{project_id}/batch-jobs/{job_id}/result/{filename}
```

---

## 8. 数据库设计原则

### 统一原则

- 大部分核心表都带 `project_id`
- 主键统一 `uuid`
- 时间统一：
  - `created_at`
  - `updated_at`
- 任务表统一：
  - `status`
  - `error_code`
  - `error_message`
- 可变结构字段优先 `jsonb`

### 鉴权与项目域

#### `users`

- `id`
- `email`
- `name`
- `avatar_url`
- `status`
- `created_at`

#### `projects`

- `id`
- `name`
- `code`
- `description`
- `status`
- `created_by`
- `created_at`

#### `project_members`

- `id`
- `project_id`
- `user_id`
- `role`
- `created_at`

#### `api_keys`

- `id`
- `project_id`
- `name`
- `key_prefix`
- `key_hash`
- `status`
- `last_used_at`
- `created_by`
- `created_at`

### 数据集域

#### `datasets`

- `id`
- `project_id`
- `name`
- `description`
- `purpose`
- `format`
- `status`
- `latest_version_id`
- `created_by`
- `created_at`

#### `dataset_versions`

- `id`
- `dataset_id`
- `version`
- `source_type`
- `object_key`
- `file_size`
- `record_count`
- `status`
- `import_job_id`
- `created_by`
- `created_at`

#### `dataset_files`

- `id`
- `dataset_version_id`
- `file_name`
- `object_key`
- `mime_type`
- `size_bytes`
- `etag`
- `created_at`

### 模型与接入点域

#### `models`

- `id`
- `project_id`
- `name`
- `vendor`
- `source`
- `base_model`
- `category`
- `description`
- `status`
- `created_by`
- `created_at`

#### `endpoints`

- `id`
- `project_id`
- `name`
- `endpoint_type`
- `model_id`
- `purchase_type`
- `status`
- `config_json`
- `created_by`
- `created_at`

### 评测与批量任务域

#### `eval_jobs`

- `id`
- `project_id`
- `name`
- `description`
- `status`
- `model_source`
- `model_id`
- `inference_mode`
- `eval_method`
- `criteria_text`
- `dataset_version_id`
- `temporal_workflow_id`
- `batch_job_id`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`

#### `eval_job_metrics`

- `id`
- `eval_job_id`
- `metric_name`
- `metric_value`
- `metric_unit`
- `extra_json`
- `created_at`

#### `batch_jobs`

- `id`
- `project_id`
- `name`
- `description`
- `status`
- `endpoint_id`
- `input_object_key`
- `output_object_key`
- `temporal_workflow_id`
- `progress_total`
- `progress_done`
- `created_by`
- `created_at`
- `started_at`
- `finished_at`

#### `job_logs`

- `id`
- `project_id`
- `job_type`
- `job_id`
- `level`
- `message`
- `payload_json`
- `logged_at`

### 配额与使用量域

#### `quota_rules`

- `id`
- `project_id`
- `resource_type`
- `resource_code`
- `account_quota`
- `shared_ratio`
- `exclusive_ratio`
- `updated_by`
- `updated_at`

#### `usage_events`

- `id`
- `project_id`
- `resource_type`
- `resource_id`
- `model_code`
- `input_tokens`
- `output_tokens`
- `request_count`
- `occurred_at`

#### `usage_daily_agg`

- `id`
- `project_id`
- `date`
- `model_code`
- `endpoint_id`
- `input_tokens`
- `output_tokens`
- `request_count`

### 安全与网络域

#### `security_events`

- `id`
- `project_id`
- `endpoint_id`
- `risk_type`
- `severity`
- `count`
- `event_at`

#### `vpc_bindings`

- `id`
- `project_id`
- `vpc_id`
- `subnet_id`
- `private_link_service_id`
- `status`
- `created_at`

---

## 9. Temporal 任务设计

### Workflow 划分建议

#### `dataset_import_workflow`

步骤：

1. 校验对象是否存在
2. 解析文件元数据
3. 执行格式校验
4. 写入记录数 / 状态
5. 产生日志

#### `eval_job_workflow`

步骤：

1. 校验模型和评测集
2. 生成批量推理子任务
3. 等待批量推理完成
4. 拉取输出结果
5. 执行评测
6. 写入指标
7. 归档结果

#### `batch_inference_workflow`

步骤：

1. 校验输入文件
2. 切分任务
3. 调用模型服务
4. 合并结果
5. 写入对象存储
6. 更新状态

#### `usage_aggregation_workflow`

步骤：

1. 扫描 usage events
2. 聚合到日表
3. 刷新缓存

### Temporal 最重要的实践

- Workflow 只做编排
- 重 IO 放 Activity
- 每个 Activity 做幂等
- 任务状态写库要可重试
- 外部调用要带超时和 retry policy

---

## 10. API 路由分组建议

```text
/api/v1/auth/*
/api/v1/projects/*
/api/v1/api-keys/*
/api/v1/datasets/*
/api/v1/dataset-versions/*
/api/v1/models/*
/api/v1/endpoints/*
/api/v1/batch-jobs/*
/api/v1/eval-jobs/*
/api/v1/usage/*
/api/v1/quotas/*
/api/v1/security/*
/api/v1/network/*
/api/v1/uploads/*
/api/v1/streams/*
```

SSE 路由建议：

```text
/api/v1/streams/eval-jobs/{job_id}
/api/v1/streams/batch-jobs/{job_id}
/api/v1/streams/job-logs/{job_type}/{job_id}
```

WebSocket 路由建议：

```text
/ws/playground/{session_id}
/ws/promptpilot/{session_id}
```

---

## 11. 本地开发最佳实践

### 不推荐

- 一开始拆很多 Python 微服务
- API 服务里直接跑长任务
- 文件通过 API 中转
- 所有实时能力都强行做 WebSocket
- 前后端和 infra 全部都塞 Docker 做日常开发

### 推荐

- `infra` 用 Docker Compose
- `frontend/backend` 本地热更新
- Worker 单独进程
- SSE 优先
- 直传对象存储
- 数据库只存元数据

---

## 12. 建议的第一阶段交付

第一阶段只做这些就够：

- `frontend`
- `backend/apps/api`
- `backend/apps/worker`
- `infra/docker-compose.dev.yml`
- 核心表：
  - `projects`
  - `project_members`
  - `api_keys`
  - `datasets`
  - `dataset_versions`
  - `models`
  - `endpoints`
  - `eval_jobs`
  - `batch_jobs`
  - `job_logs`
  - `usage_daily_agg`

等这些跑稳，再继续补：

- 内容安全
- 网络配置
- 更细粒度权限
- 账单与定价
- 更复杂的应用实验室

---

## 13. 结论

对你这个项目，最合理的单仓形态是：

- `frontend`：Next.js + shadcn/ui
- `backend`：FastAPI API + Temporal Worker
- `infra`：Postgres / Redis / Temporal / RustFS 走 Docker Compose

不要一开始过度微服务化。  
先做成 **模块化单体 + 独立 Worker + Docker 化基础设施**，这是最接近业界最佳实践、同时又能真正落地的一版。

---

## 14. 参考

- [Next.js App Router](https://nextjs.org/docs/app)
- [Next.js Fetching Data](https://nextjs.org/docs/app/getting-started/fetching-data)
- [shadcn/ui](https://ui.shadcn.com/docs)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/latest/)
- [SQLAlchemy](https://docs.sqlalchemy.org/20/intro.html)
- [Temporal Python Guide](https://docs.temporal.io/develop/python)
- [Temporal Python API](https://python.temporal.io/)
