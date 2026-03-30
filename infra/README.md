# infra

基础设施层通过 Docker Compose 启动本地开发依赖。

## 组件

- `postgres`：主数据库
- `redis`：缓存 / SSE fan-out / 限流
- `temporal`：workflow backend
- `temporal-ui`：workflow 观察界面
- `temporal-admin-tools`：namespace 管理
- `rustfs`：S3 兼容对象存储
- `rustfs-init`：创建开发桶
- `temporal-namespace-init`：注册开发 namespace
- `gateway`：开发环境统一入口，代理 `frontend / api`

## 目录

- `compose/docker-compose.dev.yml`：开发环境 compose
- `compose/.env.example`：compose 环境变量模板
- `scripts/init-db.sql`：数据库初始化
- `scripts/init-buckets.sh`：对象存储桶初始化
- `scripts/create-temporal-namespace.sh`：Temporal namespace 初始化
- `temporal/dynamicconfig/development-sql.yaml`：Temporal 动态配置

## 启动

```bash
make infra-up
```

开发环境推荐入口：

- `http://localhost:8081/`

`make infra-up` 现在会在 `docker compose up -d` 之后继续校验：

- `gateway` 容器里的 nginx 配置能通过 `nginx -t`
- `http://127.0.0.1:8081/nta-default` 已经由 dev gateway 代理到对象存储

如果这一步失败，最常见的原因是宿主机上已有别的进程占用了 `:8081`，需要先释放该端口后再重新执行 `make infra-up`。

## 生产部署骨架

生产环境新增了这些文件：

- `compose/docker-compose.prod.yml`
- `compose/.env.prod.example`
- `../nginx/default.conf`
- `../../frontend/Dockerfile`
- `../../backend/Dockerfile.api`
- `../../backend/Dockerfile.worker`
- `../../scripts/release.sh`

推荐做法：

1. 在服务器上复制 `compose/.env.prod.example` 为 `compose/.env.prod`
2. 替换所有默认密码、密钥和域名
3. 执行

```bash
docker compose --env-file compose/.env.prod -f compose/docker-compose.prod.yml config
../../scripts/release.sh
```

生产 compose 默认通过 `nginx` 暴露两个入口：

- `/` -> `frontend`
- `/api/*` -> `api`
- `/ws/*` -> `api`

同时把 `postgres`、`redis`、`temporal`、`rustfs` 收在容器内网络，避免直接暴露到公网。
