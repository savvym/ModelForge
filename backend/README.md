# backend

后端采用 `FastAPI + SQLAlchemy 2.0 + Temporal Python SDK`。

## 目录

- `apps/api`：FastAPI 入口
- `apps/worker`：Temporal Worker 入口
- `src/nta_backend/core`：配置、数据库、Redis、S3、Temporal 接入
- `src/nta_backend/models`：SQLAlchemy 模型
- `src/nta_backend/schemas`：Pydantic schema
- `src/nta_backend/api/routers`：REST / SSE / WebSocket 路由
- `src/nta_backend/workflows`：Temporal workflows
- `src/nta_backend/activities`：Temporal activities
- `migrations`：Alembic skeleton

## 关键路由

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/projects`
- `GET /api/v1/datasets`
- `POST /api/v1/uploads/presign`
- `GET /api/v1/eval-jobs`
- `POST /api/v1/eval-jobs`
- `GET /api/v1/streams/eval-jobs/{job_id}`
- `WS /ws/playground/{session_id}`

## 开发

```bash
uv sync
uv run alembic upgrade head
```

推荐从仓库根目录启动：

```bash
make backend-dev
```

这会同时启动 API 和 Worker。API 继续使用 `uvicorn --reload`，Worker 通过 `uv run python -m apps.worker.dev` 监听 `backend/apps`、`backend/src`、`backend/migrations` 下的 Python 变更并自动重启。

本地开发也保持和生产一致的双配置模式：`S3_ENDPOINT_URL` 给后端/Worker 使用，`S3_BROWSER_ENDPOINT_URL` 给浏览器直传使用。开发环境默认都指向 dev gateway `http://127.0.0.1:8081`。

如果只需要单独调试某一侧：

```bash
make api-dev
make worker-dev
```

## 日志文件

- API 日志默认写入 `backend/logs/api.log`
- Worker 日志默认写入 `backend/logs/worker.log`
- 可通过 `LOG_DIR`、`LOG_LEVEL`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` 调整目录、级别和轮转策略
