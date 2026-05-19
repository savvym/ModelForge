# 数据湖（Data Lake）

数据湖以 **Git 仓库为单位** 管理原始资产。每个仓库可以是一个 md + 图片的目录、一个 URL 解析结果，或单个文件；底层用 [Gitea](https://gitea.com) 作为 Git server，大文件走 Git LFS。该实现替换了旧的 `lake_batches` / `lake_assets` + 对象存储方案。

## 架构

```
┌─────────────┐     /data-lake/repos       ┌──────────────┐
│   Browser   │ ─────────────────────────▶ │ FastAPI BE   │
└─────────────┘                            │ (lake_repos) │
                                           └───────┬──────┘
                                                   │  httpx + token
                                                   ▼
                                           ┌──────────────┐
                                           │   Gitea      │  ─── PG (gitea db)
                                           │ (compose)    │  ─── LFS / local disk
                                           └──────────────┘
```

- 一个 **platform project** 对应一个 **Gitea organization**，命名 `proj-<project.code>`（截断到 40 字符）。
- 一个 **LakeRepo** 行 ↔ 一个 Gitea repo。PG 只存元数据（名称、显示名、描述、默认分支、可见性、status），Gitea 是文件/提交历史的真相之源。
- 所有 Gitea API 调用都用 **单一 admin token**；commit 的 `author` 通过 API body 字段切换为当前平台用户（不要求 Gitea 侧存在对应用户）。

## 关键文件

| 模块 | 文件 |
|------|------|
| Async Gitea API client | `backend/src/nta_backend/core/gitea_client.py` |
| ORM model | `backend/src/nta_backend/models/lake_repo.py` |
| Pydantic schemas | `backend/src/nta_backend/schemas/lake_repo.py` |
| Business service | `backend/src/nta_backend/services/lake_repo_service.py` |
| HTTP router (`/data-lake/...`) | `backend/src/nta_backend/api/routers/lake_repos.py` |
| Schema migration (head = 0014) | `backend/migrations/versions/0014_data_lake_repos.py` |
| Frontend feature folder | `frontend/features/data-lake/` |
| Frontend routes | `frontend/app/(console)/data-lake/` |

## 启动

1. 拷贝 env：`cp .env.example .env`，确认 `GITEA_*` 字段。
2. 起 infra：`make infra.up`（会一并起 Gitea）。
3. 首次部署需 bootstrap Gitea admin + token：`make gitea.bootstrap`。脚本会把 `GITEA_ADMIN_TOKEN` 写回 `.env`。
4. 跑迁移：`make backend.migrate`。
5. 启后端/前端：`make backend.dev` + `make frontend.dev`。

## 环境变量

| 变量 | 说明 |
|------|------|
| `GITEA_HTTP_PORT` | Gitea web/api 端口（默认 3001） |
| `GITEA_SSH_PORT` | Gitea ssh 端口（默认 2222） |
| `GITEA_INTERNAL_URL` | 后端访问 Gitea 的地址（compose 内网，默认 `http://gitea:3000`） |
| `GITEA_EXTERNAL_URL` | 浏览器/克隆使用的 URL（默认 `http://127.0.0.1:3001`） |
| `GITEA_ADMIN_USER` / `GITEA_ADMIN_PASSWORD` / `GITEA_ADMIN_EMAIL` | bootstrap 用的 admin |
| `GITEA_ADMIN_TOKEN` | 由 bootstrap 写入；后端读取 |
| `GITEA_DEFAULT_BRANCH` | 新仓库默认分支（main） |
| `GITEA_ORG_PREFIX` | org 名前缀（默认 `proj-`） |
| `GITEA_SECRET_KEY` / `GITEA_INTERNAL_TOKEN` / `GITEA_LFS_JWT_SECRET` | Gitea 内部用于会话、JWT、LFS 的密钥；dev 环境用占位值即可 |

## API 端点（prefix `/api/v1/data-lake`）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/repos?query=&page=&page_size=` | 列出当前项目下的仓库 |
| POST | `/repos` | 创建仓库（同步在 Gitea 创建 org+repo） |
| GET | `/repos/{id}` | 仓库详情（含 web_url / clone_url / 最近 commit） |
| PATCH | `/repos/{id}` | 修改展示名、描述、默认分支 |
| DELETE | `/repos/{id}` | 删除（同步删 Gitea 仓库） |
| GET | `/repos/{id}/branches` | 分支列表 |
| GET | `/repos/{id}/tree/{ref}?path=` | 目录树 |
| GET | `/repos/{id}/file/{ref}?path=` | 单个文件（含内联文本/二进制 download URL） |
| GET | `/repos/{id}/raw/{ref}/{path}` | 后端代理下载（用于 `<img>` 等） |
| POST | `/repos/{id}/commits` | 单次 commit 批量上传 |
| GET | `/repos/{id}/commits/{ref}` | commit 列表 |

## 失败语义

| 场景 | 行为 |
|------|------|
| Gitea 不可达，列表请求 | DB-only，返回 200 |
| Gitea 不可达，详情请求 | 503，前端展示 alert |
| Gitea 不可达，写操作 | 502，DB 不污染（如 create 留 `status='provisioning'`，由 reconcile 兜底） |
| Create repo 时 Gitea 422（已存在） | 视为成功，复用 |
| Delete repo 时 Gitea 404 | 视为成功 |
| Project 创建后 Gitea 建 org 失败 | 不回滚项目，记 warning，等 reconcile |

## LFS / 大文件

- PoC 阶段 LFS 使用 Gitea 本地盘（docker volume `gitea_data`）；阈值默认 25 MiB / 单次 commit（前端校验）。
- 后端 `GET /file/{ref}` 对超过 `GITEA_LAKE_INLINE_MAX_BYTES`（默认 1 MiB）或 LFS pointer 的文件，返回代理 URL 而非内联内容。
- 迁到 COS：把 `GITEA__lfs__STORAGE_TYPE=minio` + S3 兼容参数填入 compose 即可（不改 Git 历史）。

## Reconcile

如果 Gitea 与平台 DB 出现偏差（例如 Gitea 重新部署后丢失数据），可以：

1. 平台侧手动通过 `LakeRepoService.reconcile_org_for_project` / `reconcile_delete_org` 重建。
2. 或在 `/api/v1/data-lake/repos` 创建调用时让 `create_org` 走 422-idempotent 路径自然恢复。

## 测试

- `backend/tests/test_gitea_client.py`：mocked httpx，覆盖 token header、create_org idempotency、批量 commit 的 create/update 路径切换、5xx vs 4xx、网络错误、X-Total-Count 解析等。
- 业务级 e2e：先 `make infra.up && make gitea.bootstrap && make backend.migrate`，再走 Plan 文件中的 8 步验证清单。
