# ModelForge

训练、推理、评测一体化的模型工程平台。

## 仓库结构

- `frontend`: Next.js 控制台
- `backend`: FastAPI API 和 Temporal Worker
- `infra`: PostgreSQL、Redis、Temporal、RustFS 的 Docker Compose

## 本地启动

1. 启动基础设施

```bash
make infra.up
```

2. 执行数据库迁移

```bash
make backend.migrate
```

3. 启动后端开发进程

```bash
make backend.dev
```

4. 启动前端

```bash
make frontend.dev
```

也可以直接同时启动前后端：

```bash
make dev
```

5. 打开控制台

```bash
open http://localhost:8081
```

`make backend.dev` 会同时启动 API 和 Worker。`make dev` 会在此基础上再启动前端。API 修改后由 `uvicorn --reload` 热更新，Worker 修改 `backend/apps`、`backend/src`、`backend/migrations` 下的 Python 文件后会自动重启。

后端进程会额外把运行日志写入 `backend/logs/api.log` 和 `backend/logs/worker.log`，可通过根目录 `.env` 里的 `LOG_DIR`、`LOG_LEVEL`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT` 调整。

如果只想单独启动一侧，仍然可以使用：

```bash
make backend.api
make backend.worker
```

## 生产部署

1. 复制环境变量模板

```bash
cp infra/compose/.env.prod.example infra/compose/.env.prod
```

2. 修改 `infra/compose/.env.prod`

至少需要设置这些值：

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `CORS_ORIGINS`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`

3. 校验 Compose 配置

```bash
make prod.config PROD_ENV_FILE=infra/compose/.env.prod
```

4. 全新环境首次部署

```bash
make prod.release-with-migrate PROD_ENV_FILE=infra/compose/.env.prod
```

5. 已有环境发布新版本

```bash
make prod.release PROD_ENV_FILE=infra/compose/.env.prod
```

6. 如果本次发布包含数据库 schema 变更，再执行迁移

```bash
make prod.migrate PROD_ENV_FILE=infra/compose/.env.prod
```


> 兼容说明：旧命令（如 `make infra-up`、`make backend-dev`）仍可用，推荐逐步迁移到新的命名空间风格目标（如 `make infra.up`、`make backend.dev`）。

## 常用命令

查看生产环境日志：

```bash
make prod.logs PROD_ENV_FILE=infra/compose/.env.prod
```

停止生产环境：

```bash
make prod.down PROD_ENV_FILE=infra/compose/.env.prod
```
