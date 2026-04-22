# backend

后端采用 `FastAPI + SQLAlchemy 2.0 + Temporal Python SDK`。

## 目录

- `apps/api`：FastAPI 入口
- `apps/worker`：Temporal Worker 入口
- `src/nta_backend/core`：配置、数据库、S3、Temporal 接入
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
- `GET /api/v2/evaluation-runs`
- `POST /api/v2/evaluation-runs`
- `WS /ws/playground/{session_id}`

## 开发

```bash
PYTHONPATH=src uv run python -m alembic upgrade head
```

推荐从仓库根目录启动：

```bash
make backend-dev
```

这会同时启动 API 和 Worker。API 继续使用 `uvicorn --reload`，Worker 通过 `uv run python -m apps.worker.dev` 监听 `backend/apps`、`backend/src`、`backend/migrations` 下的 Python 变更并自动重启。

对象存储统一使用一套 `S3_*` 配置键：`S3_ENDPOINT_URL` 给后端/Worker 使用，`S3_BROWSER_ENDPOINT_URL` 给浏览器直传使用。

推荐约定：

- 本地开发默认用 RustFS：`S3_ENDPOINT_URL=http://127.0.0.1:8081`、`S3_BROWSER_ENDPOINT_URL=http://127.0.0.1:8081`
- 线上部署改用腾讯云 COS：`S3_ENDPOINT_URL=https://cos-internal.<region>.tencentcos.cn`、`S3_BROWSER_ENDPOINT_URL=https://cos-internal.<region>.tencentcos.cn`

接外部对象存储时，继续使用这一套 `S3_*` 配置即可；如果对象存储换成腾讯云 COS，建议同时设置：

- `S3_ADDRESSING_STYLE=virtual`
- `S3_ROOT_PREFIX=nta-dev` 或 `nta-prod`

如果对象存储是本地 RustFS，推荐设置：

- `S3_ADDRESSING_STYLE=path`
- `S3_DIRECT_UPLOAD_MODE=presigned`

这样本地开发内容会写入 `nta-dev/...`，生产内容会写入 `nta-prod/...`。

如果只需要单独调试某一侧：

```bash
make api-dev
make worker-dev
```

## 日志文件

- API 日志默认写入 `backend/logs/api.log`
- Worker 日志默认写入 `backend/logs/worker.log`
- 可通过 `LOG_DIR`、`LOG_LEVEL`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` 调整目录、级别和轮转策略
