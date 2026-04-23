# Infer Agent + 声明式控制面设计（姊妹方案）

> NTA Platform - 模型部署控制面备选方案
> 版本：0.1 | 2026-04-21
> 关联文档：`model-deployment-control-plane.zh-CN.md`（主方案 0.1）

---

## 0. 本文档的定位

本文档不是对主方案的替代，而是一份**视角互补**的姊妹方案：

- **主方案**聚焦"系统怎么组织"：训练产物登记 + 单 active 模型部署 + 部署后评测。
- **本方案**聚焦"Infer Agent 怎么实现"：声明式 API + Reconciler loop + generation 乐观锁 + 独立进程语义。

两份文档的关系：

| 维度 | 主方案 (`model-deployment-control-plane.zh-CN.md`) | 本方案 |
|------|------|------|
| 数据模型、API 表单、Phase 规划 | 以主方案为准 | 不重复 |
| 单模型部署链路、训练产物视角 | 以主方案为准 | 不重复 |
| Infer Agent 内部架构、Reconciler、通信模型 | 主方案留白 | 本文详述 |
| 声明式 API 设计 | 主方案是命令式 | 本文给出声明式变体 |
| 独立 Infer Agent vs 复用 probe | 主方案未展开对比 | 本文明确结论 |

建议阅读顺序：先读主方案了解全景，再读本方案补充 Infer Agent 实现细节。

---

## 目录

1. [核心设计原则](#1-核心设计原则)
2. [为什么是独立 Infer Agent，不复用 probe](#2-为什么是独立-infer-agent不复用-probe)
3. [Infer Agent 进程内部架构](#3-infer-agent-进程内部架构)
4. [声明式 API 设计](#4-声明式-api-设计)
5. [Reconciler 状态机](#5-reconciler-状态机)
6. [Infer Agent 与控制面通信模型](#6-infer-agent-与控制面通信模型)
7. [Infer Agent 注册、升级、运维](#7-infer-agent-注册升级运维)
8. [安全补充](#8-安全补充)
9. [与主方案的融合建议](#9-与主方案的融合建议)
10. [代码布局与工程约定](#10-代码布局与工程约定)
11. [开放问题](#11-开放问题)

---

## 1. 核心设计原则

本方案围绕四条原则展开：

1. **声明式优先**：控制面告诉 Infer Agent "想要什么"，不是"做什么"。Infer Agent 内部 Reconciler 负责收敛。
2. **期望态持久化**：Infer Agent 本地 SQLite 持久化 desired state。重启后能自动恢复。
3. **最终一致性**：任何阶段失败都能被下一次 reconcile 重试修复，不依赖外部重试。
4. **职责单一**：Infer Agent 只管本机 vLLM 生命周期和模型缓存。鉴权、调度、计费在控制面。

四条原则的共同目标：**让 Infer Agent 成为一个可预测、可重启、可观测的状态机**，而不是"远端命令执行器"。

---

## 2. 为什么是独立 Infer Agent，不复用 probe

`probe` 已经具备注册、心跳、任务派发能力，看上去可以直接扩展。本方案不复用，理由如下。

### 2.1 语义差异

| 维度 | probe | infer-agent |
|------|-------|------|
| 任务形态 | 短任务，执行完即完成 | 长驻服务生命周期管理 |
| 状态模型 | `queued → running → done` | `desired ≠ observed` 持续 reconcile |
| 失败处理 | 任务标记 failed，等下次调度 | 需要回滚、重启、保留 endpoint 可用性 |
| 调度粒度 | 每次一个 evalscope 进程 | 当前一个 vLLM 容器 + 期望一个 |
| 客户端关系 | pull task 模式 | 声明式 REST（可 push） |

将"长驻服务管理"塞进"短任务执行器"，会让 probe 状态机越来越复杂。

### 2.2 运维独立性

- Infer Agent 升级不影响评测 probe，反之亦然。
- Infer Agent 挂掉时，评测 probe 仍能跑 API 评测任务。
- Infer Agent 的 Docker socket / GPU 管理权限不与 probe 共享，攻击面更小。

### 2.3 同机共存

Infer Agent 和 probe 可部署在同一台 H20，互不干涉：

```
H20
├── probe            (评测任务执行)
├── infer-agent      (vLLM 生命周期管理)
└── vllm container   (Infer Agent 启动并管理)
```

甚至 probe 可以直接调用本机 vLLM endpoint 做同机评测，成为 benchmarking 利器。

### 2.4 结论

**独立 Infer Agent 更清晰**。代价是多一个 systemd service 和一套部署脚本，但在你项目长期演进中值得。

以下文档中 `Infer Agent` 指推理节点上的部署执行器；服务名统一使用 `infer-agent`。

---

## 3. Infer Agent 进程内部架构

```text
┌────────────────────────────────────────────────────────────┐
│ infer-agent (FastAPI + asyncio)                            │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ API Layer (FastAPI)                                 │   │
│  │   - /v1/deployments/current (PUT/GET/DELETE)        │   │
│  │   - /v1/events (SSE)                                │   │
│  │   - /v1/cache/models (GET/DELETE)                   │   │
│  │   - /v1/health, /v1/metrics                         │   │
│  └───────────────────┬─────────────────────────────────┘   │
│                      │ 只写 desired_state                   │
│                      ▼                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ State Store (SQLite, /var/lib/infer-agent/state.db) │   │
│  │   - desired_state (spec JSON + generation)          │   │
│  │   - observed_state (phase, progress, endpoint)      │   │
│  │   - events (时间线)                                  │   │
│  └───────────────────┬─────────────────────────────────┘   │
│                      │ 读 desired + observed                │
│                      ▼                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Reconciler (asyncio task, tick 2s 或 kick)          │   │
│  │   - 计算 diff                                         │   │
│  │   - 推进状态机                                         │   │
│  │   - 发事件                                            │   │
│  └────┬─────────────┬──────────────┬───────────────────┘   │
│       │             │              │                        │
│       ▼             ▼              ▼                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────────┐    │
│  │ COS      │ │ Docker   │ │ Local Cache              │    │
│  │ Client   │ │ Runtime  │ │ (path + LRU + locks)     │    │
│  │ (STS)    │ │ (vLLM)   │ │                          │    │
│  └──────────┘ └──────────┘ └──────────────────────────┘    │
│       │             │              │                        │
└───────┼─────────────┼──────────────┼───────────────────────┘
        ▼             ▼              ▼
     COS Bucket  nta-vllm 容器  /data/model-cache/
                    :8000
```

### 3.1 模块职责

| 模块 | 职责 | 技术 |
|------|------|------|
| API Layer | 接收声明式请求，只写 desired state；暴露 observed state 和 SSE | FastAPI |
| State Store | 期望态 / 实际态 / 事件持久化 | SQLite (WAL 模式) |
| Reconciler | 计算 diff，推进状态机，发事件 | asyncio |
| COS Client | 从 COS 下载 artifact，校验 sha256，支持断点续传 | boto3 |
| Docker Runtime | 启停 vLLM 容器，收集日志，健康检查 | docker SDK |
| Local Cache | 缓存路径管理，LRU 淘汰，读写锁 | filesystem + SQLite |

### 3.2 为什么 SQLite 而不是 JSON 文件

- **原子写**：避免半写状态
- **并发**：API 和 Reconciler 在不同协程
- **WAL**：读不阻塞写
- **事件时间线**：天然支持追加查询
- **约 0 额外依赖**：Python 标准库自带

### 3.3 为什么 Reconciler 是一等公民

- 单 API handler 做"下载→停旧→启新→等就绪"会导致：
  - handler 超时必须很长（10+ 分钟）
  - Infer Agent 重启后丢状态
  - 并发多次请求难处理
- Reconciler 把 **"推进状态机"和"接收请求"解耦**，API 立刻返回，后台慢慢收敛。
- 这是 Kubernetes 所有 controller 的通用模式。

---

## 4. 声明式 API 设计

与主方案的命令式 API（`activate`, `cancel`, `rollback`）不同，本方案 Infer Agent 的 API 是声明式。控制面可在外层仍保留命令式 API 供人类使用，但**调用到 Infer Agent 这一跳应当声明式**。

### 4.1 核心 Schema

```python
# 共享包 packages/forge-schemas/src/forge_schemas/deployment.py
# backend 和 infer-agent 同时依赖

class ModelSource(BaseModel):
    type: Literal["cos", "local"]
    uri: str                          # "cos://bucket/prefix/" 或 "local:///data/.../sha"
    sha256: str | None                # manifest-level 校验
    manifest_key: str | None          # "manifest.json" 路径

class EngineSpec(BaseModel):
    name: Literal["vllm"] = "vllm"
    image: str                        # "vllm/vllm-openai:v0.6.3"
    served_model_name: str
    tensor_parallel_size: int = 8
    pipeline_parallel_size: int = 1
    gpu_ids: list[int]                # [0,1,2,3,4,5,6,7]
    listen_port: int = 8000
    api_key_ref: str | None           # Infer Agent 从环境变量/文件读取
    extra_args: dict[str, Any] = {}

class DeploymentSpec(BaseModel):
    """控制面 → Infer Agent 的期望状态"""
    deployment_id: UUID
    generation: int                   # 单调递增，每次改 spec 就 +1（乐观锁）
    model_source: ModelSource
    engine: EngineSpec
    desired_phase: Literal["running", "stopped"] = "running"
    smoke_test: SmokeTestSpec | None = None

class DeploymentStatus(BaseModel):
    """Infer Agent → 控制面的实际状态"""
    deployment_id: UUID
    generation: int                   # 对应已处理到哪一代 spec
    phase: Literal[
        "pending",
        "downloading",
        "verifying",
        "stopping_previous",
        "starting",
        "warming",
        "smoke_testing",
        "ready",
        "stopped",
        "error",
    ]
    progress: int                     # 0-100
    endpoint: str | None              # "http://host:8000/v1"
    active_model_name: str | None     # 用于校验是否和 spec 一致
    container_id: str | None
    last_event: str
    error: ErrorDetail | None
    observed_at: datetime
    last_health_ok_at: datetime | None
```

### 4.2 API 列表

| Method | Path | 含义 |
|--------|------|------|
| PUT | `/v1/deployments/current` | 设置期望态（幂等：同 generation no-op；新 generation 覆盖） |
| GET | `/v1/deployments/current` | 读实际态 |
| DELETE | `/v1/deployments/current` | 期望态置为 stopped（不删记录） |
| GET | `/v1/events` | SSE 事件流（断线重连用 `Last-Event-Id`） |
| GET | `/v1/cache/models` | 本地缓存清单 |
| DELETE | `/v1/cache/models/{sha}` | 手动清理（active 的禁止删） |
| GET | `/v1/health` | 存活 + GPU 状态 |
| GET | `/v1/metrics` | Prometheus |

### 4.3 PUT 语义（核心）

```
PUT /v1/deployments/current
Body: DeploymentSpec { generation: N, ... }
```

Infer Agent 行为：

1. 比较请求 `generation` 和本地 `desired.generation`
   - 请求 < 本地：返回 409 `stale_generation`
   - 请求 = 本地：no-op，返回当前 status
   - 请求 > 本地：覆盖 desired，kick reconciler
2. 同步返回 `DeploymentStatus`（可能仍是 pending）
3. 不阻塞等待 ready

### 4.4 与主方案命令式 API 的对齐

主方案的外层命令式 API 保留：

```
POST /api/v2/model-deployments/{id}/activate
POST /api/v2/model-deployments/{id}/cancel
POST /api/v2/model-deployments/{id}/rollback
```

控制面内部的 `deployment_service` 把命令翻译为声明式：

- activate → PUT Infer Agent `desired_phase=running`, `generation=新值`
- cancel → PUT Infer Agent `desired_phase=stopped`, `generation=新值`
- rollback → 读出上一次 generation 的 spec，PUT 到 Infer Agent（generation 更高）

这样人类友好的 API 和声明式下行调用两全。

---

## 5. Reconciler 状态机

### 5.1 状态转移图

```text
                ┌─────────────┐
                │   pending   │  (Infer Agent 刚收到 spec)
                └──────┬──────┘
                       │ cache miss          cache hit
          ┌────────────┴───────────┐         │
          ▼                        ▼         │
    ┌──────────────┐         ┌───────────────┘
    │ downloading  │         │
    └──────┬───────┘         │
           ▼                 ▼
    ┌──────────────┐  ┌───────────────┐
    │  verifying   │─►│stopping_prev  │  (若旧容器存在)
    └──────┬───────┘  └──────┬────────┘
           └────────┬────────┘
                    ▼
              ┌───────────┐
              │ starting  │
              └─────┬─────┘
                    ▼
              ┌───────────┐
              │  warming  │  (等 /health 200)
              └─────┬─────┘
                    ▼
              ┌──────────────┐  可选
              │smoke_testing │
              └─────┬────────┘
                    ▼
              ┌───────────┐
              │   ready   │
              └─────┬─────┘
        desired=stopped│
                    ▼
              ┌───────────┐
              │  stopped  │
              └───────────┘

任意非 ready/stopped 阶段
   → error (保留 spec 和错误详情)
   → 下一轮 reconcile 重新尝试（有重试上限）
```

### 5.2 Reconcile 伪代码

```python
async def reconcile_once():
    desired = state.get_desired()
    if desired is None:
        return

    observed = await observe()  # docker inspect + health check

    # 1. 期望停止
    if desired.desired_phase == "stopped":
        if observed.phase not in ("stopped", "pending"):
            await runtime.stop(observed.container_id)
            state.set_phase("stopped", generation=desired.generation)
        return

    # 2. 已就绪且一致 → 健康兜底
    if (observed.phase == "ready"
            and observed.generation == desired.generation
            and observed.active_model_name == desired.engine.served_model_name):
        if not await runtime.is_healthy():
            state.set_phase("error", error="health_check_failed")
            # 下一次 tick 会重新部署
        return

    # 3. 推进部署（根据当前 observed.phase 决定下一步）
    match observed.phase:
        case "pending" | "error":
            await ensure_cached(desired)
        case "downloading":
            # 下载是 activity，监控进度即可
            pass
        case "verifying":
            await verify_artifact(desired)
        case "stopping_previous":
            await wait_stop(observed.previous_container_id)
            state.set_phase("starting")
        case "starting":
            await runtime.start(desired)
            state.set_phase("warming")
        case "warming":
            if await runtime.is_healthy():
                state.set_phase("smoke_testing" if desired.smoke_test else "ready")
        case "smoke_testing":
            ok = await run_smoke(desired)
            state.set_phase("ready" if ok else "error")
```

### 5.3 Reconcile 触发时机

- **定时**：每 2 秒一次，保证最终一致
- **kick**：API 写入 desired 后立刻唤醒
- **健康检查失败**：observed `is_healthy()` 返回 false 时重新进入 reconcile
- **Infer Agent 启动时**：从 SQLite 恢复 desired，立刻跑一次

### 5.4 失败与重试

- Reconciler 捕获异常后记录到 `events` 表并置 observed.phase=error
- `error_retry_count` 字段限制重试次数（默认 3 次）
- 超过上限后停止自动重试，等人工或新 generation

---

## 6. Infer Agent 与控制面通信模型

### 6.1 通信拓扑

```
Backend (公网域名 or 内网)
    │
    │ ①启动时 Infer Agent 主动注册 (Bootstrap Token)
    │ ②Backend 下发 PUT /v1/deployments/current
    │ ③Infer Agent SSE 回推事件，Backend 订阅
    │ ④Infer Agent 定期心跳 POST /api/v2/infer-agents/{id}/heartbeat
    ▼
Infer Agent (监听内网 :9000)
```

### 6.2 关键决策：下行用 PUSH，上行用 SSE + 心跳

| 方向 | 方式 | 理由 |
|------|------|------|
| Backend → Infer Agent | Backend 主动 PUT Infer Agent | 部署是用户触发，低延迟响应；命令是稀疏事件 |
| Infer Agent → Backend (事件) | Backend 订阅 Infer Agent SSE | 进度事件高频、流式，SSE 天然 |
| Infer Agent → Backend (心跳) | Infer Agent 定期 POST | 低频（30s 一次），用于在线感知 |

**与主方案的差异**：主方案讨论了 pull-based（Infer Agent 轮询 claim task）和 Temporal Worker 两种模式。本方案推荐第三种——**PUSH + SSE**，理由：

- Infer Agent 有公网/内网 endpoint 不算问题（内网 VPC 即可）
- 部署操作延迟敏感，push 比 pull 低 5-10 秒
- 进度事件流式天然适合 SSE
- 不把 Infer Agent 塞进 Temporal worker pool，保持 Infer Agent 独立

### 6.3 SSE 订阅示例

```python
# backend/src/nta_backend/services/deployment_service.py

async def watch_agent_events(agent: InferAgent, deployment_id: UUID):
    client = InferAgentClient(agent)
    async for evt in client.stream_events(deployment_id):
        # 持久化到 model_deployment_events
        await events_repo.insert(deployment_id, evt)
        # 推前端 SSE
        await sse_bus.publish(f"deployment:{deployment_id}", evt)
```

### 6.4 失联处理

- Backend 心跳超时（如 90s 未更新） → 标记 Infer Agent `offline`
- Infer Agent 重启后重新注册 → 心跳恢复后继续订阅 SSE
- **重要**：Infer Agent 重启期间如果状态发生变化（容器崩溃），Infer Agent 下次 reconcile 发现 desired ≠ observed，会自愈

---

## 7. Infer Agent 注册、升级、运维

### 7.1 一键安装

```bash
# 从控制面管理页获取 bootstrap token + backend url，然后在 H20 上执行
curl -sSL https://your-nta.example.com/install/infer-agent.sh \
    | sudo bash -s -- \
      --bootstrap-token=xxxxx \
      --backend-url=https://nta.example.com \
      --node-name=h20-node-01 \
      --cache-root=/data/model-cache
```

脚本做的事：

1. 校验系统依赖（docker / nvidia-container-toolkit / python3.11）
2. 创建 `forge` 系统用户，加入 `docker` group
3. 下载 infer-agent 可执行包到 `/opt/infer-agent`
4. 写 `/etc/infer-agent/env`（含 bootstrap token）
5. 安装 systemd unit
6. `systemctl enable --now infer-agent`
7. 调 backend `/api/v2/infer-agents/register` 换取长期 token
8. 输出验证命令 `systemctl status infer-agent`

### 7.2 Infer Agent 升级

两种模式：

- **蓝绿升级**：新版本 Infer Agent 监听 :9001，控制面切换 endpoint 后停老版本
- **原地升级**：systemd 重启，desired state 从 SQLite 恢复

注意：Infer Agent 重启期间 vLLM 容器**不受影响**（容器是独立进程）。用户请求继续走 vLLM。

### 7.3 日志

| 日志 | 位置 | 轮转 |
|------|------|------|
| Infer Agent 自身 | `journalctl -u infer-agent` 或 `/var/log/infer-agent/agent.log` | logrotate |
| vLLM 容器 | `/data/nta-runtime/deployments/{id}/stdout.log` | size-based |
| Reconcile 事件 | SQLite `events` 表 | 保留最近 7 天 |

### 7.4 常见运维动作

| 动作 | 命令 |
|------|------|
| 查看当前部署 | `curl localhost:9000/v1/deployments/current` |
| 查看缓存 | `curl localhost:9000/v1/cache/models` |
| 手动停止 vLLM | `curl -X DELETE localhost:9000/v1/deployments/current` |
| 强制重部署 | 控制面 bump generation，PUT 下来 |
| Infer Agent 重启 | `systemctl restart infer-agent` |
| 紧急下线 | `systemctl stop infer-agent && docker stop nta-vllm` |

---

## 8. 安全补充

主方案已覆盖大部分安全设计，本节只做增量补充。

### 8.1 COS STS 临时凭据

**原则**：Infer Agent 机器不持久化长期 COS SecretKey。

流程：

```
Infer Agent 需要下载 → 调 Backend /api/v2/infer-agents/{id}/cos-credentials
                        ↓
                  Backend 调腾讯云 STS 生成
                  - 限定 bucket 和 prefix（只能读对应 artifact）
                  - 只读权限
                  - 30 分钟过期
                        ↓
                  返回 TmpSecretId/Key/Token
                        ↓
Infer Agent 用临时凭据下载 → 30 分钟后自动失效
```

好处：Infer Agent 机器被攻破，攻击者最多拿到 30 分钟的只读访问。

### 8.2 Bootstrap Token 一次性

- Bootstrap Token 只用于首次注册
- 换到 Agent Token 后立即失效（Backend 侧记录使用状态）
- Agent Token 可由控制面管理页手动吊销

### 8.3 Docker socket 限权（可选增强）

如果担心 Infer Agent 持有 docker socket = root：

- 方案 A：Infer Agent 进程本身运行在受限 user namespace 内
- 方案 B：不挂 docker socket，使用 `dockerd --tls` + Infer Agent 持客户端证书
- 方案 C：使用 [sysbox](https://github.com/nestybox/sysbox) 或 rootless docker

第一阶段**方案 A 够用**，二三阶段再评估。

### 8.4 Infer Agent 监听绑定

默认 `--host 127.0.0.1:9000`（仅本机）。Backend 通过 SSH 隧道或 WireGuard 访问。如确需跨机，强制配置：

- TLS 证书
- Bearer token header
- 可选 mTLS

禁止 `0.0.0.0` + 无鉴权。

---

## 9. 与主方案的融合建议

如果要出 0.2 版最终文档，建议把本方案的以下要点吸收进主方案：

### 9.1 Infer Agent 实现层面

- Infer Agent 内部采用 **Reconciler loop + SQLite desired/observed** 结构（写入主方案第 8 章）
- 新增 `generation` 字段到 `model_deployments` 表，用作乐观锁
- Infer Agent 进程通信采用 **PUSH + SSE** 而非 pull-based（主方案第 8 章 API 形式澄清）

### 9.2 安全层面

- 明确 COS 使用 **STS 临时凭据**而非长期 SecretKey（主方案第 12.3 节补充）
- 规定 **Bootstrap Token 一次性** + Agent Token 可吊销（主方案第 12.2 节补充）
- 明确 Infer Agent 默认 **绑本机**，跨机访问必须走隧道或 TLS（主方案第 12.1 节补充）

### 9.3 运维层面

- 提供**一键安装脚本**规格（主方案第 8.1 节补充）
- Infer Agent 升级不影响 vLLM 容器（主方案第 8 章新增"升级策略"小节）

### 9.4 不建议合并的部分

- 声明式 API 和命令式 API 的对立：保持控制面对外命令式，Infer Agent 内部声明式，两层并存。
- 多 slot、Gateway 热切换、多模型资源调度不进入当前主方案 MVP。

---

## 10. 代码布局与工程约定

### 10.1 仓库目录建议

```
model-forge/
├── backend/                     # 已有
├── frontend/                    # 已有
├── probe/                       # 已有，不动
├── infer/                       # 新增（Infer Agent 部署执行器）
│   ├── pyproject.toml
│   ├── src/nta_infer_agent/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── state.py             # SQLite 持久化
│   │   ├── reconciler.py        # 核心 loop
│   │   ├── api/
│   │   │   ├── deployments.py
│   │   │   ├── cache.py
│   │   │   ├── events.py
│   │   │   └── health.py
│   │   ├── runtime/
│   │   │   ├── docker_runtime.py
│   │   │   └── vllm_driver.py
│   │   ├── storage/
│   │   │   ├── cos_client.py    # 用 STS 凭据
│   │   │   ├── manifest.py      # 校验 + 解析
│   │   │   ├── local_cache.py
│   │   │   └── lock.py
│   │   ├── observability/
│   │   │   ├── events.py
│   │   │   └── metrics.py
│   │   └── security/
│   │       ├── bootstrap.py
│   │       └── token.py
│   ├── tests/
│   ├── Dockerfile
│   └── systemd/infer-agent.service
├── packages/                    # 新增（shared）
│   └── forge-schemas/
│       └── src/forge_schemas/
│           ├── deployment.py    # Spec + Status 共享
│           ├── manifest.py
│           └── events.py
└── infra/
    └── infer/
        ├── install.sh
        └── uninstall.sh
```

### 10.2 依赖约定

| 组件 | 运行时 | 关键依赖 |
|------|--------|----------|
| Infer Agent | Python 3.11+ | FastAPI, uvicorn, docker, boto3, aiosqlite, httpx |
| Backend | 沿用项目现状 | 新增 `forge-schemas` 依赖 |

### 10.3 测试分层

- **Unit**：Reconciler 状态机、Manifest 解析、LRU 淘汰
- **Integration**：Mock Docker + Mock COS，跑完整 reconcile
- **E2E**：小模型（如 Qwen2.5-0.5B）真实跑一次 deploy/stop/deploy

### 10.4 代码风格

- 沿用项目 service pattern：`api/ → services/ → storage/`
- Pydantic 2 + 严格校验
- 所有 I/O 异步
- 结构化日志（JSON），字段：`deployment_id`, `generation`, `phase`, `event_type`

---

## 11. 开放问题

本方案特有的开放问题（主方案 16 个问题之外）：

1. **generation 冲突策略**：同时两个用户对同一个 deployment 改参数，后写覆盖还是合并？
2. **Infer Agent SQLite 迁移**：未来 Agent schema 升级的迁移机制？
3. **Reconcile tick 频率**：2 秒是否合适？高频浪费 CPU，低频切换响应慢。
4. **SSE 断线策略**：Backend 订阅 Infer Agent SSE 断线后，是重连还是改轮询？
5. **Infer Agent 和 Backend 时钟漂移**：event 时间戳以谁为准？
6. **是否需要 Agent 侧鉴权 Middleware 的白名单**：只允许注册过的 Backend IP 调用？
7. **STS 凭据续期**：下载耗时 > 30 分钟的大模型如何处理？

---

## 附录 A：与主方案的关键字段对齐

| 主方案字段 | 本方案字段 | 说明 |
|------|------|------|
| `model_deployments.status` | `DeploymentStatus.phase` | 同义，建议值集合对齐 |
| `model_deployments.temporal_workflow_id` | 不需要 | 本方案不强依赖 Temporal |
| 新增 `model_deployments.generation` | `DeploymentSpec.generation` | **需要新增**，用作乐观锁 |
| `model_deployment_events.event_type` | Infer Agent SSE event.type | 命名应对齐 |

## 附录 B：与主方案实施计划的配合

主方案 5 个 Phase 中本方案的工作位置：

| Phase | 主方案范围 | 本方案对应工作 |
|------|------|------|
| Phase 1 | 单节点单模型部署 | Infer Agent 骨架 + Reconciler + PUT/GET API + COS 下载 + docker 启停 |
| Phase 2 | 切换与回滚 | Infer Agent 支持 stopping_previous 阶段 + rollback 的 generation 回放 |
| Phase 3 | GPU 资源计划 | Infer Agent 支持多 deployment 并存（扩展 API 从 current 改为 {id}） |
| Phase 4 | LoRA | Infer Agent 扩展 engine spec，支持 `--enable-lora` 和 adapter 热加载 |
| Phase 5 | 多节点 | 多 Infer Agent 协调由 Backend 完成，单 Infer Agent 职责不变 |

**Phase 1 的 Infer Agent MVP 预估工作量**：2 周（1 人）
- 骨架 + SQLite + Reconciler：3 天
- COS 下载 + manifest 校验：2 天
- docker runtime + vLLM 驱动：2 天
- API + SSE：2 天
- 测试 + 安装脚本 + 联调：3 天
