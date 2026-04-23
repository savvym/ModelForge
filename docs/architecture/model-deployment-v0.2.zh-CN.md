# 模型部署控制面设计（v0.2 融合版）

> NTA Platform - 训练产出部署控制面
> 版本：0.2 | 2026-04-21
> 关联：`model-deployment-control-plane.zh-CN.md`（主方案 0.1）、`model-deployment-independent-agent.zh-CN.md`（姊妹方案 0.1）

---

## 0. 文档说明

### 0.1 本版本相对 0.1 的变化

本版本是**针对"训练产出部署 + 评测闭环"场景的收敛版**。在 0.1 主方案和姊妹方案基础上做了三件事：

1. **裁剪**：砍掉当前场景用不到的复杂度（Inference Gateway、蓝绿 slot、多节点）
2. **融合**：吸收姊妹方案的 Agent 内部实现（Reconciler、声明式 API、STS 凭据等）
3. **新增**：**Base + Adapter 二元制品模型**，同时支持全参微调和 LoRA/QLoRA 微调

### 0.2 目标场景

本版本专为以下场景设计：

- 对 base model 做 **CPT**（继续预训练）产出新 base
- 对 base model 做 **全参数 SFT** 产出新 base
- 对 base model 做 **LoRA/QLoRA SFT** 产出 adapter
- 训练产出存储到 COS
- 在控制面可以**浏览、部署、评测**这些产出
- 部署**一次一个底座**，底座切换接受停机
- LoRA adapter 可在同一底座上**不停机热插拔**

### 0.3 什么场景应该回到 0.1 方案

当你的场景演进到下列情形，再回到 0.1 主方案：

- 推理机扩展到多台
- 需要真正零停机切换（业务侧不能容忍秒级不可用）
- 需要同时服务多个异构底座
- 需要多租户强隔离

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [设计结论](#2-设计结论)
3. [核心概念：Base + Adapter 二元制品](#3-核心概念base--adapter-二元制品)
4. [系统架构](#4-系统架构)
5. [核心组件](#5-核心组件)
6. [数据模型](#6-数据模型)
7. [API 设计](#7-api-设计)
8. [三种典型部署场景](#8-三种典型部署场景)
9. [部署流程与状态机](#9-部署流程与状态机)
10. [Agent 内部架构](#10-agent-内部架构)
11. [vLLM Runtime 配置](#11-vllm-runtime-配置)
12. [模型切换策略](#12-模型切换策略)
13. [制品识别与 COS 规范](#13-制品识别与-cos-规范)
14. [缓存策略](#14-缓存策略)
15. [安全与网络](#15-安全与网络)
16. [可观测性](#16-可观测性)
17. [与现有系统集成](#17-与现有系统集成)
18. [实施计划](#18-实施计划)
19. [开放问题](#19-开放问题)

---

## 1. 背景与目标

### 1.1 背景

NTA Platform 已具备：

- PostgreSQL 元数据 / COS 对象存储 / Temporal 长任务编排 / Model Registry / Evaluation / Probe
- 团队已在使用上述能力进行模型评测与批量推理

下一阶段需要**把平台扩展为训练产出的部署控制面**：把 COS 中保存的 CPT/SFT 产出部署到一台 8 卡 H20 推理机，并能被现有评测和聊天模块直接使用。

### 1.2 目标

1. 训练完成后的制品（CPT / 全参 SFT / LoRA SFT）能在平台上**登记和浏览**
2. 能**一键部署**选中的制品到 H20 推理机
3. **自动识别制品类型**（base vs adapter），并做兼容性校验
4. 部署状态、下载进度、日志、健康检查**可观测**
5. 部署成功后**自动注册到 Model Registry**，评测/聊天立即可用
6. **Adapter 热插拔**：同一底座上增减 LoRA 不停机
7. 底座切换可停机，停机窗口展示清晰

### 1.3 非目标（本版本）

- 多机 GPU 调度
- Kubernetes 编排
- Inference Gateway 和蓝绿 slot
- 多租户强隔离与配额
- 自动弹性扩缩容
- 同时服务多个底座

---

## 2. 设计结论

本版本采用：

```text
NTA 控制面 + Inference Node Agent (独立进程) + Docker + vLLM with LoRA
```

关键决策：

1. **独立 Agent 进程**，不复用 probe，理由见姊妹方案第 2 节
2. **Agent 内部声明式 + Reconciler**，API 只写期望态，后台收敛
3. **Base + Adapter 二元制品模型**，同时支持全参和 LoRA
4. **单 slot 单底座**，不做蓝绿，切换接受停机
5. **vLLM 启动即开 `--enable-lora`**，为 adapter 热插拔做准备
6. **Model Registry 直连 vLLM endpoint**，不做 Gateway

---

## 3. 核心概念：Base + Adapter 二元制品

### 3.1 两类制品

| 类型 | 含义 | 代表 | 大小 | 部署方式 |
|------|------|------|------|---------|
| **base** | 完整模型权重 | 原厂模型 / CPT 产出 / 全参 SFT 产出 | 几十 GB ~ 几百 GB | 必须由 vLLM 直接加载 |
| **adapter** | LoRA/QLoRA 适配器 | LoRA SFT 产出 | 几十 MB ~ 几 GB | 必须依附于 base |

### 3.2 兼容性规则

- 每个 adapter 必须声明其**源 base**（训练时所用的底座）
- 部署时，adapter 只能挂载到**源 base 匹配**的部署上
- 规则由 `adapter_config.json` 中 `base_model_name_or_path` 字段决定，Agent 侧严格校验

### 3.3 部署组合

```text
一次部署 = 一个 base + 零个或多个 adapter

场景 ①  纯 base 部署        (全参 SFT / CPT / 原厂模型)
        vLLM ← base
        对外 serving: {base}

场景 ②  base + adapters     (LoRA 微调 + Multi-LoRA 并行)
        vLLM ← base + enable-lora + [adapter_1, adapter_2, ...]
        对外 serving: {base, adapter_1, adapter_2, ...}

场景 ③  切换 base           (停机)
        旧 vLLM stop → 新 base 下载 → 新 vLLM start
```

### 3.4 Multi-LoRA 带来的质变

同一底座下，**多个 LoRA 可同时服务**：

- 评测模块可对同一底座的 **v1、v2、v3 做 A/B 对比**（同时请求）
- 新 adapter 加载 / 卸载 **2-10 秒，不重启 vLLM**
- 一个底座可服务几十个微调版本，显存增量小

这是"base + adapter"模型相对"每个微调都当作独立 base"的核心收益。

---

## 4. 系统架构

```text
┌──────────────────────────────────────────────────────────────────┐
│                        NTA 控制面                                │
│                                                                  │
│  ┌────────────────────┐   ┌────────────────────────────────────┐ │
│  │ Frontend (Next.js) │   │ Backend (FastAPI + Temporal)       │ │
│  │  /artifacts        │   │  - artifact_service                 │ │
│  │  /deployments      │──►│  - deployment_service               │ │
│  │  /evaluations      │   │  - agent_client                     │ │
│  └────────────────────┘   │  - eval (已有)                      │ │
│                           │  - model_registry (已有)            │ │
│                           └──────────────┬─────────────────────┘ │
│                                          │                        │
│  ┌──────────────────────────────────────▼────────────────────┐  │
│  │ PostgreSQL                                                │  │
│  │  model_artifacts (base/adapter)                          │  │
│  │  inference_nodes                                         │  │
│  │  model_deployments                                       │  │
│  │  deployment_adapters (多对多)                             │  │
│  │  model_deployment_events                                 │  │
│  │  model_cache_entries (可选)                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────┘
                                       │ HTTPS
                                       │ ①PUT /v1/deployments/current
                                       │ ②SSE /v1/events
                                       │ ③POST /heartbeat
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     H20 推理机                                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ forge-agent (FastAPI, :9000)                              │ │
│  │  - API: deployments / cache / events / health             │ │
│  │  - Reconciler (desired → observed)                        │ │
│  │  - COS 下载 (STS 临时凭据)                                │ │
│  │  - Docker Runtime (启停 vLLM)                             │ │
│  │  - State (SQLite)                                         │ │
│  └─────────────────────┬──────────────────────────────────────┘ │
│                        │ docker API                              │
│                        ▼                                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ vLLM Container (nta-vllm)                                  │ │
│  │  --enable-lora                                             │ │
│  │  :8000 (OpenAI-compatible)                                 │ │
│  │  GPUs: 0-7                                                 │ │
│  │                                                            │ │
│  │  Serving:                                                  │ │
│  │    base: qwen-cpt-v1                                      │ │
│  │    adapter: my-sft-v1                                     │ │
│  │    adapter: my-sft-v2                                     │ │
│  │    adapter: my-sft-v3                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  /data/model-cache/                                              │
│    bases/{sha}/        完整模型                                  │
│    adapters/{sha}/     LoRA 权重                                 │
└──────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │ Model Registry Provider
                                       │ base_url: http://h20-1:8000/v1
                                       │
                                       └── Evaluation / Chat / Batch
```

---

## 5. 核心组件

### 5.1 NTA 控制面

职责：
- 制品元数据管理（识别、登记、兼容性校验）
- 节点注册和状态展示
- 部署编排（声明式下发给 Agent）
- 订阅 Agent SSE，持久化事件
- 同步 Model Registry

控制面不直接操作 GPU 或容器。

### 5.2 Inference Node Agent (`forge-agent`)

职责：
- 自注册 + 心跳
- GPU/磁盘/缓存状态上报
- 从 COS 下载制品（用 STS 临时凭据）
- 校验 manifest/sha256
- 启停 vLLM 容器
- 动态加载/卸载 LoRA adapter
- Reconciler 推进状态机
- SSE 事件流回推

详见第 10 节。

### 5.3 vLLM Runtime

每台推理机上**只运行一个 vLLM 容器**（名字 `nta-vllm`）。

关键：启动时一律带 `--enable-lora`，即便当前不挂 adapter，以便将来动态添加无需重启。

### 5.4 Model Registry（已有，扩展）

新增逻辑：
- 部署成功 → 自动为 serving 的每个模型创建 Model 条目
- Adapter 增减 → 同步增删 Model 条目
- 底座切换 → 替换所有 Model 条目

---

## 6. 数据模型

### 6.1 `model_artifacts`

相比 0.1 主方案，新增 `artifact_type`、`base_artifact_id` 和 adapter 元信息字段。

```python
class ModelArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "model_artifacts"

    project_id: UUID
    name: str                         # "my-sft-lora-v3"
    version: str
    description: str | None

    # 分类
    artifact_type: Literal["base", "adapter"]
    base_artifact_id: UUID | None      # adapter 专用，指向其源 base

    # 来源
    source_type: Literal["upstream", "training", "manual_upload"]
    source_training_run_id: UUID | None  # 来自训练任务（如果你有训练模块）

    # COS 存储
    storage_uri: str
    storage_bucket: str
    storage_prefix: str
    manifest_key: str | None

    # 模型元信息（base 或 adapter 通用）
    architecture: str | None           # "qwen2", "llama", "deepseek" 等
    dtype: str | None                  # "bf16" | "fp16" | "fp8" | "int4"
    size_bytes: int | None
    sha256: str | None
    file_count: int | None

    # base 专有
    quantization: str | None
    recommended_tp_size: int | None
    recommended_max_model_len: int | None

    # adapter 专有
    adapter_format: Literal["lora", "qlora"] | None
    adapter_rank: int | None
    adapter_alpha: int | None
    adapter_target_modules: list[str] | None
    adapter_base_model_hint: str | None   # 训练时记录的底座名/路径

    # 运行时建议参数
    runtime_args_json: dict

    # 状态
    status: Literal["pending", "inspecting", "available", "invalid", "deleted"]
    inspected_at: datetime | None
    invalid_reason: str | None
```

### 6.2 `inference_nodes`

沿用 0.1 主方案设计，字段不变。

### 6.3 `model_deployments`

相比 0.1 主方案，**去掉 `slot` 字段**，新增 `generation` 和 `enable_lora`。

```python
class ModelDeployment(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "model_deployments"

    project_id: UUID
    node_id: UUID
    base_artifact_id: UUID            # ⭐ 必填：底座
    provider_id: UUID | None          # 部署成功后同步到 Model Registry
    name: str                         # 人类可读

    # 状态
    status: Literal[
        "queued", "downloading", "verifying",
        "stopping_previous", "starting", "warming",
        "smoke_testing", "active",
        "failed", "cancelling", "cancelled", "stopped"
    ]
    generation: int                   # ⭐ 乐观锁
    enable_lora: bool                 # ⭐ 即使初始无 adapter 也建议 true

    # Runtime
    runtime: str = "vllm"
    container_id: str | None
    container_name: str | None
    listen_port: int = 8000
    base_url: str | None              # "http://h20-1:8000/v1"

    # vLLM 参数
    served_base_name: str             # 对外暴露的底座名
    tensor_parallel_size: int = 8
    pipeline_parallel_size: int = 1
    gpu_ids_json: list[int] = [0,1,2,3,4,5,6,7]
    max_model_len: int | None
    max_loras: int = 16
    max_lora_rank: int = 128
    runtime_args_json: dict = {}

    # 工作流
    temporal_workflow_id: str | None

    # 错误
    error_code: str | None
    error_message: str | None

    # 时间戳
    started_at: datetime | None
    activated_at: datetime | None
    finished_at: datetime | None
```

### 6.4 `deployment_adapters` (新增)

部署和 adapter 的多对多关系表。

```python
class DeploymentAdapter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deployment_adapters"

    deployment_id: UUID
    adapter_artifact_id: UUID
    adapter_name: str                 # 对外 serving 的名字（必须在部署内唯一）

    # 状态
    status: Literal["pending", "loading", "loaded", "unloading", "error"]
    load_on_start: bool = True

    loaded_at: datetime | None
    error_message: str | None

    # 约束：(deployment_id, adapter_name) 唯一
```

### 6.5 `model_deployment_events`

沿用 0.1 主方案，但 `event_type` 值集扩展：

```text
artifact.inspected
artifact.download_started
artifact.download_progress
artifact.download_completed
artifact.verify_completed

runtime.stopping_previous
runtime.starting
runtime.ready
runtime.unhealthy
runtime.stopped

adapter.load_started
adapter.load_completed
adapter.unload_completed
adapter.load_failed

smoke_test.started
smoke_test.completed

registry.synced
```

### 6.6 `model_cache_entries`

沿用 0.1 主方案。

---

## 7. API 设计

### 7.1 分层原则

- **外部 API（控制面对外）**：命令式，符合 HTTP/REST 习惯
- **Agent API（控制面对 Agent）**：声明式，幂等

### 7.2 制品 API

```text
GET    /api/v2/model-artifacts
POST   /api/v2/model-artifacts                    登记（扫描 COS）
GET    /api/v2/model-artifacts/{id}
POST   /api/v2/model-artifacts/{id}/inspect       重新扫描 COS 识别
PATCH  /api/v2/model-artifacts/{id}               修改元信息
DELETE /api/v2/model-artifacts/{id}
GET    /api/v2/model-artifacts/{id}/compatible-bases    # adapter 查可用底座
GET    /api/v2/model-artifacts/{id}/compatible-adapters # base 查可挂 adapter
```

### 7.3 推理节点 API

```text
GET    /api/v2/inference-nodes
GET    /api/v2/inference-nodes/{id}
GET    /api/v2/inference-nodes/{id}/cache
POST   /api/v2/inference-nodes/{id}/disable
POST   /api/v2/inference-nodes/{id}/enable
POST   /api/v2/inference-agents/register          # Agent 主动调用
POST   /api/v2/inference-agents/{id}/heartbeat
POST   /api/v2/inference-agents/{id}/cos-credentials  # STS 换凭据
```

### 7.4 部署 API

```text
GET    /api/v2/model-deployments
POST   /api/v2/model-deployments                  创建部署
GET    /api/v2/model-deployments/{id}
POST   /api/v2/model-deployments/{id}/cancel      取消
DELETE /api/v2/model-deployments/{id}             停止（保留记录）
GET    /api/v2/model-deployments/{id}/events      SSE 事件流
GET    /api/v2/model-deployments/{id}/logs        vLLM 日志（尾部 N 行）

# Adapter 热插拔
GET    /api/v2/model-deployments/{id}/adapters
POST   /api/v2/model-deployments/{id}/adapters    挂载 adapter
DELETE /api/v2/model-deployments/{id}/adapters/{adapter_name}
```

### 7.5 Agent 侧声明式 API

Agent 监听 `:9000`，Backend 通过 `AgentClient` 调用。

```text
PUT    /v1/deployments/current     设置期望态（含 base + adapters）
GET    /v1/deployments/current     读实际态
DELETE /v1/deployments/current     期望态置为 stopped
GET    /v1/events                  SSE 事件流
GET    /v1/cache/models            缓存清单
DELETE /v1/cache/models/{sha}      手动清理
GET    /v1/health                  健康 + GPU 状态
GET    /v1/metrics                 Prometheus
```

### 7.6 关键 Schema（共享包 `forge-schemas`）

```python
class AdapterBinding(BaseModel):
    adapter_artifact_id: UUID
    adapter_name: str
    local_path: str | None           # Agent 填写
    load_on_start: bool = True

class BaseBinding(BaseModel):
    base_artifact_id: UUID
    served_name: str                 # 对外暴露的底座名
    local_path: str | None           # Agent 填写
    cos_source: CosSource

class EngineSpec(BaseModel):
    name: Literal["vllm"] = "vllm"
    image: str
    tensor_parallel_size: int
    pipeline_parallel_size: int = 1
    max_model_len: int | None
    max_loras: int = 16
    max_lora_rank: int = 128
    gpu_memory_utilization: float = 0.85
    dtype: Literal["bf16", "fp16", "fp8"] = "bf16"
    enable_prefix_caching: bool = True
    extra_args: dict[str, Any] = {}

class DeploymentSpec(BaseModel):
    deployment_id: UUID
    generation: int
    base: BaseBinding
    adapters: list[AdapterBinding] = []
    engine: EngineSpec
    desired_phase: Literal["running", "stopped"] = "running"
    smoke_test: SmokeTestSpec | None = None
    enable_lora: bool = True          # 默认开，以便将来挂 adapter

class DeploymentStatus(BaseModel):
    deployment_id: UUID
    generation: int
    phase: str
    progress: int
    endpoint: str | None
    base_name: str | None
    loaded_adapters: list[str]
    container_id: str | None
    last_event: str
    error: ErrorDetail | None
    observed_at: datetime
    last_health_ok_at: datetime | None
```

---

## 8. 三种典型部署场景

### 8.1 场景 ①：纯 base 部署

**适用**：原厂模型、CPT 产出、全参 SFT 产出

**UI 流程**：
1. 制品列表选一个 `artifact_type=base` 的制品
2. 确认 vLLM 参数（默认从制品的 `recommended_*` 推断）
3. 点"部署"

**Spec**：
```json
{
  "base": {"base_artifact_id": "...", "served_name": "my-sft-full-v2"},
  "adapters": [],
  "engine": {...},
  "enable_lora": true
}
```

**结果**：
- vLLM 启动 + 对外 serving `my-sft-full-v2`
- Registry 注册一个 Model

### 8.2 场景 ②：base + adapters

**适用**：LoRA SFT 产出，尤其同底座多版本对比

**UI 流程**：
1. 制品列表选一个 adapter → 系统自动找到兼容 base
2. 可选：再挂其他兼容 adapter（多选）
3. 点"部署"

**Spec**：
```json
{
  "base": {"base_artifact_id": "base-uuid", "served_name": "qwen-cpt-v1"},
  "adapters": [
    {"adapter_artifact_id": "a1", "adapter_name": "my-sft-v1"},
    {"adapter_artifact_id": "a2", "adapter_name": "my-sft-v2"},
    {"adapter_artifact_id": "a3", "adapter_name": "my-sft-v3"}
  ],
  "engine": {...},
  "enable_lora": true
}
```

**结果**：
- vLLM 启动 + 加载 3 个 LoRA
- Registry 注册 4 个 Model（底座 + 3 adapter）
- 评测可对 3 个版本 A/B 对比

### 8.3 场景 ③：切换 base（停机）

**适用**：从 Qwen 切 DeepSeek、从全参 SFT 切到另一个底座

**流程**：
1. 创建新部署（新 base_artifact_id）
2. Agent Reconciler 发现底座变化 → 停旧 vLLM → 下载新 base → 启新 vLLM
3. 停机窗口 1-15 分钟（取决于是否需要下载）

**UI 提示**：
- "切换底座会中断当前所有 serving，预计停机 X 分钟"
- 切换期间所有 `/v1/chat/completions` 请求失败
- 评测模块应延后运行

### 8.4 Adapter 运行时热插拔

场景 ② 部署成功后，用户可**不停机**增减 adapter：

```
POST /api/v2/model-deployments/{id}/adapters
{"adapter_artifact_id": "a4", "adapter_name": "my-sft-v4"}

→ Backend 更新 DeploymentSpec.adapters，generation+1
→ Agent Reconciler 发现 adapter 列表变化
→ 只调用 vLLM load_lora_adapter，不重启容器
→ 2-10 秒后新 adapter 可用
```

---

## 9. 部署流程与状态机

### 9.1 总体状态机

```text
queued
  └─► downloading
        └─► verifying
              └─► stopping_previous  (如有旧部署)
                    └─► starting
                          └─► warming      (等 /health 200)
                                └─► smoke_testing  (可选)
                                      └─► active
                                            │
                                            ├─ adapter 增减 → 保持 active
                                            └─ 底座切换 → 重走流程

任意阶段
  └─► failed (可重试)
  └─► cancelling → cancelled
  └─► stopped (由用户主动停止)
```

### 9.2 Temporal 工作流（简化版）

相比 0.1 主方案的 11 步工作流，本版本简化为：

```text
ModelDeploymentWorkflow
  1. validate_spec
  2. ensure_base_cached           (cache miss 才下载)
  3. verify_base
  4. ensure_adapters_cached       (并行)
  5. stop_previous_container      (如存在)
  6. start_vllm_container
  7. wait_runtime_healthy
  8. load_adapters                (通过 Agent)
  9. run_smoke_test               (可选)
 10. sync_model_registry
 11. mark_deployment_active
```

第 4、8 步由 Agent 完成。

### 9.3 Activity 分层

**控制面 Activity**（由 Backend worker 执行）：
- `validate_spec`
- `sync_model_registry`
- `mark_deployment_active`
- `mark_deployment_failed`

**Agent Activity**（由 Agent 的 Reconciler 执行，Backend 通过 AgentClient 调用并轮询）：
- `ensure_base_cached`（Agent 内部自动 COS 下载）
- `verify_base`
- `ensure_adapters_cached`
- `stop_previous_container`
- `start_vllm_container`
- `wait_runtime_healthy`
- `load_adapters`
- `unload_adapters`
- `run_smoke_test`

**简化选择**：如果觉得 Temporal 太重，第一阶段可以直接用 asyncio + 数据库状态持久化，Reconciler 的幂等性保证最终一致。Temporal 放在 Phase 2 引入。

### 9.4 Adapter 增减（不走 Workflow）

Adapter 热插拔不需要 Temporal，直接：

```
Backend.deployment_service.add_adapter(dep_id, adapter_id)
  → 更新 DB 的 deployment_adapters 表 + generation+1
  → AgentClient.put_deployment(new_spec)
  → 订阅 SSE 等 adapter.load_completed 事件
  → 更新 deployment_adapters.status = loaded
  → 同步 Model Registry 新增 Model 条目
```

---

## 10. Agent 内部架构

### 10.1 进程内部

```text
┌──────────────────────────────────────────────┐
│ forge-agent (FastAPI + asyncio)              │
│                                              │
│  API Layer                                   │
│    PUT/GET /v1/deployments/current           │
│    SSE /v1/events                            │
│    ...                                       │
│             │                                │
│             ▼                                │
│  State Store (SQLite, WAL)                   │
│    desired_state                             │
│    observed_state                            │
│    events                                    │
│             │                                │
│             ▼                                │
│  Reconciler (tick 2s 或 kick)                │
│    - diff desired vs observed                │
│    - 推进状态机                               │
│    - 发事件                                   │
│             │                                │
│   ┌─────────┼─────────┐                      │
│   ▼         ▼         ▼                      │
│ COS      Docker    Local                     │
│ (STS)    Runtime   Cache                     │
└──────────────────────────────────────────────┘
```

### 10.2 Reconcile 核心逻辑

```python
async def reconcile_once():
    desired = state.get_desired()
    if desired is None:
        return

    observed = await observe_actual_state()

    # 期望停止
    if desired.desired_phase == "stopped":
        if observed.phase != "stopped":
            await docker.stop("nta-vllm")
            state.set_phase("stopped")
        return

    # 期望运行
    # 底座变化 → 完整重部署
    if observed.base_name != desired.base.served_name:
        await full_redeploy(desired)
        return

    # 底座不变，检查 adapter 差异
    if observed.phase == "ready":
        await reconcile_adapters(desired, observed)
        return

    # 正常推进（warming / starting 等中间态）
    await advance_state(observed)


async def reconcile_adapters(desired, observed):
    """关键：adapter 变更不重启 vLLM"""
    desired_set = {a.adapter_name: a for a in desired.adapters}
    observed_set = set(observed.loaded_adapters)

    # 加载新的
    for name, binding in desired_set.items():
        if name not in observed_set:
            await ensure_adapter_cached(binding)
            await vllm_load_adapter(binding)

    # 卸载移除的
    for name in observed_set - desired_set.keys():
        await vllm_unload_adapter(name)
```

### 10.3 Generation 乐观锁

- 每次 Backend PUT 新 spec，`generation` +1
- Agent 只接受 ≥ 当前 generation 的 spec
- 并发情况下后到的新 generation 覆盖在途的旧 generation

### 10.4 状态持久化

SQLite（`/var/lib/forge-agent/state.db`）：

```sql
CREATE TABLE desired_state (
    id INTEGER PRIMARY KEY CHECK (id=1),    -- 单行
    spec_json TEXT NOT NULL,
    generation INTEGER NOT NULL,
    updated_at TEXT
);

CREATE TABLE observed_state (
    id INTEGER PRIMARY KEY CHECK (id=1),
    phase TEXT,
    base_name TEXT,
    loaded_adapters_json TEXT,
    container_id TEXT,
    endpoint TEXT,
    last_health_ok_at TEXT
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployment_id TEXT,
    generation INTEGER,
    event_type TEXT,
    level TEXT,
    message TEXT,
    payload_json TEXT,
    created_at TEXT
);
```

### 10.5 Agent 运维

- **systemd** 管理，文件位置沿用 0.1 主方案
- **一键安装脚本** `infra/agent/install.sh`
- **升级不影响 vLLM 容器**（容器独立进程）

详见姊妹方案第 7 节。

---

## 11. vLLM Runtime 配置

### 11.1 启动命令模板

```bash
docker run -d --name nta-vllm \
    --restart=unless-stopped \
    --gpus '"device=0,1,2,3,4,5,6,7"' \
    --ipc=host \
    -p 8000:8000 \
    -v /data/model-cache:/models:ro \
    vllm/vllm-openai:v0.6.3 \
    --model /models/bases/${BASE_SHA} \
    --served-model-name ${BASE_SERVED_NAME} \
    --tensor-parallel-size 8 \
    --pipeline-parallel-size 1 \
    --dtype bfloat16 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 32768 \
    --enable-prefix-caching \
    --enable-lora \
    --max-loras 16 \
    --max-lora-rank 128 \
    --max-cpu-loras 64 \
    --api-key ${RUNTIME_API_KEY}
```

### 11.2 关键参数

| 参数 | 推荐值 | 理由 |
|------|--------|------|
| `--enable-lora` | **总是开** | 即使当前无 adapter，为将来热插拔保留能力 |
| `--max-loras` | 16 | 同时活跃 adapter 上限 |
| `--max-lora-rank` | 128 | 覆盖绝大多数训练 rank（32/64/128） |
| `--max-cpu-loras` | 64 | 更多 adapter 可缓存在内存，按需换入 GPU |
| `--gpu-memory-utilization` | 0.85 | 比 0.9 低一点，给 LoRA 留显存 |
| `--enable-prefix-caching` | 开 | 多轮相似 prompt 提升吞吐 |
| `--max-model-len` | 明确设 | 避免默认超长上下文 OOM |

### 11.3 Adapter 动态加载 API

vLLM 提供两个原生 endpoint（启动 `--enable-lora` 后可用）：

```bash
# 加载
POST /v1/load_lora_adapter
{
  "lora_name": "my-sft-v3",
  "lora_path": "/models/adapters/{sha}"
}

# 卸载
POST /v1/unload_lora_adapter
{
  "lora_name": "my-sft-v3"
}
```

调用方为 Agent 进程。

---

## 12. 模型切换策略

### 12.1 Adapter 切换（推荐路径，不停机）

触发：DeploymentSpec.adapters 变化

流程：
```text
检测 adapter diff
  → 下载新 adapter（~几十秒，取决于大小和网络）
  → vLLM load_lora_adapter  (~2-10 秒)
  → Agent 上报 adapter.load_completed
  → Backend 同步 Registry
  → 用户可立即调用
```

**关键**：vLLM 进程不动，其他 adapter 继续服务。

### 12.2 底座切换（停机）

触发：DeploymentSpec.base 变化，或新建部署但底座与当前不同

流程：
```text
Agent 检测底座变化
  → 下载新 base（如未缓存，5-15 分钟）
  → verify sha256
  → docker stop nta-vllm  (~10-30 秒)
  → docker run 新 base + 所有需要的 adapter
  → wait healthy (~60-180 秒大模型加载到显存)
  → smoke test
  → active
```

**总停机时间**：1-15 分钟，取决于缓存状态。

**UI 要求**：
- 部署确认页明确显示"预计停机 X 分钟"
- 切换进行中，Model Registry 里相关模型标记为 "switching"，评测应延后
- 切换失败自动回滚到上一版 spec（Agent generation 回退）

### 12.3 回滚策略（简化版）

相比 0.1 主方案 3 级回滚，本版本简化为：

1. **底座缓存仍在** → 重新 PUT 上一版 DeploymentSpec，几十秒恢复
2. **底座缓存已淘汰** → 重新下载 + 启动，停机再一次

每次部署记录 `previous_generation_spec`，回滚 = 重放上一版 spec。

---

## 13. 制品识别与 COS 规范

### 13.1 COS 路径规范

```text
s3://{bucket}/{root_prefix}/
  projects/{project_id}/
    artifacts/
      bases/{artifact_name}/{version}/
        manifest.json
        config.json
        tokenizer.json
        model-00001-of-000xx.safetensors
        ...
      adapters/{artifact_name}/{version}/
        manifest.json
        adapter_config.json
        adapter_model.safetensors
        tokenizer.json (可选)
```

### 13.2 自动识别逻辑

```python
async def inspect_cos_path(cos_uri: str) -> ArtifactInspection:
    files = await cos.list_objects(cos_uri)
    fnames = {f.name for f in files}

    # Adapter 判定（最高优先级）
    if "adapter_config.json" in fnames:
        cfg = await cos.get_json(f"{cos_uri}/adapter_config.json")
        return ArtifactInspection(
            artifact_type="adapter",
            adapter_format="qlora" if "quantization_config" in cfg else "lora",
            adapter_rank=cfg.get("r"),
            adapter_alpha=cfg.get("lora_alpha"),
            adapter_target_modules=cfg.get("target_modules"),
            adapter_base_model_hint=cfg.get("base_model_name_or_path"),
            suggested_base_artifact_id=await match_base_by_hint(
                cfg.get("base_model_name_or_path")
            ),
        )

    # Base 判定
    if any(f.startswith("model-") and f.endswith(".safetensors") for f in fnames):
        cfg = await cos.get_json(f"{cos_uri}/config.json")
        return ArtifactInspection(
            artifact_type="base",
            architecture=cfg.get("model_type"),
            dtype=cfg.get("torch_dtype", "bf16"),
            size_bytes=sum(f.size for f in files),
        )

    raise InvalidArtifactError(
        "既无 adapter_config.json 也无 model-*.safetensors，无法识别"
    )
```

### 13.3 Manifest 约定（可选但推荐）

如果训练 pipeline 能在 COS 目录下额外上传 `manifest.json`，可以减少扫描开销并提供校验：

```json
{
  "schema_version": "1",
  "artifact_type": "adapter",
  "adapter_format": "lora",
  "adapter_rank": 64,
  "adapter_target_modules": ["q_proj","v_proj","k_proj","o_proj"],
  "base_artifact_id": "uuid-of-base",
  "base_model_name_or_path": "Qwen/Qwen2.5-72B-Instruct",
  "size_bytes": 524288000,
  "files": [
    {"path": "adapter_model.safetensors", "size_bytes": 524000000, "sha256": "..."},
    {"path": "adapter_config.json", "size_bytes": 2048, "sha256": "..."}
  ],
  "training": {
    "run_id": "...",
    "framework": "llama-factory",
    "epochs": 3,
    "dataset": "..."
  }
}
```

如果 manifest 不存在，Agent 下载完成后**动态生成并写回 COS**，下次加载直接读取。

### 13.4 兼容性校验规则

部署时，Backend 校验：

1. `adapter.adapter_base_model_hint` 的 base_model_name/path **必须**与 `base_artifact.name` 或 `base_artifact.source_hf_name` 一致
2. `adapter.adapter_rank` **必须** ≤ `deployment.engine.max_lora_rank`
3. 同一部署内，所有 adapter 的 `adapter_name` 唯一
4. `adapter.architecture`（如有）必须与 base 相同

---

## 14. 缓存策略

### 14.1 目录结构

```text
/data/model-cache/
  bases/
    {sha256}/
      config.json
      tokenizer.json
      model-00001-of-000xx.safetensors
      ...
  adapters/
    {sha256}/
      adapter_config.json
      adapter_model.safetensors
      tokenizer.json (可选)
  .partial/
    {sha256}.partial/    下载中的临时目录
  .meta/
    lru.json             记录 last_used_at
```

### 14.2 LRU 淘汰

- 磁盘使用率 > 85% 触发清理
- 清到 70% 停止
- **active 部署** 的 base 和所有 adapter 永不删除
- 非 active 的按 `last_used_at` 排序，最久未用先删
- Adapter 小（几百 MB），优先保留
- Base 大，优先淘汰非活跃的

### 14.3 下载优化

- 分片并行下载（boto3 支持）
- 断点续传：`.partial` 目录，校验通过后 `rename` 到最终位置
- 同目录 sha256 校验 → 若失败，删除重下
- 并发下载多个 adapter（小文件，网络友好）

---

## 15. 安全与网络

### 15.1 网络拓扑

- 控制面：HTTPS 对外
- Agent：默认 `127.0.0.1:9000`，跨机必须走 VPN / 内网 / TLS
- vLLM：仅监听 Agent 同机 `127.0.0.1:8000`，或内网地址（同时配 `--api-key`）
- Model Registry 的 `base_url` 指向 vLLM 内网地址

### 15.2 鉴权层级

| 层 | 机制 |
|----|------|
| 用户 → 控制面 | 现有平台鉴权 |
| 控制面 → Agent | Bearer Token（Agent 注册时签发，可吊销） |
| Agent ↔ Backend COS 凭据交换 | Agent Token 换 STS 临时凭据 |
| Agent → COS | STS 临时凭据（30 分钟有效，只读，限 prefix） |
| Agent → vLLM | 内部随机 API key |
| Model Registry → vLLM | 与上同一 API key |

### 15.3 关键原则

- **Agent 不持有长期 COS SecretKey**
- **Bootstrap Token 一次性**，换出 Agent Token 后立即失效
- Agent COS 权限仅 `GetObject` / `HeadObject` / 限 prefix `ListBucket`
- vLLM 的 API key 随机生成，仅 Backend 和 Agent 知道

---

## 16. 可观测性

### 16.1 部署事件（`model_deployment_events`）

前端展示：
- 事件时间线
- 关键事件耗时柱状图（下载、校验、启动、健康检查）
- 错误堆栈 + 最近 100 行日志

### 16.2 节点指标（Agent 心跳上报）

- GPU 利用率、显存、温度（逐卡）
- 磁盘使用（cache_root）
- 当前 active deployment
- vLLM 容器健康
- 已加载 adapter 列表

### 16.3 Runtime 指标

vLLM 的 `/metrics` 端点暴露 Prometheus 格式：
- request 吞吐 / 延迟
- 首 token 延迟（TTFT）
- 输入/输出 token 数
- KV cache 使用率
- LoRA adapter 调用分布

第一阶段可由 Agent 聚合后通过心跳上报少量关键指标；完整 Prometheus 采集放 Phase 3。

### 16.4 日志

- vLLM 容器日志：`/data/nta-runtime/deployments/{id}/{stdout,stderr}.log`
- Agent 可通过 `GET /v1/deployments/current/logs?tail=200` 返回尾部
- 控制面 `/api/v2/model-deployments/{id}/logs` 转发该接口

---

## 17. 与现有系统集成

### 17.1 Model Registry

部署 active 后自动同步：

**Provider**（同一部署共享）：
```
name: Local Inference (h20-node-01)
provider_type: openai-compatible
api_format: chat-completions
base_url: http://h20-1.internal:8000/v1
api_key: <runtime_api_key>
source: deployment
```

**Models**（每个 serving model 一条）：
```
name: qwen-cpt-v1              # 底座
model_code: qwen-cpt-v1
provider_id: <above>

name: my-sft-v1                # adapter
model_code: my-sft-v1
provider_id: <above>
metadata: {adapter: true, base_artifact_id: ...}

name: my-sft-v2
...
```

**更新规则**：
- 部署 active → 插入 Provider + 所有 Models
- Adapter 增加 → 只插 Model
- Adapter 卸载 → 删 Model
- 底座切换 → 删旧 Provider 下所有 Model + 插新的
- 部署 stopped → 标记 Models 为 inactive（保留历史）

### 17.2 Evaluation

评测侧完全无感。模型列表里挑 `my-sft-v1` / `my-sft-v2` 就能评测。

推荐加一个 UX 入口：**部署详情页**有"评测这个版本"按钮，跳转到评测页并预选好 model。

### 17.3 Training（如果已有训练模块）

训练完成钩子：
```
training_run.completed
  → 扫描输出目录
  → 自动创建 model_artifact
  → artifact.status = "available"
  → 推送前端通知："新产出可部署"
```

用户无需手动登记制品。

### 17.4 COS

沿用现有 S3 抽象（`core/s3.py`），COS 兼容 S3 协议。

推理机使用**内网 COS endpoint**（`cos-internal.ap-*.tencentcos.cn`）避免公网流量。

### 17.5 Temporal

新增 task queue：`model-deployments`

控制面 worker 负责 DB 状态变更 activity；Agent 不作为 Temporal worker，改由 Backend 的 activity 通过 AgentClient 调 HTTP。

---

## 18. 实施计划

### Phase 0：制品管理（3-5 天）

目标：能浏览 COS 中的训练产出

- [ ] `model_artifacts` 表（含 base/adapter 字段）
- [ ] `POST /inspect` 扫描 COS 识别类型
- [ ] 前端 `/console/artifacts` 列表页
- [ ] 制品详情页（含兼容性信息）
- [ ] 训练完成钩子（如已有训练模块）

**交付**：用户能登记 COS 路径并看到制品清单。

### Phase 1：Agent MVP + 纯 base 部署（1.5-2 周）

目标：能部署一个 base 模型并被评测

- [ ] `forge-agent` 项目骨架（FastAPI + SQLite + Reconciler）
- [ ] Agent 注册 + 心跳 + Bootstrap Token
- [ ] STS 凭据换取 API
- [ ] COS 下载 + sha256 校验（支持断点续传）
- [ ] Docker Runtime 封装（启停 vLLM）
- [ ] 健康检查 + wait_ready
- [ ] `PUT /v1/deployments/current` 声明式 API
- [ ] `model_deployments` 表 + 部署 API
- [ ] 部署完成自动同步 Model Registry
- [ ] 前端 `/console/deployments` 部署表单
- [ ] 一键安装脚本 `infra/agent/install.sh`

**交付**：选一个 base 制品 → 一键部署 → 在评测中看到该模型可用。

### Phase 2：监测与事件流（3-5 天）

目标：部署过程可见、可诊断

- [ ] Agent SSE `/v1/events`
- [ ] Backend 订阅 SSE 持久化 `model_deployment_events`
- [ ] 前端部署详情页事件时间线
- [ ] vLLM 日志读取接口
- [ ] GPU / 缓存 / 健康指标心跳上报
- [ ] 失败重试 + 错误上报

**交付**：部署过程前端实时可见，错误可诊断。

### Phase 3：LoRA / Adapter 支持（1 周）

目标：支持 LoRA 部署和热插拔

- [ ] vLLM 启动参数加 `--enable-lora` (Phase 1 就应该做)
- [ ] Adapter 制品识别（`adapter_config.json` 解析）
- [ ] `deployment_adapters` 表
- [ ] 部署 Spec 支持 adapters 列表
- [ ] Agent Reconciler 的 adapter diff 逻辑
- [ ] `vllm_load_adapter` / `vllm_unload_adapter` 调用
- [ ] 前端部署页"挂载 adapter" 交互
- [ ] 兼容性校验（base_hint、rank、architecture）
- [ ] Adapter 增减同步到 Model Registry

**交付**：能在同一底座上同时服务 N 个 LoRA，运行时增减不停机。

### Phase 4：Temporal 编排 + 切换优化（可选，3-5 天）

- [ ] 引入 `ModelDeploymentWorkflow` (第 9.2 节)
- [ ] 底座切换回滚机制（previous_generation 回放）
- [ ] 切换 UI 增强（停机预估、倒计时）
- [ ] smoke test 集成

### 后续阶段

当推理机扩展到多台或需要零停机时，回到 0.1 主方案，引入：
- Inference Gateway
- 蓝绿 slot
- 节点调度
- Kubernetes / KServe

---

## 19. 开放问题

承接 0.1 主方案的开放问题，本版本特有的问题：

1. **训练产出的自动登记**：是否有训练 pipeline 可以在完成时回调 Backend？如果没有，用户手动贴 COS 路径？
2. **Adapter 命名规则**：部署内 `adapter_name` 建议格式？`{project}-{name}-{version}`？
3. **Base 模型命名与 HuggingFace 名对齐**：用户训练 LoRA 时 `adapter_config.json` 里 `base_model_name_or_path` 可能是 HF 名（如 `Qwen/Qwen2.5-72B-Instruct`），而 Registry 里登记的是自定义名。如何维护映射？
4. **Multi-LoRA 的显存监控**：16 个 LoRA 同时加载时显存占用如何测算？需要上限保护？
5. **Adapter 上传 / 下载工具**：是否需要给训练同学提供 CLI 方便上传训练产出到标准 COS 路径？
6. **Smoke test 内容**：第一阶段就做还是 Phase 4？如果做，测什么 prompt？
7. **删除制品的清理**：制品删除时，COS 对象是否同时删除？是否需要软删除 + 定期回收？
8. **版本语义**：`artifact.version` 是否强制 semver？和 `artifact.name` 如何联动？
9. **鉴权粒度**：部署操作是 project 级还是需要更细粒度？

---

## 附录 A：术语对齐

| 术语 | 含义 |
|------|------|
| base（底座） | 完整模型权重，可独立部署 |
| adapter | LoRA/QLoRA 适配器，必须依附 base |
| deployment | 一次 vLLM 部署（一个 base + 若干 adapter） |
| artifact | base 或 adapter 的统称 |
| serving model | 通过 vLLM 对外暴露的模型（可能是 base 自身或某个 adapter） |
| generation | DeploymentSpec 的版本号，单调递增 |
| slot | 本版本不使用，0.1 主方案概念 |

## 附录 B：字段对齐（vs 0.1 主方案）

| 0.1 字段 | 本版本变化 |
|---------|----------|
| `model_artifacts.format` | 保留 |
| `model_artifacts.artifact_type` | **新增** |
| `model_artifacts.base_artifact_id` | **新增** |
| `model_artifacts.adapter_*` | **新增一组** |
| `model_deployments.slot` | **删除** |
| `model_deployments.generation` | **新增** |
| `model_deployments.enable_lora` | **新增** |
| `deployment_adapters` 表 | **新增** |

## 附录 C：工作量估算

| Phase | 人天 | 可并行 |
|-------|------|-------|
| Phase 0 | 3-5 | 前后端可并行 |
| Phase 1 | 10-15 | Agent 和 Backend 可并行 |
| Phase 2 | 3-5 | - |
| Phase 3 | 5-7 | - |
| Phase 4 | 3-5 | - |
| **合计** | **24-37 人天** | |

单人全栈约 5-7 周。2 人分工（Backend + Agent）约 3-4 周。
