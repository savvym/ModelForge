# 训练产物单模型部署控制面设计文档

> NTA Platform - Training Artifact -> Single Active Deployment -> Evaluation  
> 版本：0.2 | 2026-04-21

---

## 目录

1. [场景与结论](#1-场景与结论)
2. [设计目标与非目标](#2-设计目标与非目标)
3. [系统架构](#3-系统架构)
4. [核心对象](#4-核心对象)
5. [数据模型设计](#5-数据模型设计)
6. [API 设计](#6-api-设计)
7. [部署工作流](#7-部署工作流)
8. [Infer Agent](#8-infer-agent)
9. [vLLM Runtime](#9-vllm-runtime)
10. [评测集成](#10-评测集成)
11. [状态与可观测性](#11-状态与可观测性)
12. [实施计划](#12-实施计划)
13. [后续演进](#13-后续演进)

---

## 1. 场景与结论

当前业务场景：

1. 对 base model 做 CPT 或 SFT。
2. checkpoint 或 final 训练结果保存到 COS。
3. 需要在平台里随时查看训练结果、模型制品、部署状态。
4. 需要把某个训练结果部署到一台 8 卡 H20 推理机器。
5. 需要针对部署后的模型跑评测。
6. 当前只要求一台机器上同时服务一个模型。
7. 切换模型允许停机，但部署任务必须可监测、可失败、可重试。

结论：更适合采用**训练产物驱动的单模型部署控制面**，而不是完整的蓝绿 slot、多模型调度或分布式探针方案。

推荐架构：

```text
NTA 控制面
  + Model Artifact Registry
  + Model Deployment Workflow
  + Infer Agent
  + vLLM 单实例 Runtime
  + Model Registry / Evaluation 集成
```

核心链路：

```text
CPT/SFT 训练结果写入 COS
        ↓
控制面登记 Model Artifact
        ↓
用户选择某个 artifact 点击部署
        ↓
Temporal 创建部署任务
        ↓
Infer Agent 停止旧 vLLM
        ↓
下载 / 校验新 artifact
        ↓
启动新 vLLM
        ↓
healthcheck + smoke test
        ↓
更新 Model Registry
        ↓
针对部署结果发起 EvaluationRun
```

---

## 2. 设计目标与非目标

### 2.1 目标

1. 管理 CPT/SFT 训练产物，包括 checkpoint、final model、COS 路径和训练来源。
2. 支持把一个训练产物部署到唯一的 active 推理实例。
3. 支持部署任务状态监控：下载、校验、停止旧模型、启动新模型、健康检查、失败原因。
4. 部署成功后自动注册为 OpenAI-compatible 模型，复用现有聊天、评测、批量推理链路。
5. 支持对部署模型直接发起评测，并把评测结果关联回训练产物。
6. 支持失败重试、取消、重新部署。

### 2.2 非目标

第一阶段不做：

- 同机多模型并存。
- 蓝绿 slot 无停机切换。
- GPU 资源调度和配额。
- Kubernetes / Ray Serve / 多节点部署。
- LoRA adapter 动态切换。
- 复杂 Gateway active slot 路由。
- 多租户强隔离和审批流。

这些不是当前瓶颈。当前最重要的是训练产物可追踪、可部署、可评测。

---

## 3. 系统架构

```text
┌────────────────────────────────────────────────────────────────────┐
│                         NTA Platform                               │
│                                                                    │
│  ┌──────────────────────┐      ┌────────────────────────────────┐  │
│  │ Training Artifact UI  │      │ Model Deployment API            │  │
│  │ - 训练结果列表          │      │ - artifact CRUD                 │  │
│  │ - checkpoint/final     │      │ - deployment CRUD               │  │
│  │ - 指标 / 评测结果       │      │ - deploy / cancel / retry       │  │
│  └──────────┬───────────┘      └──────────────┬─────────────────┘  │
│             │                                  │                    │
│  ┌──────────▼───────────┐      ┌──────────────▼─────────────────┐  │
│  │ PostgreSQL            │      │ Temporal                         │  │
│  │ - training_runs        │      │ - ModelDeploymentWorkflow        │  │
│  │ - model_artifacts      │      │ - Deploy / Stop / Start / Check │  │
│  │ - model_deployments    │      └──────────────┬─────────────────┘  │
│  │ - deployment_events    │                     │                    │
│  └──────────┬───────────┘                     │                    │
│             │                                  │                    │
│             ▼                                  ▼                    │
│  ┌──────────────────────┐      ┌────────────────────────────────┐  │
│  │ Model Registry        │      │ Evaluation                      │  │
│  │ - Provider: local     │      │ - benchmark / suite             │  │
│  │ - Model: active model │      │ - run against deployed model    │  │
│  └──────────────────────┘      └────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                 │
                 │ Temporal task queue 或 Infer Agent API
                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                         H20 推理机器                                │
│                                                                    │
│  ┌──────────────────────┐      ┌────────────────────────────────┐  │
│  │ Infer Agent           │      │ Local Model Cache               │  │
│  │ - 心跳 / GPU 状态       │      │ /data/model-cache/{artifact_id} │  │
│  │ - 下载 COS artifact    │      │ - HF safetensors 模型目录        │  │
│  │ - 校验 manifest        │      │ - checkpoint / final             │  │
│  │ - 停止旧 vLLM          │      └────────────────────────────────┘  │
│  │ - 启动新 vLLM          │                                           │
│  └──────────┬───────────┘                                           │
│             │ Docker API                                            │
│             ▼                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ vLLM 单实例 Runtime                                           │   │
│  │ - fixed port: 8000 or 18000                                   │   │
│  │ - OpenAI-compatible /v1                                       │   │
│  │ - one active model at a time                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### 3.1 为什么不需要 Gateway / 蓝绿

当前允许停机切换，且只要求一个模型服务，所以第一阶段可以直接让 Model Provider 指向固定的 vLLM endpoint：

```text
http://{h20-host}:18000/v1
```

切换模型时：

```text
停止旧 vLLM -> 启动新 vLLM -> 健康检查 -> 恢复可用
```

只要部署任务状态清晰，用户知道何时不可用、何时恢复即可。

---

## 4. 核心对象

### 4.1 TrainingRun

训练任务，包括 CPT / SFT。它可能由平台内训练系统创建，也可能从外部训练系统同步。

关键字段：

- base model
- training type: `cpt` / `sft`
- dataset / recipe / hyperparameters
- status
- metrics
- output artifacts

### 4.2 ModelArtifact

一次可部署的模型产物。可以是某个 checkpoint，也可以是 final model。

它是部署和评测的核心对象。

### 4.3 ModelDeployment

一次部署任务及其最终 active runtime 记录。

### 4.4 InferenceNode

一台推理机器。当前只有一台 H20，但数据模型应允许后续多节点。

### 4.5 EvaluationRun

部署成功后，针对 active model 发起现有 evaluation_v2 评测。

---

## 5. 数据模型设计

### 5.1 `training_runs`

如果平台内已有训练任务表，可复用；如果没有，第一阶段可以做外部训练结果登记表。

```python
class TrainingRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "training_runs"

    project_id: UUID
    name: str
    training_type: str          # cpt | sft
    base_model_name: str
    base_model_artifact_id: UUID | None

    status: str                 # running | completed | failed | imported
    source: str                 # platform | external
    source_task_id: str | None

    dataset_refs_json: list[dict]
    recipe_json: dict
    hyperparameters_json: dict
    metrics_json: dict

    output_prefix_uri: str | None
    started_at: datetime | None
    finished_at: datetime | None
```

### 5.2 `model_artifacts`

```python
class ModelArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "model_artifacts"

    project_id: UUID
    training_run_id: UUID | None
    parent_artifact_id: UUID | None

    name: str
    version: str
    artifact_type: str          # checkpoint | final | imported
    training_type: str | None   # cpt | sft
    base_model_name: str | None

    storage_uri: str            # s3://bucket/prefix/
    storage_bucket: str
    storage_prefix: str
    manifest_key: str | None

    format: str                 # huggingface
    dtype: str | None           # bf16 | fp16 | fp8
    quantization: str | None
    size_bytes: int | None
    sha256: str | None

    recommended_runtime: str    # vllm
    recommended_tp_size: int | None
    recommended_max_model_len: int | None
    runtime_args_json: dict

    status: str                 # available | invalid | deleted
```

### 5.3 `inference_nodes`

```python
class InferenceNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inference_nodes"

    project_id: UUID
    name: str
    host: str
    agent_id: str
    agent_version: str

    gpu_type: str               # H20
    gpu_count: int              # 8
    cache_root: str             # /data/model-cache

    status: str                 # online | offline | disabled
    heartbeat_at: datetime | None
    metrics_json: dict
```

### 5.4 `model_deployments`

```python
class ModelDeployment(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "model_deployments"

    project_id: UUID
    artifact_id: UUID
    node_id: UUID

    provider_id: UUID | None
    model_id: UUID | None

    status: str
    # queued | stopping_previous | downloading | verifying
    # starting | warming | active | failed | cancelling | cancelled

    runtime: str                # vllm
    served_model_name: str
    endpoint_url: str           # http://h20:18000/v1
    container_id: str | None
    container_name: str | None

    tensor_parallel_size: int
    gpu_ids_json: list[int]
    runtime_args_json: dict

    temporal_workflow_id: str | None
    previous_deployment_id: UUID | None

    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    activated_at: datetime | None
    finished_at: datetime | None
```

### 5.5 `model_deployment_events`

```python
class ModelDeploymentEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "model_deployment_events"

    deployment_id: UUID
    event_type: str
    level: str                  # info | warning | error
    message: str
    payload_json: dict
    created_at: datetime
```

### 5.6 `artifact_evaluation_links`

用于把训练产物、部署和评测结果串起来。

```python
class ArtifactEvaluationLink(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "artifact_evaluation_links"

    artifact_id: UUID
    deployment_id: UUID | None
    evaluation_run_id: UUID
    benchmark_name: str | None
    created_at: datetime
```

---

## 6. API 设计

### 6.1 训练结果 / 产物

```text
GET    /api/v2/training-runs
POST   /api/v2/training-runs/import
GET    /api/v2/training-runs/{training_run_id}

GET    /api/v2/model-artifacts
POST   /api/v2/model-artifacts
GET    /api/v2/model-artifacts/{artifact_id}
POST   /api/v2/model-artifacts/{artifact_id}/inspect
POST   /api/v2/model-artifacts/{artifact_id}/deploy
DELETE /api/v2/model-artifacts/{artifact_id}
```

### 6.2 部署

```text
GET    /api/v2/model-deployments
GET    /api/v2/model-deployments/current
POST   /api/v2/model-deployments
GET    /api/v2/model-deployments/{deployment_id}
POST   /api/v2/model-deployments/{deployment_id}/cancel
POST   /api/v2/model-deployments/{deployment_id}/retry
POST   /api/v2/model-deployments/{deployment_id}/rollback
GET    /api/v2/model-deployments/{deployment_id}/events
```

### 6.3 节点

```text
GET    /api/v2/inference-nodes
GET    /api/v2/inference-nodes/{node_id}
GET    /api/v2/inference-nodes/{node_id}/cache
```

### 6.4 评测

```text
POST   /api/v2/model-artifacts/{artifact_id}/evaluation-runs
GET    /api/v2/model-artifacts/{artifact_id}/evaluation-runs
```

内部仍复用现有：

```text
POST /api/v2/evaluation-runs/benchmark
POST /api/v2/evaluation-runs
```

---

## 7. 部署工作流

### 7.1 `ModelDeploymentWorkflow`

```text
1. validate_artifact
2. create_deployment_record
3. stop_previous_runtime
4. ensure_artifact_cached
5. verify_local_artifact
6. start_vllm_runtime
7. wait_healthcheck
8. run_smoke_test
9. sync_model_registry
10. mark_active
```

### 7.2 状态迁移

```text
queued
  -> stopping_previous
  -> downloading
  -> verifying
  -> starting
  -> warming
  -> active

任意阶段
  -> failed
  -> cancelling
  -> cancelled
```

### 7.3 切换语义

因为只允许一个 active 模型，部署新模型时必须先停止旧模型。

```text
旧模型 active
  -> 创建新 deployment
  -> 停旧 vLLM
  -> 旧 deployment 标记 inactive
  -> 启新 vLLM
  -> 新 deployment 标记 active
```

如果新模型启动失败：

- 任务标记 failed。
- 可通过 retry 重试当前 artifact。
- 可通过 rollback 重新启动 previous deployment。
- 切换期间 endpoint 可能不可用，这是当前阶段可接受约束。

---

## 8. Infer Agent

### 8.1 推荐形态

使用独立 `Infer Agent`，不复用 probe。

原因：

- probe 是短任务执行器，部署是长驻服务生命周期管理。
- Infer Agent 需要 Docker socket / GPU 管理权限，不应和评测 probe 混用。
- Infer Agent 需要本地状态恢复，适合 Reconciler 模式。

Infer Agent 实现细节参考：

```text
docs/architecture/model-deployment-independent-agent.zh-CN.md
```

### 8.2 最小职责

第一阶段 Infer Agent 只需要：

1. 注册节点和心跳。
2. 上报 GPU / 显存 / 磁盘 / 当前容器状态。
3. 下载 COS 模型到本地缓存。
4. 校验 manifest 或文件 hash。
5. 停止旧 vLLM 容器。
6. 启动新 vLLM 容器。
7. 执行 healthcheck 和 smoke test。
8. 上报部署事件。

### 8.3 不需要的能力

第一阶段不需要：

- 多 slot 管理。
- 多模型容器编排。
- GPU 资源分片。
- 网关配置热切换。
- 多节点调度。

---

## 9. vLLM Runtime

### 9.1 启动命令

```bash
docker run --rm --gpus all --ipc=host \
  --name nta-vllm-current \
  -p 18000:8000 \
  -v /data/model-cache:/models:ro \
  vllm/vllm-openai:latest \
  --model /models/${ARTIFACT_ID} \
  --served-model-name ${MODEL_CODE} \
  --tensor-parallel-size 8 \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.9 \
  --max-model-len ${MAX_MODEL_LEN} \
  --enable-prefix-caching \
  --api-key ${RUNTIME_API_KEY}
```

### 9.2 Provider 注册

部署成功后，控制面创建或更新 Provider：

```text
Provider:
  name: Local Inference Runtime
  provider_type: openai-compatible
  api_format: chat-completions
  base_url: http://{h20-host}:18000/v1
```

并创建或更新 Model：

```text
Model:
  name: artifact display name
  model_code: served_model_name
  provider_id: Local Inference Runtime
  source: deployment
  status: active
```

---

## 10. 评测集成

### 10.1 评测入口

训练产物详情页应提供：

```text
部署
部署并评测
仅评测当前 active 部署
```

### 10.2 评测流程

```text
用户选择 artifact
  -> 若未部署，先创建 deployment
  -> deployment active 后创建 EvaluationRun
  -> EvaluationRun 使用部署后的 Model Provider
  -> 评测结果关联 artifact_id / deployment_id
```

### 10.3 展示视角

Artifact 详情页展示：

- 训练来源
- COS 路径
- 部署状态
- 当前是否 active
- 最近一次部署日志
- 所有关联评测结果
- benchmark 分数趋势

这样用户可以直接比较不同 checkpoint / final model 的评测表现。

---

## 11. 状态与可观测性

### 11.1 部署事件

部署详情页至少展示：

- `deployment.created`
- `previous_runtime.stopping`
- `artifact.download.started`
- `artifact.download.progress`
- `artifact.verify.completed`
- `runtime.starting`
- `runtime.healthcheck.ok`
- `smoke_test.completed`
- `registry.synced`
- `deployment.active`
- `deployment.failed`

### 11.2 进度定义

```text
queued              0
stopping_previous   10
downloading         20-60
verifying           65
starting            75
warming             85
smoke_testing       92
active              100
failed              100
cancelled           100
```

### 11.3 健康检查

部署成功前必须通过：

1. vLLM `/health`
2. OpenAI-compatible `/v1/models`
3. 简单 chat completion smoke test

---

## 12. 实施计划

### Phase 1：训练产物登记

- 新增 `training_runs` 或外部训练结果导入能力。
- 新增 `model_artifacts`。
- 支持从 COS prefix inspect artifact。
- 前端展示训练产物列表和详情。

### Phase 2：单模型部署

- 新增 `inference_nodes`、`model_deployments`、`deployment_events`。
- 实现 Infer Agent。
- 实现停止旧 vLLM、下载 artifact、启动新 vLLM。
- 部署成功后同步 Model Provider。

### Phase 3：部署可观测

- 前端展示部署事件流。
- 支持取消、重试、回滚。
- 支持查看 Infer Agent 心跳和节点资源。

### Phase 4：部署后评测

- Artifact 详情页支持“部署并评测”。
- EvaluationRun 关联 artifact / deployment。
- 展示 checkpoint 间评测趋势。

### Phase 5：增强能力

- 本地缓存 LRU。
- 断点续传。
- manifest 规范化。
- 部署前自动 smoke benchmark。

---

## 13. 后续演进

当前 MVP 稳定后，再考虑：

- 同机多个小模型并存。
- 蓝绿 slot 降低切换停机时间。
- LoRA / adapter 常驻 base model 切换。
- 多 H20 节点调度。
- Kubernetes / Ray Serve / vLLM Production Stack。
- 统一推理 Gateway。

这些能力都可以在当前数据模型上扩展，但不应进入第一阶段。
