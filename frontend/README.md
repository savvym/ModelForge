# frontend

前端采用 `Next.js App Router + shadcn/ui + Tailwind CSS`。

## 目录

- `app/(console)`：控制台路由
- `components/ui`：基础 UI 组件
- `components/console`：控制台壳层与页面容器
- `features/*/api.ts`：按领域拆分的数据访问
- `lib/api-client`：HTTP client
- `lib/sse`：SSE 接入
- `lib/websocket`：WebSocket 接入
- `types/api.ts`：前后端 DTO 对齐

## 已接入的页面

- `/overview` -> `GET /api/v1/projects`
- `/dataset` -> `GET /api/v1/datasets`
- `/model/eval` -> `GET /api/v2/evaluation-runs` + `GET /api/v2/evaluation-catalog`

## 开发

```bash
pnpm install
pnpm dev
pnpm typecheck
```

浏览器侧本地调试默认通过 dev gateway 访问，入口使用 `http://localhost:8081`。即使单独启动了 `pnpm dev`，前端默认也会把 API / SSE / WebSocket 请求转到 `8081`，避免绕过本地 nginx。
