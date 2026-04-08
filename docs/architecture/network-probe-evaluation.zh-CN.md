# 网络探针评测架构

> 检测在不同 IP 地域、运营商与网络提供商下调用 LLM 时是否出现智力退化。

## 1. 问题定义

当从不同 IP 地域和运营商调用同一个 Provider API 时，LLM 的响应质量可能并不一致。潜在原因包括：

- **Provider 侧路由差异**：不同地域的 API 网关可能路由到不同的 GPU 集群或模型版本
- **流量整形**：运营商层面的限速或 QoS 策略影响 API 响应
- **CDN / 代理干扰**：中间节点可能截断、缓存或修改响应
- **限流歧视**：按 IP / 地域做限流，导致回退到更小模型
- **地理分区模型服务**：出于合规或成本优化，Provider 按地域提供不同模型权重

**目标**：构建一套分布式探针系统，在多个网络观测点上运行完全一致的 benchmark，并输出可比较的退化分析报告。

---

## 2. 核心概念

### 2.1 什么是 “Probe Agent”？

借鉴 Multica 的 daemon 架构，**Probe Agent** 是部署在某个特定网络观测点上的轻量 Python 进程（云主机、边缘节点、VPN 出口、住宅代理等）。它负责：

1. 向控制面**注册**自己，并上报网络身份信息（IP、运营商、地理位置、AS 号）
2. **轮询**控制面，领取分配给自己的评测任务
3. 使用 evalscope 对目标 LLM API 执行 benchmark
4. 将结果与网络元数据**回传**到控制面

与 Multica 的 daemon 不同，后者执行的是 Claude / Codex CLI，而我们的 probe agent 执行的是 **evalscope benchmark**，任务载荷要聚焦得多。

### 2.2 网络观测点

一个观测点由以下信息共同定义：

```text
VantagePoint {
    probe_id:    UUID
    ip_address:  str          # 公网 IP
    isp:         str          # 例如 "中国电信"、"AWS"
    asn:         int          # 自治系统号
    region:      str          # 例如 "cn-beijing"、"us-east-1"
    country:     str          # ISO 3166-1 alpha-2
    city:        str | None
    network_type: enum        # cloud | residential | mobile | vpn | proxy
    tags:        list[str]    # 自定义标签，例如 ["aliyun", "education-network"]
}
```

### 2.3 ProbeRun（对比型评测）

**ProbeRun** 是顶层实体，用来把多个观测点基于相同 benchmark 和相同目标模型的评测结果组织在一起：

```text
ProbeRun {
    id:             UUID
    name:           str
    status:         queued | dispatching | running | completed | failed
    benchmark:      EvaluationTargetRef    # 复用现有 spec / suite
    target_model:   ModelBindingSnapshot   # 被测试的 LLM
    probe_filter:   ProbeFilter            # 哪些 probe 参与
    repetitions:    int                    # 每个 probe 的重复运行次数，用于统计显著性
    created_at:     datetime

    # Results
    items:          list[ProbeRunItem]     # 每个 (probe, repetition) 一条
    comparison:     ComparisonReport       # 跨 probe 分析
}
```

---

## 3. 架构总览

```text
                         ┌──────────────────────────────────────────┐
                         │           NTA Platform Backend           │
                         │                                          │
                         │  ┌───────────────────────────────────┐   │
                         │  │      Probe Coordination Service    │   │
                         │  │  - Probe 注册与心跳管理            │   │
                         │  │  - ProbeRun 生命周期管理           │   │
                         │  │  - 任务下发                        │   │
                         │  │  - 结果聚合                        │   │
                         │  └─────────────┬─────────────────────┘   │
                         │                │                         │
                         │  ┌─────────────┴─────────────────────┐   │
                         │  │        Temporal Workflows          │   │
                         │  │  - ProbeRunWorkflow               │   │
                         │  │  - ProbeRunItemWorkflow           │   │
                         │  │  （复用 evaluation_v2 模式）       │   │
                         │  └─────────────┬─────────────────────┘   │
                         │                │                         │
                         │  ┌─────────────┴─────────────────────┐   │
                         │  │        Comparison Engine           │   │
                         │  │  - 跨 probe 分数差异分析           │   │
                         │  │  - 统计显著性检验                 │   │
                         │  │  - 退化分类                       │   │
                         │  │  - 延迟与 token 分析              │   │
                         │  └───────────────────────────────────┘   │
                         └────────────────┬─────────────────────────┘
                                          │ REST API（轮询模式）
                     ┌────────────────────┼────────────────────────┐
                     │                    │                        │
              ┌──────┴──────┐     ┌───────┴──────┐      ┌─────────┴────────┐
              │ Probe Agent │     │ Probe Agent  │      │   Probe Agent    │
              │ 北京        │     │ 上海         │      │   美国东部       │
              │ 中国电信    │     │ 中国联通     │      │   AWS            │
              │             │     │              │      │                  │
              │ ┌─────────┐ │     │ ┌──────────┐ │      │ ┌──────────────┐ │
              │ │evalscope│ │     │ │evalscope │ │      │ │  evalscope   │ │
              │ └─────────┘ │     │ └──────────┘ │      │ └──────────────┘ │
              │      │      │     │      │       │      │       │          │
              │      ▼      │     │      ▼       │      │       ▼          │
              │   LLM API   │     │   LLM API    │      │    LLM API      │
              └─────────────┘     └──────────────┘      └──────────────────┘
```

---

## 4. 组件设计

### 4.1 Probe Agent（Python Daemon）

**设计原则**：agent 要尽可能轻。它本质上是包在 evalscope 外面的一层薄壳，只负责补充网络元数据和控制面通信。

```python
# probe_agent/agent.py（概念示例）

class ProbeAgent:
    """
    生命周期：
      1. 启动   → 识别网络身份 → 向控制面注册
      2. 轮询   → 从控制面领取任务
      3. 执行   → 运行 evalscope benchmark
      4. 上报   → 上传结果与网络元数据
      5. 循环   → 回到轮询阶段
    """

    def __init__(self, config: ProbeConfig):
        self.config = config
        self.vantage: VantagePoint = None
        self.registered: bool = False

    async def run(self):
        self.vantage = await detect_vantage_point()
        await self.register()
        await self.heartbeat_loop()   # 后台任务
        await self.poll_loop()        # 主循环

    async def detect_vantage_point(self) -> VantagePoint:
        """
        自动识别网络身份：
        - 通过外部服务获取公网 IP（ipinfo.io、ip-api.com）
        - 通过 IP 查询 ISP、ASN、地理位置
        - 对已知部署场景支持配置覆盖
        """
        ...

    async def register(self):
        """POST /api/v2/probes/register"""
        ...

    async def poll_loop(self):
        """
        轮询间隔：5 秒（可配置）
        并发度：一次只跑 1 个任务（benchmark 需要独占资源）
        """
        while True:
            task = await self.claim_task()
            if task:
                await self.execute_task(task)
            await asyncio.sleep(self.config.poll_interval)

    async def execute_task(self, task: ProbeTask):
        """
        核心执行流程：
        1. 用 task.item_plan 构造 evalscope TaskConfig
        2. 采集执行前网络指标（ping、traceroute 到 API）
        3. 运行 evalscope evaluator
        4. 采集执行后网络指标
        5. 上报结果
        """
        pre_net = await self.collect_network_metrics(task.api_endpoint)
        result = self.run_evalscope(task.item_plan)
        post_net = await self.collect_network_metrics(task.api_endpoint)

        await self.report_result(task.id, result, pre_net, post_net)
```

**每次执行采集的网络指标**：

```python
@dataclass
class NetworkMetrics:
    timestamp: datetime
    target_host: str
    dns_resolve_ms: float        # DNS 解析耗时
    tcp_connect_ms: float        # TCP 握手耗时
    tls_handshake_ms: float      # TLS 握手耗时
    first_byte_ms: float         # 首字节时间（TTFB）
    ping_rtt_ms: float           # ICMP / TCP ping RTT
    traceroute_hops: int | None  # 跳数（可选）
    packet_loss_pct: float       # 丢包率
    resolved_ip: str             # API 实际解析到的 IP
```

**部署模式**：

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **Standalone** | 单个 `probe-agent run` 进程 | 云主机、容器 |
| **Docker** | `docker run nta/probe-agent` | 云端 / 边缘节点部署 |
| **Ephemeral** | 启动 → 执行一个任务 → 退出 | Serverless / CI |

### 4.2 控制面扩展

在现有 NTA backend 上扩展 probe 协调能力。**不要 fork 新系统**，而是在 `evaluation_v2` 旁边新增。

#### 4.2.1 Probe Registry

```python
# models/probe.py

class Probe(Base, UUIDPrimaryKey, Timestamps):
    """已注册的 probe agent 实例。"""
    project_id:     UUID
    name:           str               # 人类可读名称，例如 "beijing-ct-01"
    status:         str               # online | offline | disabled
    ip_address:     str
    isp:            str | None
    asn:            int | None
    region:         str | None
    country:        str | None
    city:           str | None
    network_type:   str               # cloud | residential | mobile | vpn
    tags_json:      list[str]
    agent_version:  str | None
    last_heartbeat: datetime | None
    device_info:    dict              # OS、Python 版本、evalscope 版本

class ProbeHeartbeat(Base, UUIDPrimaryKey):
    """心跳日志（保留最近 N 条，旧数据定期清理）。"""
    probe_id:       UUID
    ip_address:     str               # 每次心跳重新识别（IP 可能变化）
    network_metrics: dict             # 基础连通性指标
    created_at:     datetime
```

#### 4.2.2 ProbeRun 与 ProbeRunItem

复用现有 `EvaluationRun` 基础设施，而不是重复造一套。只在上面再加一层很薄的协调层：

```python
class ProbeRun(Base, UUIDPrimaryKey, Timestamps, CreatedBy):
    """
    面向多个 probe 观测点的对比评测。
    每个 ProbeRunItem 与一个 EvaluationRunItem 1:1 映射，
    但会额外携带 probe / network 上下文。
    """
    project_id:       UUID
    name:             str
    status:           str            # queued | dispatching | running | completed | failed
    description:      str | None

    # 要评测的内容
    target_ref:       dict           # 序列化后的 EvaluationTargetRef
    model_id:         UUID
    judge_policy_id:  UUID | None
    overrides:        dict

    # Probe 选择条件
    probe_filter_json: dict          # 包含 tags、regions、ISPs 等过滤条件
    repetitions:      int = 3        # 每个 probe 的重复次数，用于统计

    # 编排
    temporal_workflow_id: str | None

    # 结果
    comparison_report_uri: str | None
    summary_json:     dict | None    # 快速访问的对比摘要

    items:            list["ProbeRunItem"]


class ProbeRunItem(Base, UUIDPrimaryKey, Timestamps):
    """
    一个 (probe, repetition) 对应一条记录。实际 benchmark 执行
    仍然委托给 EvaluationRun。
    """
    probe_run_id:     UUID           # FK → ProbeRun
    probe_id:         UUID           # FK → Probe
    repetition:       int            # 从 1 开始计数
    status:           str

    # 委托执行 —— 真正干活的是 EvaluationRun
    evaluation_run_id: UUID | None   # FK → EvaluationRun

    # 执行时刻捕获的网络上下文
    vantage_snapshot: dict           # 执行时冻结的 VantagePoint
    pre_network_metrics:  dict | None
    post_network_metrics: dict | None

    # 便于快速访问的结果（从 EvaluationRun 反规范化）
    score:            float | None
    latency_avg_ms:   float | None
    error_rate:       float | None
```

**关键设计决策**：`ProbeRunItem` 只负责加上 **网络维度**，真正的 benchmark 执行仍委托给 `EvaluationRun`。这样可以获得：

- 不重复集成 evalscope
- 充分复用现有编译、执行、产物流水线
- ProbeRunItem 只增加网络相关上下文

#### 4.2.3 Probe 通信 API

遵循 Multica 的模式：简单 REST、轮询式、无 push。

```text
# Probe Agent → Control Plane
POST   /api/v2/probes/register             # 注册 / 重新注册
POST   /api/v2/probes/{id}/heartbeat       # 存活心跳 + 指标
POST   /api/v2/probes/{id}/tasks/claim     # 拉取下一个任务
POST   /api/v2/probes/tasks/{id}/start     # 标记任务开始执行
POST   /api/v2/probes/tasks/{id}/progress  # 进度更新
POST   /api/v2/probes/tasks/{id}/complete  # 上传结果
POST   /api/v2/probes/tasks/{id}/fail      # 上报失败

# Control Plane → Frontend
GET    /api/v2/probe-runs                  # 列表
POST   /api/v2/probe-runs                  # 创建 ProbeRun
GET    /api/v2/probe-runs/{id}             # 详情 + 对比结果
POST   /api/v2/probe-runs/{id}/cancel      # 取消
GET    /api/v2/probes                      # 已注册 probe 列表
GET    /api/v2/probes/{id}                 # probe 详情 + 历史
```

### 4.3 执行架构：两种模式

系统支持两种执行模式，取决于 evalscope 运行在哪里。

#### 模式 A：Probe 侧执行（主模式）

```text
Control Plane                          Probe Agent
     │                                      │
     │  ── claim task ─────────────────────→ │
     │  ←── item_plan + model_binding ────── │
     │                                      │
     │                              ┌───────┴────────┐
     │                              │  evalscope     │
     │                              │  本地执行      │
     │                              │  从 probe IP   │
     │                              │  调用 LLM API  │
     │                              └───────┬────────┘
     │                                      │
     │  ←── CanonicalExecutionResult ────── │
     │  ←── NetworkMetrics ─────────────── │
```

**优点**：LLM API 请求真正从 probe 的 IP 发出，这正是我们要验证的内容。  
**缺点**：probe 上需要安装 evalscope 和 benchmark 数据。

#### 模式 B：中心侧执行 + 代理（备选）

```text
Control Plane                    Proxy / Tunnel         LLM API
     │                               │                    │
     │  evalscope 在这里运行         │                    │
     │  HTTP 流量经由 probe ────────→ │ ──────────────→   │
     │  作为代理出口                 │ ←──────────────    │
     │  ←──────────────────────────── │                    │
```

**优点**：probe 可以极轻量，只要提供 SOCKS5 / HTTP 代理。  
**缺点**：代理引入额外 hop，难以精确还原真实网络条件。

**建议**：优先采用模式 A，准确性最高。模式 B 只在 probe 部署条件极其受限时才考虑。

### 4.4 Temporal Workflow 设计

```python
# workflows/probe_run.py

@workflow.defn
class ProbeRunWorkflow:
    """
    负责编排一次对比型 probe 评测。

    1. 解析哪些 probe 需要参与
    2. 为每个 (probe, repetition) 创建 ProbeRunItem
    3. 等待所有 probe 领取并执行完成
    4. 运行对比分析
    """

    @workflow.run
    async def run(self, input: ProbeRunWorkflowInput) -> dict:
        # Step 1: 解析参与 probe
        probe_ids = await workflow.execute_activity(
            resolve_probe_participants,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 2: 创建 ProbeRunItems 并派发任务
        await workflow.execute_activity(
            dispatch_probe_tasks,
            args=[input.probe_run_id, probe_ids, input.repetitions],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 3: 等待完成（轮询式，probe 自主执行）
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

        return {"status": "completed"}
```

**为什么不做每个 probe 一个 child workflow？**  
和 `EvaluationRunWorkflow` 直接执行 item 不同，这里的 probe 执行是 **拉模式**。真正去领取并执行任务的是 probe agent，因此 workflow 更适合负责“等待 + 分析”，而不是直接驱动执行。

### 4.5 Comparison Engine

它是核心分析组件，用来回答：**“是否真的发生了退化？”**

```python
@dataclass
class DegradationReport:
    """跨 probe 对比分析的输出。"""

    # 总体结论
    degradation_detected: bool
    confidence: float                    # 0-1

    # 每个 probe 的摘要
    probe_scores: list[ProbeScoreSummary]
    #   probe_id, vantage, avg_score, std_dev, sample_count,
    #   avg_latency_ms, error_rate, score_delta_from_best

    # 两两比较
    pairwise: list[PairwiseComparison]
    #   probe_a, probe_b, score_diff, p_value, significant

    # 按维度拆分
    by_region: dict[str, RegionSummary]
    by_isp: dict[str, ISPSummary]
    by_network_type: dict[str, NetworkTypeSummary]

    # 异常标记
    anomalies: list[Anomaly]
    #   probe_id, anomaly_type, description, severity


class ComparisonEngine:

    def analyze(self, probe_run: ProbeRun) -> DegradationReport:
        """
        分析流水线：
        1. 收集所有 ProbeRunItem 结果
        2. 跨 probe 对分数做归一化
        3. 运行统计检验（Welch's t-test、Mann-Whitney U）
        4. 计算效应量（Cohen's d）
        5. 判定退化严重程度
        6. 生成对比报告
        """
        ...

    def _statistical_test(self, scores_a, scores_b) -> PairwiseComparison:
        """
        由于分数分布未必服从正态分布，因此优先采用非参数方法：
        - Mann-Whitney U：用于序关系比较
        - Bootstrap 置信区间：增强稳健性
        - Bonferroni 校正：处理多重比较问题
        """
        ...

    def _classify_degradation(self, delta: float, p_value: float) -> str:
        """
        分类矩阵：
          |delta| < 2% 且 p > 0.05   → "none"
          |delta| < 5% 且 p < 0.05   → "mild"
          |delta| < 10% 且 p < 0.01  → "moderate"
          |delta| >= 10%             → "severe"
        """
        ...
```

**关键指标**：

| 指标 | 衡量内容 | 退化信号 |
|------|----------|----------|
| **Score** | Benchmark 准确率，例如 MMLU | 核心智力指标 |
| **Latency (TTFB)** | 首 token 延迟 | 路由 / 限速信号 |
| **Latency (Total)** | 全响应耗时 | 模型版本差异信号 |
| **Token Count** | 输出 token 长度 | 截断信号 |
| **Error Rate** | API 调用失败率 | 封禁 / 限流信号 |
| **Response Consistency** | 同题是否稳定输出相近质量 | 模型变体信号 |

### 4.6 推荐 Benchmark

用于检测退化的 benchmark 应满足：

1. **够快**：样本量最好几百以内，便于多 probe 同时跑
2. **够稳定**：重复运行时方差低
3. **够敏感**：能明显区分正常模型和退化模型

| Benchmark | 样本量 | 原因 |
|-----------|--------|------|
| **MMLU（mini）** | 100 样本，选核心子集 | 知识能力黄金标准 |
| **GSM8K（mini）** | 50 样本 | 数学推理，对模型质量非常敏感 |
| **HellaSwag（mini）** | 100 样本 | 常识推理，弱模型会明显掉分 |
| **Custom NTA-Network-Bench** | 50 样本 | 人工挑选，最大化区分度 |

**建议**：新增一个专门的 `EvalSuite`，命名为 `network-probe-standard`，把这些 mini benchmark 按合理权重组合起来。

---

## 5. 数据流（端到端）

```text
用户创建 ProbeRun
    │
    ▼
[1] Compile：解析 benchmark + model binding + probe filter
    │
    ▼
[2] Dispatch：创建 ProbeRunItems，每个 (matching_probe, repetition) 一条
    │   每条 item 带有：item_plan（CompiledRunItemPlan）+ model_binding
    │
    ▼
[3] Probes 轮询并 claim 任务
    │   Probe 看到的是：“对 gpt-4o 在 https://api.openai.com 上跑 GSM8K-mini”
    │
    ▼
[4] Probe 本地执行
    │   a. 采集执行前网络指标（ping、DNS、traceroute）
    │   b. 用 plan 中的 TaskConfig 运行 evalscope
    │      - evalscope 从 probe 的 IP 调用 LLM API
    │      - 采集每个 sample 的 score、latency、tokens
    │   c. 采集执行后网络指标
    │   d. 打包：CanonicalExecutionResult + NetworkMetrics
    │
    ▼
[5] Probe 回传结果
    │   POST /api/v2/probes/tasks/{id}/complete
    │   Body: { result, pre_network, post_network, vantage_snapshot }
    │
    ▼
[6] 控制面持久化
    │   - 创建 / 更新 EvaluationRun + metrics + samples
    │   - 把网络指标写到 ProbeRunItem
    │   - 将产物上传到 S3
    │
    ▼
[7] 全部 probe 完成 → Comparison Engine 执行
    │   - 聚合每个 probe 的分数
    │   - 跨 probe 做统计检验
    │   - 生成 DegradationReport
    │
    ▼
[8] 报告可用
    Dashboard 展示：
    ┌──────────────────────────────────────────────────┐
    │  ProbeRun: "GPT-4o 中国网络测试"                  │
    │  Status: COMPLETED                              │
    │  Degradation: MODERATE (p<0.01)                 │
    │                                                  │
    │  Probe          Score   Latency  Error%  Delta   │
    │  ─────────────  ─────   ───────  ──────  ─────   │
    │  北京电信       82.3%   1.2s     2.1%    -5.7%   │
    │  上海联通       84.1%   0.9s     1.3%    -3.9%   │
    │  US-East AWS    88.0%   0.3s     0.2%    (base)  │
    │  东京 AWS       87.5%   0.4s     0.3%    -0.5%   │
    │                                                  │
    │  ⚠ 中国地区相较美国 / 日本出现统计显著性掉分     │
    │    (p=0.003, d=0.72)                             │
    └──────────────────────────────────────────────────┘
```

---

## 6. 与当前代码库的集成

### 6.1 可直接复用的内容（零重复）

| 现有组件 | 复用方式 |
|---|---|
| `evaluation_v2.compiler` | 将 benchmark target 编译成 `CompiledRunItemPlan` |
| `EvalScopeBuiltinExecutor` | 由 probe agent 直接嵌入使用 |
| `CanonicalExecutionResult` | 作为 probe → control plane 的统一结果格式 |
| `CanonicalMetric / CanonicalSample` | 用于跨 probe 对比的逐样本数据 |
| `ModelBindingSnapshot` | 将模型 API 配置传给 probe |
| `EvaluationRun / RunItem` | 每个 ProbeRunItem 委托到一个真实的 EvaluationRun |
| S3 产物流水线 | probe 结果和普通评测结果共用存储 |
| Temporal 基础设施 | 编排 ProbeRun 生命周期 |

### 6.2 需要新增的内容

| 新组件 | 位置 | 作用 |
|---|---|---|
| `Probe` model | `models/probe.py` | Probe 注册表 |
| `ProbeRun / ProbeRunItem` models | `models/probe.py` | 协调层 |
| Probe API routes | `api/routers/probes.py` | agent 与管理端接口 |
| `ProbeRunWorkflow` | `workflows/probe_run.py` | Temporal 编排 |
| Probe activities | `activities/probe_run.py` | 任务派发、等待、分析 |
| `ComparisonEngine` | `evaluation_v2/comparison.py` | 统计分析 |
| `probe-agent` CLI | `probe_agent/`（独立 package） | agent 可执行程序 |
| `NetworkMetrics` collector | `probe_agent/network.py` | 网络指标采集 |

### 6.3 当前代码需要做的重构

当前 `EvalScopeBuiltinExecutor` 是在 Temporal worker 进程内直接运行的。为了支持 probe 侧执行，需要把它抽成**可独立运行**的执行核心：

```python
# Current：和 Temporal activity 耦合较紧
async def activity_execute_evaluation_run_item(run_id, item_id):
    plan = load_plan_from_db(item_id)
    adapter = get_engine_adapter(plan.engine, plan.execution_mode)
    result = adapter.execute(plan, context)   # ← probe 需要的就是这一层
    persist_to_db(result)

# Target：抽出独立执行核心
def execute_benchmark(item_plan: CompiledRunItemPlan, output_dir: Path) -> CanonicalExecutionResult:
    """
    纯函数。不依赖 DB、不依赖 S3、不依赖 Temporal。
    输入：plan + output dir
    输出：canonical result
    既可被 Temporal activity 调用，也可被 probe agent 调用。
    """
    adapter = get_engine_adapter(item_plan.engine, item_plan.execution_mode)
    context = ExecutionContext(output_dir=output_dir)
    return adapter.execute(item_plan, context)
```

这个重构是最小且向后兼容的：现有 `activity_execute_evaluation_run_item` 内部只需要改成调用 `execute_benchmark` 即可。

---

## 7. Probe Agent 打包与部署

### 7.1 包结构

```text
nta-probe-agent/
├── pyproject.toml           # 独立 package，依赖 evalscope + httpx
├── src/
│   └── nta_probe_agent/
│       ├── __init__.py
│       ├── cli.py            # CLI 入口：probe-agent run/register/status
│       ├── agent.py          # ProbeAgent 主循环
│       ├── config.py         # 配置加载（env / file / flags）
│       ├── network.py        # VantagePoint 检测 + NetworkMetrics 采集
│       ├── client.py         # 控制面 HTTP client
│       ├── executor.py       # evalscope 执行封装
│       └── models.py         # 本地数据模型
├── Dockerfile
└── deploy/
    ├── docker-compose.yml    # 多地域部署模板
    └── terraform/            # 云主机资源编排
```

### 7.2 配置

```yaml
# probe-agent.yaml
control_plane:
  url: https://nta.example.com
  token: ${NTA_PROBE_TOKEN}

agent:
  name: "beijing-ct-01"
  poll_interval: 5s
  heartbeat_interval: 15s
  max_concurrent_tasks: 1     # benchmark 不应互相抢资源
  task_timeout: 2h

network:
  detect_vantage: true        # 自动识别 IP / ISP / geo
  overrides:                  # 手动覆盖
    region: "cn-beijing"
    isp: "中国电信"
    network_type: "cloud"
    tags: ["aliyun", "ecs"]
  collect_traceroute: false   # 在受限网络中可以关闭

evalscope:
  cache_dir: ~/.nta-probe/benchmarks   # 本地 benchmark 缓存
  log_level: INFO
```

### 7.3 部署模式

**模式 1：云主机（推荐作为第一阶段）**

```bash
# 通过 Terraform / Pulumi 部署到多地域
# 每个地域：1 台小规格 VM → 1 个 probe-agent 容器
# 成本：每个 probe 约 $5-15 / 月（t3.micro 或同级）

# 北京（阿里云 ECS）
docker run -d --name probe-beijing-ct \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=beijing-ct-01 \
  nta/probe-agent:latest

# 美国东部（AWS EC2）
docker run -d --name probe-us-east \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=us-east-aws-01 \
  nta/probe-agent:latest
```

**模式 2：住宅 / 移动网络 + VPN 出口**

```bash
# 测住宅宽带或移动网络路径时：
# 让 probe 跑在指定 VPN 出口后面
docker run -d --net=container:vpn-china-telecom \
  nta/probe-agent:latest
```

**模式 3：临时执行（CI / Serverless）**

```bash
# 执行一次任务后退出，适合按需探测
probe-agent run-once --task-id=xxx
```

---

## 8. 安全性考虑

| 风险点 | 缓解方式 |
|--------|----------|
| API key 要经过 probe | probe 收到加密后的 `model_binding`；密钥主要保留在控制面，或使用短时 token |
| 恶意 probe 伪造结果 | 通过签名 token 做 probe 认证，并做结果合理性校验（例如分数分布） |
| 网络元数据隐私 | IP / ISP 等数据仅在项目内可见，不公开共享 |
| probe 被攻陷 | 权限最小化；probe 只能 claim 属于自己的任务，只能读 benchmark 数据 |

**API key 处理，两种策略**：

1. **Key-in-plan**（更简单）：把 `api_key` 放进 `ModelBindingSnapshot` 传给 probe。适合内部 / 可信 probe。
2. **Proxy mode**（更安全）：probe 调控制面的代理接口，由控制面注入 key 再转发到 LLM API。虽然更安全，但会引入额外延迟，也削弱“从 probe 的真实 IP 发起请求”的价值。**不建议用于本场景**。

**建议**：优先使用 Provider 支持的短时、可限定范围的 token。对于不支持的 Provider，可接受加密传输下的 key-in-plan。

---

## 9. 实施阶段

### Phase 1：基础版（MVP）

**目标**：先用 2-3 个手工部署的 probe 验证概念可行。

- [ ] Probe registry model + API（register、heartbeat、list）
- [ ] ProbeRun / ProbeRunItem models
- [ ] Probe task claim / complete API
- [ ] 最小 probe agent CLI（`probe-agent run`）
- [ ] 将 `EvalScopeBuiltinExecutor` 重新封装为可独立调用的函数
- [ ] 基础网络元数据识别（IP、geo、ISP）
- [ ] 通过 API 手工创建 ProbeRun
- [ ] 简单对比：按 probe 展示平均分，先不做统计显著性

**交付结果**：能够创建 ProbeRun，让 2 个 probe 执行，并在页面上并排看到分数。

### Phase 2：分析与自动化

**目标**：补齐统计严谨性与自动编排能力。

- [ ] Temporal ProbeRunWorkflow
- [ ] 带统计检验的 ComparisonEngine
- [ ] DegradationReport 生成
- [ ] ProbeRun 结果前端 Dashboard
- [ ] Probe 健康监控（漏心跳 → offline）
- [ ] 预置 benchmark suite `network-probe-standard`
- [ ] Docker 镜像与部署脚本

**交付结果**：支持“一键运行网络探针测试”，自动生成带 p-value 和退化等级的对比报告。

### Phase 3：规模化与智能化

**目标**：支持持续监控与趋势识别。

- [ ] 定时 ProbeRun（基于 cron 的周期性测试）
- [ ] 历史趋势分析（退化是否随时间变化）
- [ ] 告警规则（分数下降超过阈值时通知）
- [ ] Probe 自动纳管（新 probe 加入后自动参与未来运行）
- [ ] A/B 网络路径测试（同一 probe，不同 DNS / route）
- [ ] 与现有 Leaderboard 集成（把 probe 作为 leaderboard 维度）

---

## 10. 未决问题

1. **Benchmark 数据分发**：probe 应该从 S3 / CDN 下载 benchmark 数据，还是直接打包进 Docker 镜像？本质是镜像体积与数据新鲜度之间的权衡。

2. **Key 轮转**：probe 认证 token 应该多久轮转一次？按运行轮转，还是长期有效？

3. **Provider ToS**：部分 LLM Provider 可能限制从多 IP 自动化做 benchmark，需要逐个 Provider 做合规评估。

4. **Baseline 定义**：退化计算时，基准分数用哪个 probe？
   可选方案：
   - 最优 probe
   - Provider 母区域，例如 OpenAI 用美国
   - 历史平均值

5. **成本管理**：N 个 probe × M 次重复 × 每次数百个 API 调用，预算如何控制？

---

## 附录 A：与 Multica 方案的对比

| 维度 | Multica Daemon | NTA Probe Agent |
|------|----------------|-----------------|
| **目标** | 执行 AI agent 任务（写代码、评审 PR） | 执行 evalscope benchmark |
| **运行时** | Claude Code / Codex CLI | evalscope evaluator |
| **注册内容** | 自动识别本机 AI CLI | 自动识别网络身份 |
| **任务类型** | Issue → 代码改动 | Benchmark → 分数 + 指标 |
| **并发度** | 20 个并行任务 | 1 个任务（benchmark 需要隔离） |
| **工作空间** | 每个任务 checkout Git repo | benchmark 数据缓存 |
| **输出** | 代码 diff、PR、评论 | 分数、延迟、网络指标 |
| **借鉴内容** | 注册 / 心跳、轮询 claim、任务状态机 | — |
| **不借鉴内容** | Workspace 管理、session 复用、skill 注入 | — |

## 附录 B：当前代码库中相关文件

```text
backend/src/nta_backend/
├── evaluation_v2/
│   ├── compiler.py                    # compile_run_request() —— 可复用
│   ├── engine_registry.py             # get_engine_adapter() —— 可复用
│   └── execution/
│       ├── contracts.py               # CanonicalExecutionResult —— 可复用
│       └── evalscope_builtin.py       # EvalScopeBuiltinExecutor —— 抽执行核心
├── workflows/
│   └── evaluation_run.py              # ProbeRunWorkflow 可参考的模式
├── activities/
│   └── evaluation_run.py              # Probe activity 可参考的模式
├── models/
│   └── evaluation_v2.py               # EvaluationRun —— ProbeRunItem 委托到这里
├── schemas/
│   └── evaluation_v2.py               # CompiledRunItemPlan、ModelBindingSnapshot —— 可复用
└── services/
    └── evaluation_run_v2_service.py   # 执行流水线 —— 可复用持久化逻辑
```
