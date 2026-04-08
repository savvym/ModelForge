# 网络探针系统设计文档

> NTA Platform — 分布式探针评测子系统  
> 版本：1.0 | 2026-04-03

---

## 目录

1. [业务背景](#1-业务背景)
2. [核心概念](#2-核心概念)
3. [系统架构总览](#3-系统架构总览)
4. [数据模型设计](#4-数据模型设计)
5. [API 设计](#5-api-设计)
6. [Temporal 工作流设计](#6-temporal-工作流设计)
7. [Probe Agent 设计](#7-probe-agent-设计)
8. [对比引擎设计](#8-对比引擎设计)
9. [前端交互设计](#9-前端交互设计)
10. [存储与工件管理](#10-存储与工件管理)
11. [安全设计](#11-安全设计)
12. [部署方案](#12-部署方案)
13. [实施计划](#13-实施计划)
14. [开放问题](#14-开放问题)

---

## 1. 业务背景

### 1.1 问题

同一个 Provider API（如 OpenAI、Anthropic），从不同地域、不同运营商发起请求，可能得到截然不同的结果：

| 差异维度 | 现象 | 可能原因 |
|---------|------|---------|
| **延迟差异** | 北京 320ms vs 弗吉尼亚 45ms | 物理距离、CDN 路由 |
| **模型路由差异** | 返回的 `system_fingerprint` 不一致 | Provider 按地域分流到不同 GPU 集群 |
| **输出质量差异** | 同 prompt + seed，某些地区得分更低 | 可能路由到较小模型或降级版本 |
| **限流策略差异** | 某些 IP 段更容易触发 429 | 按 IP / ASN 的差异化限流 |
| **内容审核差异** | 同一内容某些地区被拒绝 | 地域合规过滤 |

**核心问题**：同 prompt 同 provider，不同来源的请求，拿到的结果有没有区别？

### 1.2 目标

构建一套分布式探针系统，作为 NTA Platform 的子模块，实现：

1. 在多个网络观测点部署轻量 Probe Agent
2. 用同一 benchmark 从各观测点同时调用同一 Provider API
3. 采集评测分数 + 网络元数据（延迟、DNS、TLS、服务器 IP 等）
4. 跨 Probe 对比，输出退化分析报告

### 1.3 与现有系统的关系

探针系统**不另起炉灶**，而是构建在 evaluation_v2 之上：

```
现有 evaluation_v2                           新增 probe 层
┌─────────────────────────┐          ┌──────────────────────────┐
│ EvalSpec / EvalSuite    │←─复用──→ │ ProbeRun.target_ref      │
│ EvaluationRun / RunItem │←─委托──→ │ ProbeRunItem → EvalRun   │
│ compiler.py             │←─复用──→ │ 编译 probe 任务的 plan   │
│ EvalScopeBuiltinExecutor│←─抽取──→ │ Probe Agent 直接使用     │
│ CanonicalExecutionResult│←─复用──→ │ Probe 上报的标准格式     │
│ S3 artifact pipeline    │←─复用──→ │ Probe 结果存储          │
│ Temporal workflows      │←─模式──→ │ ProbeRunWorkflow 参考    │
└─────────────────────────┘          └──────────────────────────┘
```

---

## 2. 核心概念

### 2.1 Probe Agent（探针代理）

部署在特定网络观测点上的轻量 Python 守护进程。它：

1. **启动时**自动探测自身网络身份（IP、ISP、地理位置、ASN）
2. 向控制面**注册**并定期发送心跳
3. **轮询**控制面领取评测任务
4. 本地运行 evalscope benchmark，调用目标 LLM API
5. 将评测结果 + 网络元数据**回传**给控制面

与传统评测的本质区别：Probe 的身份（IP、地域、ASN）不是运维信息，而是**实验的核心自变量**。

### 2.2 网络观测点（VantagePoint）

```python
@dataclass
class VantagePoint:
    probe_id:     UUID
    ip_address:   str          # 公网出口 IP
    isp:          str          # 运营商，如 "中国电信"、"AWS"
    asn:          int          # 自治系统号，如 AS4134
    region:       str          # 地域，如 "cn-beijing"、"us-east-1"
    country:      str          # ISO 3166-1，如 "CN"、"US"
    city:         str | None   # 城市
    network_type: str          # cloud | residential | mobile | vpn | proxy
    tags:         list[str]    # 自定义标签，如 ["aliyun", "education-network"]
```

### 2.3 ProbeRun（对比型评测）

一个 ProbeRun 是顶层实体，将**同一 benchmark + 同一目标模型**分发给多个 Probe 同时执行，然后对比结果：

```
ProbeRun "GPT-4o 中国网络测试"
 ├── target: EvalSuite "network-probe-standard" v1
 ├── model: gpt-4o (via OpenAI API)
 ├── probe_filter: { regions: ["cn-*"], tags: ["telecom"] }
 ├── repetitions: 3
 │
 ├── ProbeRunItem (beijing-ct-01, rep #1) → EvaluationRun #A
 ├── ProbeRunItem (beijing-ct-01, rep #2) → EvaluationRun #B
 ├── ProbeRunItem (beijing-ct-01, rep #3) → EvaluationRun #C
 ├── ProbeRunItem (shanghai-cu-01, rep #1) → EvaluationRun #D
 ├── ...
 └── ComparisonReport
      ├── score_diff: 北京 82.3% vs 弗吉尼亚 88.0%
      ├── latency_diff: 北京 320ms vs 弗吉尼亚 45ms
      ├── routing_diff: 不同地区连接了不同服务器 IP
      └── degradation: MODERATE (p=0.003)
```

### 2.4 ProbeTask（任务领取单元）

ProbeRunItem 在数据库侧记录实验维度，ProbeTask 是面向 Probe Agent 的可领取工作单元：

```python
@dataclass
class ProbeTask:
    id:            UUID
    probe_run_id:  UUID
    probe_id:      UUID
    item_id:       UUID             # ProbeRunItem.id
    status:        str              # unclaimed | claimed | executing | completed | failed
    item_plan:     dict             # CompiledRunItemPlan 序列化
    model_binding: dict             # ModelBindingSnapshot 序列化
    api_endpoint:  str              # 目标 LLM API 的 base URL
    claimed_at:    datetime | None
    started_at:    datetime | None
    finished_at:   datetime | None
```

---

## 3. 系统架构总览

```
                         ┌──────────────────────────────────────────────┐
                         │             NTA Platform Backend              │
                         │                                              │
                         │  ┌────────────────────────────────────────┐  │
                         │  │       Probe Coordination Service        │  │
                         │  │  - Probe 注册 & 心跳                    │  │
                         │  │  - ProbeRun 生命周期管理                 │  │
                         │  │  - Task 派发 & 领取                     │  │
                         │  │  - 结果聚合                             │  │
                         │  └──────────────┬─────────────────────────┘  │
                         │                 │                            │
                         │  ┌──────────────┴─────────────────────────┐  │
                         │  │        Temporal Workflows               │  │
                         │  │  - ProbeRunWorkflow (编排)              │  │
                         │  │  - 复用 evaluation_v2 的 activity 模式   │  │
                         │  └──────────────┬─────────────────────────┘  │
                         │                 │                            │
                         │  ┌──────────────┴─────────────────────────┐  │
                         │  │        Comparison Engine                │  │
                         │  │  - 跨 Probe 分数对比                    │  │
                         │  │  - 统计显著性检验                        │  │
                         │  │  - 退化分级 & 异常检测                   │  │
                         │  │  - 延迟 / Token / 路由分析               │  │
                         │  └────────────────────────────────────────┘  │
                         └───────────────────┬──────────────────────────┘
                                             │ REST API (pull-based)
                      ┌──────────────────────┼──────────────────────────┐
                      │                      │                          │
               ┌──────┴──────┐      ┌────────┴───────┐      ┌──────────┴────────┐
               │ Probe Agent │      │  Probe Agent   │      │   Probe Agent     │
               │ 北京 电信    │      │  上海 联通     │      │   US-East AWS     │
               │             │      │                │      │                   │
               │ ┌─────────┐ │      │ ┌────────────┐ │      │ ┌───────────────┐ │
               │ │evalscope│ │      │ │ evalscope  │ │      │ │   evalscope   │ │
               │ └────┬────┘ │      │ └─────┬──────┘ │      │ └───────┬───────┘ │
               │      ▼      │      │       ▼        │      │         ▼         │
               │  LLM API    │      │   LLM API      │      │     LLM API       │
               └─────────────┘      └────────────────┘      └───────────────────┘
```

### 3.1 关键设计决策

| 决策点 | 选择 | 理由 |
|-------|------|------|
| 执行位置 | Probe 端本地执行 | API 调用必须从 Probe IP 发出，否则失去地域对比意义 |
| 通信模式 | Pull-based 轮询 | 简单可靠，Probe 无需公网入站端口，穿透 NAT/防火墙 |
| 与 eval_v2 关系 | 委托，非复制 | ProbeRunItem 委托给 EvaluationRun，零重复评测基础设施 |
| Probe 并发 | 1 task/probe | Benchmark 需要独占资源，避免并发任务相互干扰 |
| 工作流引擎 | Temporal | 复用现有基础设施，与 evaluation_v2 一致 |

---

## 4. 数据模型设计

### 4.1 新增表

#### `probes` — Probe 注册表

```python
class Probe(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "probes"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id:     Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name:           Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    display_name:   Mapped[str] = mapped_column(String(255), nullable=False)
    status:         Mapped[str] = mapped_column(String(32), nullable=False, default="offline")
        # online | offline | disabled
    ip_address:     Mapped[str | None] = mapped_column(String(64), nullable=True)
    isp:            Mapped[str | None] = mapped_column(String(120), nullable=True)
    asn:            Mapped[int | None] = mapped_column(Integer, nullable=True)
    region:         Mapped[str | None] = mapped_column(String(64), nullable=True)
    country:        Mapped[str | None] = mapped_column(String(8), nullable=True)
    city:           Mapped[str | None] = mapped_column(String(120), nullable=True)
    network_type:   Mapped[str] = mapped_column(String(32), nullable=False, default="cloud")
        # cloud | residential | mobile | vpn | proxy
    tags_json:      Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    agent_version:  Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_info:    Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # { os, python_version, evalscope_version, ... }
    last_heartbeat: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_token_hash:Mapped[str | None] = mapped_column(String(255), nullable=True)
```

#### `probe_heartbeats` — 心跳日志

```python
class ProbeHeartbeat(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "probe_heartbeats"

    probe_id:        Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("probes.id", ondelete="CASCADE"), index=True)
    ip_address:      Mapped[str] = mapped_column(String(64), nullable=False)
    network_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # { dns_resolve_ms, tcp_connect_ms, ping_rtt_ms, ... }
    agent_status:    Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # { cpu_usage, memory_usage, active_tasks, ... }
    created_at:      Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
```

#### `probe_runs` — 对比型评测运行

```python
class ProbeRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "probe_runs"

    project_id:           Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name:                 Mapped[str] = mapped_column(String(255), nullable=False)
    description:          Mapped[str | None] = mapped_column(Text, nullable=True)
    status:               Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
        # queued | dispatching | running | completed | failed | cancelled

    # 评测目标 — 复用现有 EvalSpec/EvalSuite
    target_ref_json:      Mapped[dict] = mapped_column(JSONB, nullable=False)
        # EvaluationTargetRef 序列化: { kind, name, version, item_keys }
    model_id:             Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    model_name:           Mapped[str | None] = mapped_column(String(255), nullable=True)
    judge_policy_id:      Mapped[PythonUUID | None] = mapped_column(UUID, ForeignKey("judge_policies.id", ondelete="SET NULL"), nullable=True)
    overrides_json:       Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Probe 选择
    probe_filter_json:    Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # { probe_ids, regions, isps, tags, network_types, exclude_probe_ids }
    repetitions:          Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # 编排
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # 结果
    comparison_report_uri:Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json:         Mapped[dict | None] = mapped_column(JSONB, nullable=True)
        # DegradationReport 的快速访问摘要

    # 进度
    progress_total:       Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    progress_done:        Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_code:           Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message:        Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at:           Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at:          Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items = relationship("ProbeRunItem", back_populates="probe_run", cascade="all, delete-orphan")
```

#### `probe_run_items` — 每个 (Probe, repetition) 的运行记录

```python
class ProbeRunItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "probe_run_items"
    __table_args__ = (UniqueConstraint("probe_run_id", "probe_id", "repetition"),)

    probe_run_id:         Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("probe_runs.id", ondelete="CASCADE"), index=True)
    probe_id:             Mapped[PythonUUID] = mapped_column(UUID, ForeignKey("probes.id", ondelete="CASCADE"), index=True)
    repetition:           Mapped[int] = mapped_column(Integer, nullable=False)
    status:               Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
        # pending | unclaimed | claimed | executing | completed | failed

    # 委托给 evaluation_v2 — 实际评测由 EvaluationRun 完成
    evaluation_run_id:    Mapped[PythonUUID | None] = mapped_column(UUID, ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True)

    # 执行时冻结的观测点快照
    vantage_snapshot:     Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # VantagePoint 序列化

    # 网络元数据（执行前后各采集一次）
    pre_network_metrics:  Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    post_network_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
        # { dns_resolve_ms, tcp_connect_ms, tls_handshake_ms, ttfb_ms,
        #   ping_rtt_ms, traceroute_hops, packet_loss_pct, resolved_ip }

    # 快速访问结果（反范式，从 EvaluationRun 提取）
    score:                Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_avg_ms:       Mapped[float | None] = mapped_column(Float, nullable=True)
    error_rate:           Mapped[float | None] = mapped_column(Float, nullable=True)
    token_count_avg:      Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 模型指纹
    model_fingerprint:    Mapped[dict | None] = mapped_column(JSONB, nullable=True)
        # { model_ids_returned, system_fingerprints, server_ips_seen }

    # 任务领取信息
    plan_json:            Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
        # CompiledRunItemPlan + ModelBindingSnapshot
    claimed_at:           Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at:           Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at:          Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code:           Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message:        Mapped[str | None] = mapped_column(String(500), nullable=True)

    probe_run = relationship("ProbeRun", back_populates="items")
```

### 4.2 ER 关系图

```
projects ──1:N──→ probes
projects ──1:N──→ probe_runs

probe_runs ──1:N──→ probe_run_items
probes     ──1:N──→ probe_run_items
probes     ──1:N──→ probe_heartbeats

probe_run_items ──1:1──→ evaluation_runs  (委托执行)

probe_runs.target_ref_json ──引用──→ eval_specs / eval_suites
probe_runs.model_id        ──引用──→ models
probe_runs.judge_policy_id ──引用──→ judge_policies
```

### 4.3 数据库迁移

新增迁移文件 `0006_probe_system.py`：

```python
# backend/migrations/versions/0006_probe_system.py
"""Create probe system tables: probes, probe_heartbeats, probe_runs, probe_run_items"""

def upgrade():
    op.create_table("probes", ...)
    op.create_table("probe_heartbeats", ...)
    op.create_table("probe_runs", ...)
    op.create_table("probe_run_items", ...)
    op.create_index("ix_probe_heartbeats_probe_id_created_at", ...)
    op.create_index("ix_probe_run_items_status", ...)

def downgrade():
    op.drop_table("probe_run_items")
    op.drop_table("probe_runs")
    op.drop_table("probe_heartbeats")
    op.drop_table("probes")
```

---

## 5. API 设计

### 5.1 Probe Agent 通信 API（供 Agent 调用）

```
POST   /api/v2/probes/register              # 注册 / 重新注册
POST   /api/v2/probes/{probe_id}/heartbeat  # 心跳 + 指标上报
POST   /api/v2/probes/{probe_id}/tasks/claim  # 领取下一个任务
POST   /api/v2/probes/tasks/{item_id}/start    # 标记任务开始
POST   /api/v2/probes/tasks/{item_id}/progress # 进度更新
POST   /api/v2/probes/tasks/{item_id}/complete # 上传结果
POST   /api/v2/probes/tasks/{item_id}/fail     # 报告失败
```

#### 注册

```http
POST /api/v2/probes/register
Authorization: Bearer <probe-token>

{
    "name": "beijing-ct-01",
    "display_name": "北京电信 ECS #1",
    "location": {
        "ip_address": "47.93.xx.xx",
        "isp": "中国电信",
        "asn": 4134,
        "region": "cn-beijing",
        "country": "CN",
        "city": "北京",
        "network_type": "cloud"
    },
    "tags": ["aliyun", "ecs", "telecom"],
    "device_info": {
        "os": "Linux 5.15",
        "python_version": "3.11.7",
        "evalscope_version": "1.5.2",
        "agent_version": "0.1.0"
    },
    "capabilities": {
        "reachable_providers": ["openai", "anthropic", "dashscope"],
        "max_concurrent": 1
    }
}
```

**响应**:
```json
{
    "probe_id": "uuid",
    "status": "online",
    "poll_interval_s": 5,
    "heartbeat_interval_s": 15
}
```

#### 任务领取

```http
POST /api/v2/probes/{probe_id}/tasks/claim
Authorization: Bearer <probe-token>
```

**响应（有任务时）**:
```json
{
    "task": {
        "item_id": "uuid",
        "probe_run_id": "uuid",
        "probe_run_name": "GPT-4o 中国网络测试",
        "repetition": 1,
        "item_plan": { /* CompiledRunItemPlan */ },
        "model_binding": { /* ModelBindingSnapshot */ },
        "api_endpoint": "https://api.openai.com",
        "timeout_s": 7200
    }
}
```

**响应（无任务时）**:
```json
{ "task": null }
```

#### 结果上报

```http
POST /api/v2/probes/tasks/{item_id}/complete
Authorization: Bearer <probe-token>
Content-Type: application/json

{
    "vantage_snapshot": { /* VantagePoint */ },
    "pre_network_metrics": {
        "target_host": "api.openai.com",
        "dns_resolve_ms": 12.3,
        "tcp_connect_ms": 45.6,
        "tls_handshake_ms": 89.1,
        "first_byte_ms": 180.5,
        "ping_rtt_ms": 35.2,
        "resolved_ip": "104.18.1.1",
        "packet_loss_pct": 0.0
    },
    "post_network_metrics": { /* 同上 */ },

    "execution_result": {
        "metrics": [
            { "metric_name": "accuracy", "metric_value": 0.823, "metric_scope": "overall" }
        ],
        "samples": [ /* CanonicalSample[] */ ],
        "artifacts": [ /* 本地路径或 base64 */ ]
    },

    "model_fingerprint": {
        "model_ids_returned": ["gpt-4o-2024-08-06"],
        "system_fingerprints": ["fp_abc123", "fp_def456"],
        "server_ips_seen": ["104.18.1.1", "104.18.1.2"]
    },

    "request_level_stats": {
        "total_requests": 200,
        "error_count": 4,
        "rate_limited_count": 2,
        "latency_p50_ms": 320,
        "latency_p99_ms": 890,
        "avg_tokens_per_response": 145
    }
}
```

### 5.2 管理 API（供前端调用）

```
GET    /api/v2/probes                        # 列出所有 Probe
GET    /api/v2/probes/{probe_id}             # Probe 详情 + 近期心跳
PATCH  /api/v2/probes/{probe_id}             # 更新标签/状态
DELETE /api/v2/probes/{probe_id}             # 注销 Probe

GET    /api/v2/probe-runs                    # 列出 ProbeRun
POST   /api/v2/probe-runs                    # 创建 ProbeRun
GET    /api/v2/probe-runs/{id}               # 详情 + 对比报告
POST   /api/v2/probe-runs/{id}/cancel        # 取消
DELETE /api/v2/probe-runs/{id}               # 删除

GET    /api/v2/probe-runs/{id}/comparison    # 获取对比报告
GET    /api/v2/probe-runs/{id}/items         # 列出所有 ProbeRunItem
GET    /api/v2/probe-runs/{id}/items/{item_id}  # 单个 item 详情
```

#### 创建 ProbeRun

```http
POST /api/v2/probe-runs

{
    "name": "GPT-4o 中国网络退化测试",
    "description": "对比中国大陆三大运营商 vs 海外节点",
    "target": {
        "kind": "suite",
        "name": "network-probe-standard",
        "version": "v1"
    },
    "model_id": "uuid",
    "judge_policy_id": null,
    "probe_filter": {
        "regions": ["cn-beijing", "cn-shanghai", "us-east-1", "ap-northeast-1"],
        "tags": [],
        "network_types": ["cloud"],
        "exclude_probe_ids": []
    },
    "repetitions": 3,
    "overrides": {
        "temperature": 0,
        "seed": 42
    }
}
```

### 5.3 API Router 文件

```
backend/src/nta_backend/api/routers/
├── probes.py                # Probe Agent 通信 + 管理 API
└── probe_runs.py            # ProbeRun CRUD + 对比报告
```

---

## 6. Temporal 工作流设计

### 6.1 ProbeRunWorkflow

```python
# backend/src/nta_backend/workflows/probe_run.py

@dataclass
class ProbeRunWorkflowInput:
    probe_run_id: str

@workflow.defn(name="probe_run_workflow")
class ProbeRunWorkflow:
    """
    编排一次对比型探针评测。

    与 EvaluationRunWorkflow 的核心区别：
    - EvaluationRunWorkflow 在 Temporal Worker 内直接执行 evalscope
    - ProbeRunWorkflow 只负责派发和等待，实际执行在远端 Probe Agent 上

    流程：
    1. 解析 probe_filter → 找到参与的 Probe 列表
    2. 编译 item_plan（复用 evaluation_v2.compiler）
    3. 创建 ProbeRunItems，状态置为 unclaimed
    4. 等待所有 Probe 领取并完成任务（超时控制）
    5. 运行对比分析引擎
    6. 生成 DegradationReport
    """

    @workflow.run
    async def run(self, input: ProbeRunWorkflowInput) -> dict:
        # Step 1: 解析参与的 Probe
        probe_ids = await workflow.execute_activity(
            resolve_probe_participants,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 2: 编译并派发任务
        await workflow.execute_activity(
            compile_and_dispatch_probe_tasks,
            args=[input.probe_run_id, probe_ids],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 3: 等待完成（Probe 自主领取执行）
        await workflow.execute_activity(
            wait_for_probe_completion,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(hours=24),
            heartbeat_timeout=timedelta(minutes=5),
        )

        # Step 4: 对比分析
        await workflow.execute_activity(
            analyze_probe_results,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(minutes=30),
        )

        return {"probe_run_id": input.probe_run_id, "status": "completed"}
```

### 6.2 Activities

```python
# backend/src/nta_backend/activities/probe_run.py

@activity.defn
async def resolve_probe_participants(probe_run_id: str) -> list[str]:
    """根据 probe_filter 查询在线且匹配的 Probe 列表"""
    ...

@activity.defn
async def compile_and_dispatch_probe_tasks(probe_run_id: str, probe_ids: list[str]):
    """
    1. 调用 compile_run_request() 生成 CompiledRunPlan
    2. 为每个 (probe, repetition) 创建 ProbeRunItem
    3. 将 item_plan 写入 plan_json，status 置为 unclaimed
    """
    ...

@activity.defn
async def wait_for_probe_completion(probe_run_id: str):
    """
    轮询检查所有 ProbeRunItem 的状态。
    每 30s 检查一次，同时发送 heartbeat 给 Temporal。
    超时或全部 item 终态时返回。
    """
    while True:
        items = await db.query_probe_run_items(probe_run_id)
        all_done = all(item.status in ("completed", "failed") for item in items)
        if all_done:
            break
        activity.heartbeat()
        await asyncio.sleep(30)

@activity.defn
async def analyze_probe_results(probe_run_id: str):
    """
    1. 收集所有 ProbeRunItem 的分数和网络指标
    2. 调用 ComparisonEngine.analyze()
    3. 将 DegradationReport 序列化存储到 S3
    4. 更新 probe_run.summary_json 和 comparison_report_uri
    """
    ...
```

### 6.3 与现有工作流的复用关系

```
EvaluationRunWorkflow                ProbeRunWorkflow
├── list_items (activity)            ├── resolve_probes (activity)
├── for item: start_child_workflow   ├── compile_and_dispatch (activity)
│   └── execute item (activity)      │   └── 复用 compile_run_request()
├── aggregate (activity)             ├── wait_for_completion (activity)
                                     │   └── Probe Agent 外部执行
                                     └── analyze_results (activity)
                                         └── ComparisonEngine (新增)
```

---

## 7. Probe Agent 设计

### 7.1 包结构

Probe Agent 作为**独立 Python 包**发布，与后端共享部分 schema 定义：

```
nta-probe-agent/
├── pyproject.toml               # 依赖: evalscope, httpx, click
├── src/
│   └── nta_probe_agent/
│       ├── __init__.py
│       ├── cli.py               # CLI 入口: probe-agent run | register | status
│       ├── agent.py             # ProbeAgent 主循环
│       ├── config.py            # 配置加载 (env / yaml / CLI flags)
│       ├── client.py            # 控制面 HTTP 客户端
│       ├── executor.py          # evalscope 执行包装
│       ├── network.py           # VantagePoint 探测 + NetworkMetrics 采集
│       ├── instrument.py        # HTTP 层插桩，采集请求级网络指标
│       └── models.py            # 本地数据模型
├── Dockerfile
└── deploy/
    ├── docker-compose.yml       # 多地域部署模板
    └── probe-agent.yaml.example # 配置示例
```

### 7.2 Agent 主循环

```python
class ProbeAgent:
    """
    生命周期：
    1. 启动 → 探测网络身份 → 向控制面注册
    2. 后台启动心跳协程
    3. 主循环：轮询 → 领取任务 → 执行 → 上报 → 继续轮询
    """

    async def run(self):
        self.vantage = await self.detect_vantage_point()
        await self.register()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.heartbeat_loop())
            tg.create_task(self.poll_loop())

    async def poll_loop(self):
        while self.running:
            task = await self.client.claim_task(self.probe_id)
            if task:
                await self.execute_task(task)
            else:
                await asyncio.sleep(self.config.poll_interval)

    async def execute_task(self, task: ProbeTask):
        await self.client.start_task(task.item_id)

        try:
            # 1. 采集执行前网络指标
            pre_net = await self.collect_network_metrics(task.api_endpoint)

            # 2. 运行 evalscope
            result = await self.run_evalscope(task.item_plan, task.model_binding)

            # 3. 采集执行后网络指标
            post_net = await self.collect_network_metrics(task.api_endpoint)

            # 4. 上报结果
            await self.client.complete_task(
                item_id=task.item_id,
                vantage_snapshot=self.vantage.to_dict(),
                pre_network_metrics=pre_net,
                post_network_metrics=post_net,
                execution_result=result,
                model_fingerprint=result.model_fingerprint,
            )
        except Exception as e:
            await self.client.fail_task(task.item_id, error=str(e))
```

### 7.3 网络探测

```python
# nta_probe_agent/network.py

async def detect_vantage_point() -> VantagePoint:
    """
    自动探测 Probe 的网络身份：
    1. 调用 ipinfo.io 获取 IP / ISP / ASN / Geo
    2. 可通过配置覆盖（已知部署时）
    """
    info = await httpx.AsyncClient().get("https://ipinfo.io/json")
    data = info.json()
    return VantagePoint(
        ip_address=data["ip"],
        isp=data.get("org", ""),
        asn=parse_asn(data.get("org", "")),
        region=data.get("region", ""),
        country=data.get("country", ""),
        city=data.get("city"),
    )

async def collect_network_metrics(target_host: str) -> NetworkMetrics:
    """
    测量到目标 API 的网络指标：
    - DNS 解析耗时
    - TCP 握手耗时
    - TLS 握手耗时
    - TTFB（首字节时间）
    - Ping RTT
    - 实际解析到的服务器 IP
    """
    ...
```

### 7.4 HTTP 插桩

对 evalscope 的 HTTP 调用进行插桩，采集请求级元数据：

```python
# nta_probe_agent/instrument.py

class InstrumentedHttpClient:
    """
    包装 httpx.AsyncClient，透明采集每次 API 调用的：
    - 延迟 (total, ttfb)
    - 服务器 IP
    - 响应头 (x-ratelimit-*, cf-ray, server, system_fingerprint)
    - HTTP 状态码
    """

    def __init__(self, base_client: httpx.AsyncClient):
        self.base_client = base_client
        self.records: list[RequestRecord] = []

    async def send(self, request, **kwargs):
        start = time.monotonic()
        response = await self.base_client.send(request, **kwargs)
        elapsed = (time.monotonic() - start) * 1000

        self.records.append(RequestRecord(
            latency_ms=elapsed,
            server_ip=response.extensions.get("network_stream", {}).get("peer_address"),
            http_status=response.status_code,
            response_headers=dict(response.headers),
            model_id_returned=response.json().get("model"),
            system_fingerprint=response.json().get("system_fingerprint"),
        ))
        return response
```

### 7.5 配置

```yaml
# probe-agent.yaml
control_plane:
  url: https://nta.example.com
  token: ${NTA_PROBE_TOKEN}

agent:
  name: "beijing-ct-01"
  display_name: "北京电信 ECS #1"
  poll_interval: 5s
  heartbeat_interval: 15s
  max_concurrent_tasks: 1
  task_timeout: 2h

network:
  detect_vantage: true
  overrides:
    region: "cn-beijing"
    isp: "中国电信"
    network_type: "cloud"
    tags: ["aliyun", "ecs"]
  collect_traceroute: false

evalscope:
  cache_dir: ~/.nta-probe/benchmarks
  log_level: INFO
```

### 7.6 部署模式

| 模式 | 描述 | 适用场景 |
|-----|------|---------|
| **Docker 容器** | `docker run nta/probe-agent` | 云主机、K8s |
| **Standalone** | `probe-agent run` 直接进程 | 物理机、开发测试 |
| **Ephemeral** | `probe-agent run-once --task-id=xxx` | CI/CD、Serverless |

---

## 8. 对比引擎设计

### 8.1 DegradationReport 结构

```python
@dataclass
class DegradationReport:
    """跨 Probe 对比分析的输出"""

    # 总结论
    degradation_detected: bool
    confidence: float                    # 0.0 ~ 1.0
    severity: str                        # none | mild | moderate | severe

    # 逐 Probe 摘要
    probe_scores: list[ProbeScoreSummary]
    # ProbeScoreSummary:
    #   probe_id, probe_name, vantage, avg_score, std_dev,
    #   sample_count, avg_latency_ms, error_rate, score_delta_from_best

    # 两两对比
    pairwise: list[PairwiseComparison]
    #   probe_a, probe_b, score_diff, p_value, significant, effect_size

    # 维度分组
    by_region:       dict[str, RegionSummary]
    by_isp:          dict[str, ISPSummary]
    by_network_type: dict[str, NetworkTypeSummary]

    # 异常标记
    anomalies: list[Anomaly]
    #   probe_id, anomaly_type, description, severity
    #   anomaly_type: "score_outlier" | "high_error_rate" | "model_switch" |
    #                 "routing_anomaly" | "rate_limit_spike"
```

### 8.2 对比引擎实现

```python
# backend/src/nta_backend/evaluation_v2/comparison.py

class ComparisonEngine:
    """跨 Probe 对比分析引擎"""

    def analyze(self, probe_run: ProbeRun, items: list[ProbeRunItem]) -> DegradationReport:
        """
        分析流水线：
        1. 收集所有 item 的分数和网络指标
        2. 按 Probe 分组聚合
        3. 两两统计检验 (Mann-Whitney U + Bonferroni 校正)
        4. 效应量计算 (Cohen's d)
        5. 退化严重度分级
        6. 异常检测
        """
        ...

    def _statistical_test(self, scores_a: list[float], scores_b: list[float]) -> PairwiseComparison:
        """
        非参数检验（分数分布可能不正态）：
        - Mann-Whitney U 检验
        - Bootstrap 置信区间
        - Bonferroni 多重比较校正
        """
        ...

    def _classify_severity(self, delta: float, p_value: float) -> str:
        """
        严重度矩阵：
        |delta| < 2%  and p > 0.05  → "none"
        |delta| < 5%  and p < 0.05  → "mild"
        |delta| < 10% and p < 0.01  → "moderate"
        |delta| >= 10%              → "severe"
        """
        ...

    def _detect_anomalies(self, items: list[ProbeRunItem]) -> list[Anomaly]:
        """
        检测异常模式：
        - 分数离群 (Z-score > 2)
        - 高错误率 (> 5%)
        - 模型切换 (system_fingerprint 不一致)
        - 路由异常 (server_ip 大幅偏离)
        - 限流突增 (rate_limited_count 显著高于其他 Probe)
        """
        ...
```

### 8.3 关键对比指标

| 指标 | 衡量内容 | 退化信号 |
|------|---------|---------|
| **Score (准确率)** | Benchmark 得分 | 核心智力指标 |
| **Latency (TTFB)** | 首 Token 延迟 | 路由 / 限流指标 |
| **Latency (Total)** | 完整响应延迟 | 模型版本指标 |
| **Token Count** | 输出 Token 长度 | 截断指标 |
| **Error Rate** | 失败 API 调用占比 | 封锁 / 限流指标 |
| **Model Fingerprint** | system_fingerprint 是否一致 | 模型切换指标 |
| **Server IP** | 实际连接的服务器 IP | CDN 路由差异 |
| **Response Consistency** | 同 prompt 同 seed 的输出一致性 | 模型变体指标 |

### 8.4 推荐 Benchmark Suite

为退化检测场景定制 `network-probe-standard` Suite：

| Benchmark | 样本数 | 选择理由 |
|-----------|--------|---------|
| **MMLU (mini)** | 100 | 知识广度测试，金标准 |
| **GSM8K (mini)** | 50 | 数学推理，对模型质量高度敏感 |
| **HellaSwag (mini)** | 100 | 常识推理，弱模型显著下降 |
| **NTA-Network-Bench** | 50 | 自定义题目，最大化区分度 |

要求：快速（几百样本以内）、确定性高（低重复方差）、敏感度高（能区分强弱模型）。

---

## 9. 前端交互设计

### 9.1 新增页面

```
frontend/app/(console)/
├── probes/                          # Probe 管理
│   └── page.tsx                     # Probe 列表 + 状态监控
├── probe-runs/                      # ProbeRun 管理
│   ├── page.tsx                     # ProbeRun 列表
│   └── [id]/
│       └── page.tsx                 # ProbeRun 详情 + 对比报告
```

### 9.2 新增组件

```
frontend/features/probe/
├── api.ts                           # HTTP 调用
├── components/
│   ├── probe-list-table.tsx         # Probe 注册列表
│   ├── probe-detail-panel.tsx       # Probe 详情（位置、心跳、历史）
│   ├── probe-run-create-form.tsx    # 创建 ProbeRun 表单
│   ├── probe-run-list-table.tsx     # ProbeRun 列表
│   ├── probe-run-detail-panel.tsx   # ProbeRun 详情
│   ├── comparison-report-view.tsx   # 对比报告可视化
│   ├── probe-score-chart.tsx        # 分数对比图表
│   ├── probe-latency-chart.tsx      # 延迟对比图表
│   └── probe-map-view.tsx           # 地图可视化（可选）
└── status.ts                        # 状态常量
```

### 9.3 TypeScript 类型

```typescript
// frontend/types/api.ts 新增

interface ProbeSummary {
  id: string;
  name: string;
  display_name: string;
  status: "online" | "offline" | "disabled";
  ip_address: string | null;
  isp: string | null;
  region: string | null;
  country: string | null;
  network_type: string;
  tags_json: string[];
  last_heartbeat: string | null;
}

interface ProbeRunSummary {
  id: string;
  name: string;
  status: string;
  model_name: string | null;
  probe_count: number;
  repetitions: number;
  degradation_severity: string | null;    // none | mild | moderate | severe
  progress_total: number | null;
  progress_done: number | null;
  created_at: string;
  finished_at: string | null;
}

interface ProbeRunDetail extends ProbeRunSummary {
  description: string | null;
  target_ref_json: EvaluationTargetRef;
  probe_filter_json: object;
  items: ProbeRunItemSummary[];
  comparison: DegradationReport | null;
}

interface ProbeRunItemSummary {
  id: string;
  probe_id: string;
  probe_name: string;
  repetition: number;
  status: string;
  score: number | null;
  latency_avg_ms: number | null;
  error_rate: number | null;
  vantage_snapshot: VantagePoint;
}

interface DegradationReport {
  degradation_detected: boolean;
  confidence: number;
  severity: string;
  probe_scores: ProbeScoreSummary[];
  pairwise: PairwiseComparison[];
  by_region: Record<string, RegionSummary>;
  anomalies: Anomaly[];
}
```

### 9.4 对比报告 Dashboard

```
┌────────────────────────────────────────────────────────────────┐
│  ProbeRun: "GPT-4o 中国网络退化测试"                            │
│  状态: COMPLETED    退化: MODERATE (p<0.01)                     │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  分数对比 (bar chart)                                   │    │
│  │  ███████████████████████  88.0%  US-East AWS (baseline) │    │
│  │  ██████████████████████   87.5%  Tokyo AWS              │    │
│  │  ████████████████████     84.1%  上海联通    -3.9%       │    │
│  │  ██████████████████       82.3%  北京电信    -5.7%  ⚠   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  延迟分布 (box plot)                                     │    │
│  │  US-East:  ├──┤ 30-80ms                                 │    │
│  │  Tokyo:    ├───┤ 150-250ms                              │    │
│  │  上海:     ├─────┤ 280-450ms                            │    │
│  │  北京:     ├──────┤ 300-890ms                           │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  异常发现                                               │    │
│  │  ⚠ 北京电信: 检测到 2 个不同的 system_fingerprint       │    │
│  │  ⚠ 北京电信: 限流次数 (3) 显著高于其他节点               │    │
│  │  ⚠ 中国大陆地区分数统计显著低于海外 (p=0.003, d=0.72)    │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌─ 详细数据表 ──────────────────────────────────────────┐    │
│  │  Probe        Score  StdDev  Latency_P50  Errors  δ    │    │
│  │  ─────────    ─────  ──────  ───────────  ──────  ──── │    │
│  │  US-East      88.0%  ±1.2%  45ms         0.2%   base  │    │
│  │  Tokyo        87.5%  ±1.1%  180ms        0.3%   -0.5% │    │
│  │  上海联通     84.1%  ±1.8%  320ms        1.3%   -3.9% │    │
│  │  北京电信     82.3%  ±2.1%  450ms        2.1%   -5.7% │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

---

## 10. 存储与工件管理

### 10.1 S3 存储路径

复用现有 `storage_layout.py` 的模式，新增 probe 前缀：

```
s3://nta-default/
└── projects/{project_id}/
    ├── evaluation-runs/              # 现有路径不变
    │   └── {run_id}/
    │       └── items/{item_key}/
    │
    └── probe-runs/                   # 新增
        └── {probe_run_id}/
            ├── comparison-report.json    # DegradationReport
            ├── comparison-report.html    # 可视化报告
            └── items/
                └── {probe_name}-rep{n}/
                    ├── execution-result.json
                    ├── network-metrics.json
                    ├── request-records.jsonl  # 逐条 API 调用记录
                    └── samples.jsonl
```

### 10.2 数据保留策略

| 数据类型 | 保留时间 | 存储位置 |
|---------|---------|---------|
| ProbeRun 元数据 | 永久 | PostgreSQL |
| ProbeRunItem 元数据 | 永久 | PostgreSQL |
| 心跳日志 | 30 天 | PostgreSQL (定期清理) |
| DegradationReport | 永久 | S3 |
| 逐条请求记录 | 90 天 | S3 (lifecycle policy) |
| 评测样本详情 | 跟随委托的 EvaluationRun | PostgreSQL + S3 |

---

## 11. 安全设计

### 11.1 认证

| 场景 | 机制 |
|------|------|
| Probe → 控制面 | Bearer Token（注册时由管理员生成，存 `probes.auth_token_hash`） |
| 前端 → API | 复用现有 JWT 认证 |
| Probe → LLM API | API Key 通过 `ModelBindingSnapshot` 下发 |

### 11.2 API Key 保护

**策略：Key-in-Plan**

Probe 通过 claim task 获取到 `model_binding`（含 `api_key`），直接用于调用 LLM API。

- 适用于**内部受信 Probe**
- API Key 在传输层使用 HTTPS 加密
- Probe 不持久化 API Key（任务完成后丢弃）
- 如果 Provider 支持，使用**短期 Scoped Token** 替代长期 Key

### 11.3 其他安全考虑

| 风险 | 缓解措施 |
|------|---------|
| 恶意 Probe 提交伪造结果 | Token 认证 + 结果分布校验（分数偏离过大触发告警） |
| Probe 被入侵 | 最小权限：只能 claim 自己的任务、只读 benchmark 数据 |
| 网络元数据泄露 | IP/ISP 数据限制在 project scope 内，不公开 |
| API Key 泄露 | 传输加密 + 内存中使用 + 用完即弃 |

---

## 12. 部署方案

### 12.1 控制面部署

控制面代码**内嵌在 NTA Backend** 中，不需要额外部署：

- 新增 API Router 注册到现有 FastAPI app
- 新增 Temporal Workflow 注册到现有 Worker
- 新增数据库表通过 Alembic 迁移创建

### 12.2 Probe Agent 部署

**方式一：Docker（推荐生产环境）**

```bash
# 北京 阿里云 ECS
docker run -d --name probe-beijing-ct \
  -e NTA_CONTROL_PLANE_URL=https://nta.example.com \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=beijing-ct-01 \
  nta/probe-agent:latest

# 弗吉尼亚 AWS EC2
docker run -d --name probe-us-east \
  -e NTA_CONTROL_PLANE_URL=https://nta.example.com \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=us-east-aws-01 \
  nta/probe-agent:latest
```

每个 Probe 约需 1 vCPU + 2 GB 内存，成本约 $5-15/月。

**方式二：直接运行**

```bash
pip install nta-probe-agent
probe-agent run --config probe-agent.yaml
```

### 12.3 多地域部署拓扑（建议初始）

```
┌─── 中国大陆 ────────────────┐  ┌─── 海外 ────────────────────┐
│ 北京   - 电信 (阿里云)      │  │ US-East   - AWS Virginia   │
│ 上海   - 联通 (腾讯云)      │  │ Tokyo     - AWS Tokyo      │
│ 广州   - 移动 (华为云)      │  │ Frankfurt - AWS Frankfurt  │
└─────────────────────────────┘  └─────────────────────────────┘
                  │                             │
                  └──────── NTA Platform ───────┘
                         (控制面 + Dashboard)
```

---

## 13. 实施计划

### Phase 1：基础框架（MVP）

**目标**：2-3 个手动部署的 Probe 跑通完整流程。

| 任务 | 文件 | 说明 |
|------|------|------|
| Probe 数据模型 | `models/probe.py` | Probe, ProbeHeartbeat, ProbeRun, ProbeRunItem |
| DB 迁移 | `migrations/versions/0006_probe_system.py` | 建表 |
| Probe 注册/心跳 API | `api/routers/probes.py` | register, heartbeat, list |
| Task claim/complete API | `api/routers/probes.py` | claim, start, complete, fail |
| ProbeRun CRUD | `api/routers/probe_runs.py` | create, list, detail |
| Probe Agent CLI | `nta-probe-agent/` | 独立包，最小可用 |
| 网络探测 | `nta_probe_agent/network.py` | IP/ISP/ASN 自动检测 |
| evalscope 抽取 | `evaluation_v2/execution/standalone.py` | 独立可调用的执行函数 |
| 简单对比 | 手动 | 各 Probe 平均分并排展示 |

**交付物**：能创建 ProbeRun → 2 个 Probe 领取执行 → 查看并排分数。

### Phase 2：分析引擎 + 自动化

**目标**：统计严谨的对比分析 + 一键运行。

| 任务 | 文件 | 说明 |
|------|------|------|
| ProbeRunWorkflow | `workflows/probe_run.py` | Temporal 全自动编排 |
| Probe Activities | `activities/probe_run.py` | resolve, dispatch, wait, analyze |
| ComparisonEngine | `evaluation_v2/comparison.py` | 统计检验 + 退化分级 |
| DegradationReport | `schemas/probe.py` | 报告数据结构 |
| 前端 Probe 列表 | `features/probe/` | Probe 状态监控 |
| 前端 ProbeRun 列表 | `features/probe/` | 创建、列表、详情 |
| 对比报告页面 | `features/probe/` | 图表 + 数据表 + 异常标记 |
| Probe 健康监控 | `services/probe_service.py` | 心跳超时 → 自动标记 offline |
| Docker 镜像 | `nta-probe-agent/Dockerfile` | 生产部署 |
| network-probe-standard | EvalSuite | 定制的退化检测 benchmark |

**交付物**：一键创建 ProbeRun → 自动执行 → 输出含 p 值和退化分级的对比报告。

### Phase 3：规模化 + 持续监控

**目标**：定时巡检 + 趋势分析 + 告警。

| 任务 | 说明 |
|------|------|
| 定时 ProbeRun | Cron 触发定期巡检 |
| 历史趋势分析 | 退化程度随时间变化图 |
| 告警规则 | 分数下降 > 阈值 → 通知 |
| Probe 自动注册 | 新 Probe 启动自动加入巡检 |
| A/B 网络路径测试 | 同 Probe 不同 DNS/VPN 出口对比 |
| 与 Leaderboard 集成 | 地域维度作为 Leaderboard 列 |

---

## 14. 开放问题

| # | 问题 | 选项 | 建议 |
|---|------|------|------|
| 1 | Benchmark 数据如何分发到 Probe？ | A) Docker 镜像内置 B) 首次执行时从 S3 下载 C) CDN 分发 | **B**，平衡镜像大小和数据新鲜度 |
| 2 | Probe Token 轮换频率？ | A) 每次 ProbeRun B) 固定有效期 C) 长期有效 | **B**，30 天轮换 |
| 3 | 退化基线如何定义？ | A) 最佳 Probe B) Provider 本地区域 C) 历史均值 | **A**，最佳 Probe 为 baseline，符合直觉 |
| 4 | Provider ToS 合规 | 多 IP 自动化 benchmark 是否违反 ToS？ | 需逐 Provider 审查 |
| 5 | 成本控制 | N Probe × M repetitions × API 调用数 | 设定每 ProbeRun 的 API 调用上限 |
| 6 | evalscope 版本一致性 | 不同 Probe 的 evalscope 版本可能不同 | Docker 镜像固定版本，注册时上报版本 |

---

## 附录 A：与 Multica Daemon 对比

| 维度 | Multica Daemon | NTA Probe Agent |
|------|---------------|-----------------|
| 用途 | 执行 AI 编程任务 | 执行 evalscope benchmark |
| 运行时 | Claude Code / Codex CLI | evalscope evaluator |
| 注册信息 | AI CLI 检测 | 网络身份检测 (IP/ISP/ASN) |
| 任务模型 | Issue → 代码变更 | Benchmark → 分数 + 网络指标 |
| 并发 | 20 并行任务 | 1 任务（需要资源隔离） |
| 输出 | PR, 代码差异, 评论 | 分数, 延迟, 网络元数据, 对比报告 |
| **借鉴** | 注册/心跳, pull-based 领取, 状态机 | — |
| **未借鉴** | Workspace 管理, Session 复用, Skill 注入 | — |

## 附录 B：项目文件变更清单

```
新增文件:
  backend/src/nta_backend/models/probe.py
  backend/src/nta_backend/schemas/probe.py
  backend/src/nta_backend/api/routers/probes.py
  backend/src/nta_backend/api/routers/probe_runs.py
  backend/src/nta_backend/services/probe_service.py
  backend/src/nta_backend/services/probe_run_service.py
  backend/src/nta_backend/workflows/probe_run.py
  backend/src/nta_backend/activities/probe_run.py
  backend/src/nta_backend/evaluation_v2/comparison.py
  backend/migrations/versions/0006_probe_system.py

  frontend/app/(console)/probes/page.tsx
  frontend/app/(console)/probe-runs/page.tsx
  frontend/app/(console)/probe-runs/[id]/page.tsx
  frontend/features/probe/api.ts
  frontend/features/probe/components/*.tsx
  frontend/features/probe/status.ts

  nta-probe-agent/  (独立 Python 包)

修改文件:
  backend/src/nta_backend/evaluation_v2/execution/evalscope_builtin.py  # 抽取可独立调用的执行函数
  backend/apps/worker/main.py                                           # 注册 ProbeRunWorkflow
  backend/apps/api/main.py                                              # 注册新 Router
  frontend/types/api.ts                                                 # 新增 Probe 相关类型
  frontend/app/(console)/layout.tsx                                     # 导航栏新增入口
  infra/compose/docker-compose.dev.yml                                  # (可选) 本地 Probe 容器
```
