# ModelForge

训练、推理、评测一体化的模型工程平台。

## 仓库结构

- `frontend`: Next.js 控制台
- `backend`: FastAPI API 和 Temporal Worker
- `infra`: PostgreSQL、Redis、Temporal、RustFS 的 Docker Compose

## 本地启动

本地开发和部署环境统一使用仓库根目录 `.env`。如果本地还没有这个文件，先从 `.env.example` 复制一份再改。

默认约定是：本地对象存储走 RustFS，线上对象存储走腾讯云 COS。也就是说，代码层统一使用同一套 `S3_*` 配置键，差异只放在环境文件里。

1. 启动基础设施

```bash
make infra.up
```

默认会启动本地开发需要的基础依赖：`postgres / temporal / temporal-ui / rustfs / gateway`，以及对应的初始化任务。

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
cp .env.example .env
```

2. 修改根目录 `.env`

至少需要设置这些值：

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `CORS_ORIGINS`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`

如果生产环境改用托管资源：

- `DATABASE_URL` 改成外部 PostgreSQL 连接串
- COS 继续沿用现有 S3 兼容接入，只需要把
  - `S3_ENDPOINT_URL`
  - `S3_BROWSER_ENDPOINT_URL`
  - `S3_REGION`
  - `S3_ACCESS_KEY_ID`
  - `S3_SECRET_ACCESS_KEY`
  - `S3_BUCKET_MAIN`
  - `S3_ADDRESSING_STYLE`
  - `S3_ROOT_PREFIX`
  - `NEXT_PUBLIC_OBJECT_STORE_ROOT_PREFIX`
    配成 COS；新建 COS bucket 推荐把 `S3_ADDRESSING_STYLE` 设为 `virtual`，并约定本地开发使用 `nta-dev`、线上部署使用 `nta-prod`

本地开发推荐保持 `.env` 里的 RustFS 默认值：

- `S3_ENDPOINT_URL=http://127.0.0.1:8081`
- `S3_BROWSER_ENDPOINT_URL=http://127.0.0.1:8081`
- `S3_REGION=us-east-1`
- `S3_ADDRESSING_STYLE=path`
- `S3_ACCESS_KEY_ID=rustfsadmin`
- `S3_SECRET_ACCESS_KEY=ChangeMe123!`
- `S3_BUCKET_MAIN=nta-default`
- `S3_DIRECT_UPLOAD_MODE=presigned`

线上部署则把同一份 `.env` 里的对象存储配置改成 COS：

- `S3_ENDPOINT_URL=https://cos-internal.<region>.tencentcos.cn`
- `S3_BROWSER_ENDPOINT_URL=https://cos-internal.<region>.tencentcos.cn`
- `S3_ADDRESSING_STYLE=virtual`
- `S3_DIRECT_UPLOAD_MODE=cos-sts`

注意：当前生产 compose 里的 Temporal 仍然默认依赖本地 `postgres` 服务作为它自己的元数据库；如果你想把这部分也切到托管 PostgreSQL，需要再单独调整 Temporal 的底层数据库连接。

3. 校验 Compose 配置

```bash
make prod.config
```

4. 全新环境首次部署

```bash
make prod.release-with-migrate
```

5. 已有环境发布新版本

```bash
make prod.release
```

6. 如果本次发布包含数据库 schema 变更，再执行迁移

```bash
make prod.migrate
```


> 兼容说明：旧命令（如 `make infra-up`、`make backend-dev`）仍可用，推荐逐步迁移到新的命名空间风格目标（如 `make infra.up`、`make backend.dev`）。

## 常用命令

查看生产环境日志：

```bash
make prod.logs
```

停止生产环境：

```bash
make prod.down
```
