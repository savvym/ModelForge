# Network Probe Evaluation Architecture

> Detect LLM intelligence degradation across IP regions, ISPs, and network providers.

## 1. Problem Statement

Different IP regions and ISPs may experience inconsistent LLM response quality when calling the same Provider API. Possible causes:

- **Provider-side routing**: Regional API gateways route to different GPU clusters or model versions
- **Traffic shaping**: ISP-level throttling or QoS policies affecting API responses
- **CDN/Proxy interference**: Intermediate nodes truncating, caching, or modifying responses
- **Rate limiting discrimination**: Per-IP/per-region rate limiting causing fallback to smaller models
- **Geographic model serving**: Providers serving different model weights by region (compliance, cost optimization)

**Goal**: Build a distributed probe system that runs identical benchmarks from multiple network vantage points and produces a comparative degradation report.

---

## 2. Core Concepts

### 2.1 What is a "Probe Agent"?

Borrowing from Multica's daemon architecture, a **Probe Agent** is a lightweight Python process deployed at a specific network vantage point (cloud VM, edge node, VPN exit, residential proxy). It:

1. **Registers** with the control plane, reporting its network identity (IP, ISP, geo, AS number)
2. **Polls** for evaluation tasks assigned to it
3. **Executes** benchmarks using evalscope against target LLM APIs
4. **Reports** results + network metadata back to the control plane

Unlike Multica's daemon (which runs Claude/Codex CLIs), our probe agent runs **evalscope benchmarks** — the execution payload is much more focused.

### 2.2 Network Vantage Point

A vantage point is the combination of:

```
VantagePoint {
    probe_id:    UUID
    ip_address:  str          # Public IP
    isp:         str          # e.g., "China Telecom", "AWS"
    asn:         int          # Autonomous System Number
    region:      str          # e.g., "cn-beijing", "us-east-1"
    country:     str          # ISO 3166-1 alpha-2
    city:        str | None
    network_type: enum        # cloud | residential | mobile | vpn | proxy
    tags:        list[str]    # Free-form labels, e.g., ["aliyun", "education-network"]
}
```

### 2.3 Probe Run (comparative evaluation)

A **ProbeRun** is the top-level entity that groups evaluation runs from multiple vantage points using the same benchmark and target model:

```
ProbeRun {
    id:             UUID
    name:           str
    status:         queued | dispatching | running | completed | failed
    benchmark:      EvaluationTargetRef    # Reuse existing spec/suite
    target_model:   ModelBindingSnapshot   # The LLM being tested
    probe_filter:   ProbeFilter            # Which probes should participate
    repetitions:    int                    # Runs per probe for statistical significance
    created_at:     datetime
    
    # Results
    items:          list[ProbeRunItem]     # One per (probe, repetition)
    comparison:     ComparisonReport       # Cross-probe analysis
}
```

---

## 3. Architecture Overview

```
                         ┌──────────────────────────────────────────┐
                         │           NTA Platform Backend           │
                         │                                         │
                         │  ┌───────────────────────────────────┐  │
                         │  │     Probe Coordination Service     │  │
                         │  │  - Probe registry & heartbeat     │  │
                         │  │  - ProbeRun lifecycle mgmt        │  │
                         │  │  - Task dispatch                  │  │
                         │  │  - Result aggregation             │  │
                         │  └─────────────┬─────────────────────┘  │
                         │                │                        │
                         │  ┌─────────────┴─────────────────────┐  │
                         │  │      Temporal Workflows            │  │
                         │  │  - ProbeRunWorkflow               │  │
                         │  │  - ProbeRunItemWorkflow            │  │
                         │  │  (reuse evaluation_v2 patterns)    │  │
                         │  └─────────────┬─────────────────────┘  │
                         │                │                        │
                         │  ┌─────────────┴─────────────────────┐  │
                         │  │      Comparison Engine             │  │
                         │  │  - Cross-probe score diff          │  │
                         │  │  - Statistical significance        │  │
                         │  │  - Degradation classification      │  │
                         │  │  - Latency & token analysis        │  │
                         │  └───────────────────────────────────┘  │
                         └────────────────┬─────────────────────────┘
                                          │ REST API (poll-based)
                     ┌────────────────────┼────────────────────────┐
                     │                    │                        │
              ┌──────┴──────┐     ┌───────┴──────┐      ┌─────────┴────────┐
              │ Probe Agent │     │ Probe Agent  │      │   Probe Agent    │
              │ Beijing     │     │ Shanghai     │      │   US-East        │
              │ China Telec │     │ China Unicom │      │   AWS            │
              │             │     │              │      │                  │
              │ ┌─────────┐ │     │ ┌──────────┐ │      │ ┌──────────────┐ │
              │ │evalscope│ │     │ │evalscope │ │      │ │  evalscope   │ │
              │ └─────────┘ │     │ └──────────┘ │      │ └──────────────┘ │
              │      │      │     │      │       │      │       │          │
              │      ▼      │     │      ▼       │      │       ▼          │
              │  LLM API    │     │  LLM API     │      │   LLM API       │
              └─────────────┘     └──────────────┘      └──────────────────┘
```

---

## 4. Component Design

### 4.1 Probe Agent (Python Daemon)

**Design principle**: Keep the agent minimal. It is a thin shell around evalscope that adds network metadata and control plane communication.

```python
# probe_agent/agent.py  (conceptual)

class ProbeAgent:
    """
    Lifecycle:
      1. Startup  → detect network identity → register with control plane
      2. Poll     → claim tasks from control plane
      3. Execute  → run evalscope benchmark
      4. Report   → upload results + network metadata
      5. Repeat   → back to poll
    """

    def __init__(self, config: ProbeConfig):
        self.config = config
        self.vantage: VantagePoint = None
        self.registered: bool = False

    async def run(self):
        self.vantage = await detect_vantage_point()
        await self.register()
        await self.heartbeat_loop()   # Background
        await self.poll_loop()        # Main loop

    async def detect_vantage_point(self) -> VantagePoint:
        """
        Auto-detect network identity:
        - Public IP via external service (ipinfo.io, ip-api.com)
        - ISP, ASN, geo from IP lookup
        - Configurable overrides for known deployments
        """
        ...

    async def register(self):
        """POST /api/v2/probes/register"""
        ...

    async def poll_loop(self):
        """
        Poll interval: 5s (configurable)
        Concurrency: 1 task at a time (benchmark needs full resources)
        """
        while True:
            task = await self.claim_task()
            if task:
                await self.execute_task(task)
            await asyncio.sleep(self.config.poll_interval)

    async def execute_task(self, task: ProbeTask):
        """
        Core execution:
        1. Build evalscope TaskConfig from task.item_plan
        2. Collect pre-execution network metrics (ping, traceroute to API)
        3. Run evalscope evaluator
        4. Collect post-execution network metrics
        5. Report results
        """
        pre_net = await self.collect_network_metrics(task.api_endpoint)
        result = self.run_evalscope(task.item_plan)
        post_net = await self.collect_network_metrics(task.api_endpoint)

        await self.report_result(task.id, result, pre_net, post_net)
```

**Network Metrics Collected Per Execution**:

```python
@dataclass
class NetworkMetrics:
    timestamp: datetime
    target_host: str
    dns_resolve_ms: float        # DNS resolution time
    tcp_connect_ms: float        # TCP handshake time
    tls_handshake_ms: float      # TLS negotiation time
    first_byte_ms: float         # Time to first byte (TTFB)
    ping_rtt_ms: float           # ICMP/TCP ping RTT
    traceroute_hops: int | None  # Hop count (optional)
    packet_loss_pct: float       # Packet loss percentage
    resolved_ip: str             # Actual IP the API resolved to
```

**Deployment modes**:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Standalone** | Single `probe-agent run` process | VMs, containers |
| **Docker** | `docker run nta/probe-agent` | Cloud/edge deploy |
| **Ephemeral** | Start → execute one task → exit | Serverless / CI |

### 4.2 Control Plane Extensions

Extend the existing NTA backend with probe coordination. **Do not fork** — add alongside `evaluation_v2`.

#### 4.2.1 Probe Registry

```python
# models/probe.py

class Probe(Base, UUIDPrimaryKey, Timestamps):
    """Registered probe agent instance."""
    project_id:     UUID
    name:           str               # Human label, e.g., "beijing-ct-01"
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
    device_info:    dict              # OS, Python version, evalscope version

class ProbeHeartbeat(Base, UUIDPrimaryKey):
    """Heartbeat log (last N kept, older pruned)."""
    probe_id:       UUID
    ip_address:     str               # Re-detect per heartbeat (IP can change)
    network_metrics: dict             # Basic connectivity metrics
    created_at:     datetime
```

#### 4.2.2 ProbeRun & ProbeRunItem

Reuse the existing `EvaluationRun` infra rather than duplicating it. Add a **thin coordination layer** on top:

```python
class ProbeRun(Base, UUIDPrimaryKey, Timestamps, CreatedBy):
    """
    A comparative evaluation across multiple probe vantage points.
    Each ProbeRunItem maps 1:1 to an EvaluationRunItem but carries
    additional probe/network context.
    """
    project_id:       UUID
    name:             str
    status:           str            # queued | dispatching | running | completed | failed
    description:      str | None

    # What to evaluate
    target_ref:       dict           # EvaluationTargetRef serialized
    model_id:         UUID
    judge_policy_id:  UUID | None
    overrides:        dict

    # Probe selection
    probe_filter_json: dict          # Tags, regions, ISPs to include
    repetitions:      int = 3        # Runs per probe for statistics

    # Orchestration
    temporal_workflow_id: str | None

    # Results
    comparison_report_uri: str | None
    summary_json:     dict | None    # Quick-access comparison summary

    items:            list["ProbeRunItem"]


class ProbeRunItem(Base, UUIDPrimaryKey, Timestamps):
    """
    One (probe, repetition) pair. Wraps an EvaluationRun that does the
    actual benchmark execution.
    """
    probe_run_id:     UUID           # FK → ProbeRun
    probe_id:         UUID           # FK → Probe
    repetition:       int            # 1-based repetition number
    status:           str

    # Delegation — the real work is an EvaluationRun
    evaluation_run_id: UUID | None   # FK → EvaluationRun

    # Network context captured at execution time
    vantage_snapshot: dict           # VantagePoint frozen at exec time
    pre_network_metrics:  dict | None
    post_network_metrics: dict | None

    # Quick-access results (denormalized from EvaluationRun)
    score:            float | None
    latency_avg_ms:   float | None
    error_rate:       float | None
```

**Key design decision**: `ProbeRunItem` delegates to `EvaluationRun` for actual execution. This means:
- Zero duplication of evalscope integration
- Full reuse of existing compilation, execution, artifact pipeline
- ProbeRunItem adds only the **network dimension**

#### 4.2.3 Probe Communication API

Following Multica's pattern — simple REST, poll-based, no push:

```
# Probe Agent → Control Plane
POST   /api/v2/probes/register          # Register/re-register
POST   /api/v2/probes/{id}/heartbeat    # Liveness + metrics
POST   /api/v2/probes/{id}/tasks/claim  # Pull next task
POST   /api/v2/probes/tasks/{id}/start  # Mark task running
POST   /api/v2/probes/tasks/{id}/progress  # Progress update
POST   /api/v2/probes/tasks/{id}/complete  # Upload results
POST   /api/v2/probes/tasks/{id}/fail   # Report failure

# Control Plane → Frontend
GET    /api/v2/probe-runs               # List probe runs
POST   /api/v2/probe-runs               # Create probe run
GET    /api/v2/probe-runs/{id}          # Detail + comparison
POST   /api/v2/probe-runs/{id}/cancel   # Cancel
GET    /api/v2/probes                   # List registered probes
GET    /api/v2/probes/{id}              # Probe detail + history
```

### 4.3 Execution Architecture: Two Modes

The system supports two execution modes based on where evalscope runs:

#### Mode A: Probe-Side Execution (Primary)

```
Control Plane                          Probe Agent
     │                                      │
     │  ── claim task ─────────────────────→ │
     │  ←── item_plan + model_binding ────── │
     │                                      │
     │                              ┌───────┴────────┐
     │                              │  evalscope     │
     │                              │  runs locally  │
     │                              │  calls LLM API │
     │                              │  FROM probe IP │
     │                              └───────┬────────┘
     │                                      │
     │  ←── CanonicalExecutionResult ────── │
     │  ←── NetworkMetrics ─────────────── │
```

**Pros**: LLM API call originates from probe's IP — this is what we want to test.  
**Cons**: Probe needs evalscope + benchmark data installed.

#### Mode B: Central Execution with Proxy (Alternative)

```
Control Plane                    Proxy/Tunnel          LLM API
     │                               │                    │
     │  evalscope runs here          │                    │
     │  HTTP traffic routed ────────→ │ ──────────────→   │
     │  through probe as proxy       │ ←──────────────    │
     │  ←──────────────────────────── │                    │
```

**Pros**: Probe is ultra-lightweight (just a SOCKS5/HTTP proxy).  
**Cons**: Added latency from proxy hop; harder to measure true network conditions.

**Recommendation**: Mode A for accuracy. Mode B only if probe deployment is severely constrained.

### 4.4 Temporal Workflow Design

```python
# workflows/probe_run.py

@workflow.defn
class ProbeRunWorkflow:
    """
    Orchestrates a comparative probe evaluation.

    1. Resolve which probes should participate
    2. For each (probe, repetition), create a ProbeRunItem
    3. Wait for all probes to claim & complete their tasks
    4. Run comparison analysis
    """

    @workflow.run
    async def run(self, input: ProbeRunWorkflowInput) -> dict:
        # Step 1: Resolve participating probes
        probe_ids = await workflow.execute_activity(
            resolve_probe_participants,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 2: Create ProbeRunItems and enqueue tasks
        await workflow.execute_activity(
            dispatch_probe_tasks,
            args=[input.probe_run_id, probe_ids, input.repetitions],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 3: Wait for completion (poll-based, probes execute autonomously)
        await workflow.execute_activity(
            wait_for_probe_completion,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(hours=24),
            heartbeat_timeout=timedelta(minutes=5),
        )

        # Step 4: Comparative analysis
        await workflow.execute_activity(
            analyze_probe_results,
            args=[input.probe_run_id],
            start_to_close_timeout=timedelta(minutes=30),
        )

        return {"status": "completed"}
```

**Why not child workflows per probe?** Unlike `EvaluationRunWorkflow` which directly executes items, probe execution is **pull-based** — the probe agent claims and runs the task. The workflow only needs to wait and then analyze.

### 4.5 Comparison Engine

The core analytical component that answers: **"Is there degradation?"**

```python
@dataclass
class DegradationReport:
    """Output of cross-probe comparison."""

    # Overall verdict
    degradation_detected: bool
    confidence: float                    # 0-1

    # Per-probe summary
    probe_scores: list[ProbeScoreSummary]
    #   probe_id, vantage, avg_score, std_dev, sample_count,
    #   avg_latency_ms, error_rate, score_delta_from_best

    # Pairwise comparisons
    pairwise: list[PairwiseComparison]
    #   probe_a, probe_b, score_diff, p_value, significant

    # Dimension breakdowns
    by_region: dict[str, RegionSummary]
    by_isp: dict[str, ISPSummary]
    by_network_type: dict[str, NetworkTypeSummary]

    # Anomaly flags
    anomalies: list[Anomaly]
    #   probe_id, anomaly_type, description, severity


class ComparisonEngine:

    def analyze(self, probe_run: ProbeRun) -> DegradationReport:
        """
        Analysis pipeline:
        1. Collect all ProbeRunItem results
        2. Normalize scores across probes
        3. Statistical tests (Welch's t-test, Mann-Whitney U)
        4. Effect size calculation (Cohen's d)
        5. Classify degradation severity
        6. Generate comparison report
        """
        ...

    def _statistical_test(self, scores_a, scores_b) -> PairwiseComparison:
        """
        Use non-parametric tests since score distributions may not be normal.
        - Mann-Whitney U for ordinal comparison
        - Bootstrap confidence intervals for robust estimation
        - Bonferroni correction for multiple comparisons
        """
        ...

    def _classify_degradation(self, delta: float, p_value: float) -> str:
        """
        Classification matrix:
          |delta| < 2% and p > 0.05  → "none"
          |delta| < 5% and p < 0.05  → "mild"
          |delta| < 10% and p < 0.01 → "moderate"
          |delta| >= 10%             → "severe"
        """
        ...
```

**Key Metrics**:

| Metric | What It Measures | Degradation Signal |
|--------|-----------------|-------------------|
| **Score** | Benchmark accuracy (e.g., MMLU) | Core intelligence indicator |
| **Latency (TTFB)** | Time to first token | Routing/throttling indicator |
| **Latency (Total)** | Full response time | Model version indicator |
| **Token Count** | Output token length | Truncation indicator |
| **Error Rate** | Failed API calls | Blocking/rate-limit indicator |
| **Response Consistency** | Same question → same quality | Model variant indicator |

### 4.6 Recommended Benchmarks

For degradation detection, benchmarks should be:
1. **Fast** — few hundred samples max (runs on many probes simultaneously)
2. **Deterministic** — low variance on repeated runs
3. **Sensitive** — clearly separates capable vs degraded models

| Benchmark | Samples | Why |
|-----------|---------|-----|
| **MMLU (mini)** | 100 samples from core subsets | Gold standard knowledge test |
| **GSM8K (mini)** | 50 samples | Math reasoning — very sensitive to model quality |
| **HellaSwag (mini)** | 100 samples | Commonsense — drops sharply on weaker models |
| **Custom NTA-Network-Bench** | 50 samples | Hand-picked questions that maximize separation |

**Recommendation**: Create a dedicated `EvalSuite` named `network-probe-standard` that combines these mini-benchmarks with appropriate weights.

---

## 5. Data Flow (End-to-End)

```
User creates ProbeRun
    │
    ▼
[1] Compile: resolve benchmark + model binding + probe filter
    │
    ▼
[2] Dispatch: create ProbeRunItems, one per (matching_probe, repetition)
    │   each item gets: item_plan (CompiledRunItemPlan) + model_binding
    │
    ▼
[3] Probes poll & claim tasks
    │   Probe sees: "run GSM8K-mini against gpt-4o at https://api.openai.com"
    │
    ▼
[4] Probe executes locally
    │   a. Collect pre-network metrics (ping, DNS, traceroute)
    │   b. Run evalscope with plan's TaskConfig
    │      - evalscope calls LLM API from probe's IP
    │      - collects per-sample: score, latency, tokens
    │   c. Collect post-network metrics
    │   d. Package: CanonicalExecutionResult + NetworkMetrics
    │
    ▼
[5] Probe reports results
    │   POST /api/v2/probes/tasks/{id}/complete
    │   Body: { result, pre_network, post_network, vantage_snapshot }
    │
    ▼
[6] Control plane persists
    │   - Creates/updates EvaluationRun + metrics + samples
    │   - Stores network metrics on ProbeRunItem
    │   - Uploads artifacts to S3
    │
    ▼
[7] All probes done → Comparison Engine runs
    │   - Aggregates scores per probe
    │   - Statistical tests across probes
    │   - Generates DegradationReport
    │
    ▼
[8] Report available
    Dashboard shows:
    ┌──────────────────────────────────────────────────┐
    │  ProbeRun: "GPT-4o China Network Test"           │
    │  Status: COMPLETED                               │
    │  Degradation: MODERATE (p<0.01)                  │
    │                                                  │
    │  Probe          Score   Latency  Error%  Delta   │
    │  ─────────────  ─────   ───────  ──────  ─────   │
    │  Beijing CT     82.3%   1.2s     2.1%    -5.7%   │
    │  Shanghai CU    84.1%   0.9s     1.3%    -3.9%   │
    │  US-East AWS    88.0%   0.3s     0.2%    (base)  │
    │  Tokyo AWS      87.5%   0.4s     0.3%    -0.5%   │
    │                                                  │
    │  ⚠ China region shows statistically significant  │
    │    score drop vs US/Japan (p=0.003, d=0.72)      │
    └──────────────────────────────────────────────────┘
```

---

## 6. Integration with Current Codebase

### 6.1 What to Reuse (Zero Duplication)

| Existing Component | Reuse How |
|---|---|
| `evaluation_v2.compiler` | Compile benchmark target into `CompiledRunItemPlan` |
| `EvalScopeBuiltinExecutor` | Probe agent embeds this executor directly |
| `CanonicalExecutionResult` | Standard result format from probe → control plane |
| `CanonicalMetric / CanonicalSample` | Per-sample data for comparison |
| `ModelBindingSnapshot` | Model API config passed to probes |
| `EvaluationRun / RunItem` | Each ProbeRunItem delegates to a real EvaluationRun |
| S3 artifact pipeline | Store probe results alongside regular eval results |
| Temporal infrastructure | Orchestrate ProbeRun lifecycle |

### 6.2 What to Add

| New Component | Location | Purpose |
|---|---|---|
| `Probe` model | `models/probe.py` | Probe registry |
| `ProbeRun / ProbeRunItem` models | `models/probe.py` | Coordination layer |
| Probe API routes | `api/routers/probes.py` | Agent + management endpoints |
| `ProbeRunWorkflow` | `workflows/probe_run.py` | Temporal orchestration |
| Probe activities | `activities/probe_run.py` | Task dispatch, wait, analyze |
| `ComparisonEngine` | `evaluation_v2/comparison.py` | Statistical analysis |
| `probe-agent` CLI | `probe_agent/` (separate package) | Agent binary |
| `NetworkMetrics` collector | `probe_agent/network.py` | Network measurement |

### 6.3 What to Refactor in Current Code

The current `EvalScopeBuiltinExecutor` runs in-process within the Temporal worker. For probe-side execution, we need to make it **independently runnable**:

```python
# Current: tightly coupled to Temporal activity
async def activity_execute_evaluation_run_item(run_id, item_id):
    plan = load_plan_from_db(item_id)
    adapter = get_engine_adapter(plan.engine, plan.execution_mode)
    result = adapter.execute(plan, context)   # ← This is what the probe needs
    persist_to_db(result)

# Target: extract execution core as standalone
def execute_benchmark(item_plan: CompiledRunItemPlan, output_dir: Path) -> CanonicalExecutionResult:
    """
    Pure function. No DB, no S3, no Temporal.
    Input: plan + output dir.
    Output: canonical result.
    Usable both in Temporal activity AND in probe agent.
    """
    adapter = get_engine_adapter(item_plan.engine, item_plan.execution_mode)
    context = ExecutionContext(output_dir=output_dir)
    return adapter.execute(item_plan, context)
```

This refactor is minimal and backwards-compatible — the existing `activity_execute_evaluation_run_item` simply calls `execute_benchmark` internally.

---

## 7. Probe Agent Packaging & Deployment

### 7.1 Package Structure

```
nta-probe-agent/
├── pyproject.toml           # Standalone package, depends on evalscope + httpx
├── src/
│   └── nta_probe_agent/
│       ├── __init__.py
│       ├── cli.py            # CLI entry: probe-agent run/register/status
│       ├── agent.py          # ProbeAgent main loop
│       ├── config.py         # Config loading (env/file/flags)
│       ├── network.py        # VantagePoint detection + NetworkMetrics collection
│       ├── client.py         # Control plane HTTP client
│       ├── executor.py       # evalscope execution wrapper
│       └── models.py         # Local data models
├── Dockerfile
└── deploy/
    ├── docker-compose.yml    # Multi-region deploy template
    └── terraform/            # Cloud VM provisioning
```

### 7.2 Configuration

```yaml
# probe-agent.yaml
control_plane:
  url: https://nta.example.com
  token: ${NTA_PROBE_TOKEN}

agent:
  name: "beijing-ct-01"
  poll_interval: 5s
  heartbeat_interval: 15s
  max_concurrent_tasks: 1     # Benchmarks should not compete for resources
  task_timeout: 2h

network:
  detect_vantage: true        # Auto-detect IP/ISP/geo
  overrides:                  # Manual overrides
    region: "cn-beijing"
    isp: "China Telecom"
    network_type: "cloud"
    tags: ["aliyun", "ecs"]
  collect_traceroute: false   # Disable on restricted networks

evalscope:
  cache_dir: ~/.nta-probe/benchmarks   # Local benchmark cache
  log_level: INFO
```

### 7.3 Deployment Patterns

**Pattern 1: Cloud VMs (recommended for initial rollout)**
```bash
# Deploy to multiple regions via Terraform/Pulumi
# Each region gets: 1 small VM → 1 probe-agent container
# Cost: ~$5-15/month per probe (t3.micro or equivalent)

# Beijing (Aliyun ECS)
docker run -d --name probe-beijing-ct \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=beijing-ct-01 \
  nta/probe-agent:latest

# US-East (AWS EC2)  
docker run -d --name probe-us-east \
  -e NTA_PROBE_TOKEN=xxx \
  -e NTA_PROBE_NAME=us-east-aws-01 \
  nta/probe-agent:latest
```

**Pattern 2: Residential/Mobile via VPN exits**
```bash
# For testing residential ISP paths:
# Run probe behind specific VPN exit nodes
docker run -d --net=container:vpn-china-telecom \
  nta/probe-agent:latest
```

**Pattern 3: Ephemeral (CI/Serverless)**
```bash
# Run once and exit — for on-demand probing
probe-agent run-once --task-id=xxx
```

---

## 8. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| API keys transit through probes | Probe receives encrypted `model_binding`; keys in control plane only, proxied or short-lived tokens |
| Rogue probe submits fake results | Probe authentication via signed tokens; result validation (score distribution checks) |
| Network metadata privacy | IP/ISP data scoped to project, not publicly shared |
| Probe compromise | Minimal permissions; probe can only claim its own tasks, read-only benchmark data |

**API key handling — two strategies**:

1. **Key-in-plan** (simpler): Pass `api_key` in `ModelBindingSnapshot` to probe. Acceptable for internal/trusted probes.
2. **Proxy mode** (more secure): Probe calls control plane's proxy endpoint; control plane injects the key and forwards to LLM API. Adds latency but protects keys. **Not recommended for this use case** — it defeats the purpose of testing from the probe's IP.

**Recommendation**: Use short-lived, scoped API tokens where providers support them. For providers that don't, accept key-in-plan with encrypted transit.

---

## 9. Implementation Phases

### Phase 1: Foundation (MVP)

**Goal**: Prove the concept with 2-3 manually deployed probes.

- [ ] Probe registry model + API (register, heartbeat, list)
- [ ] ProbeRun / ProbeRunItem models
- [ ] Probe task claim/complete API
- [ ] Minimal probe agent CLI (`probe-agent run`)
- [ ] Repackage `EvalScopeBuiltinExecutor` as standalone function
- [ ] Basic network metadata detection (IP, geo, ISP)
- [ ] Manual ProbeRun creation via API
- [ ] Simple comparison: average score per probe, no statistics

**Deliverable**: Can create a ProbeRun, have 2 probes execute it, see scores side by side.

### Phase 2: Analysis & Automation

**Goal**: Statistical rigor and automated orchestration.

- [ ] Temporal ProbeRunWorkflow
- [ ] ComparisonEngine with statistical tests
- [ ] DegradationReport generation
- [ ] Frontend dashboard for ProbeRun results
- [ ] Probe health monitoring (missed heartbeats → offline)
- [ ] Benchmark suite `network-probe-standard` curated
- [ ] Docker image + deploy scripts

**Deliverable**: One-click "run network probe test", automated comparison with p-values and degradation classification.

### Phase 3: Scale & Intelligence

**Goal**: Continuous monitoring and trend detection.

- [ ] Scheduled ProbeRuns (cron-based recurring tests)
- [ ] Historical trend analysis (degradation over time)
- [ ] Alert rules (score drops > threshold → notification)
- [ ] Probe auto-enrollment (new probe joins → auto-included in future runs)
- [ ] A/B network path testing (same probe, different DNS/route)
- [ ] Integration with existing Leaderboard (probes as leaderboard dimensions)

---

## 10. Open Questions

1. **Benchmark data distribution**: Should probes download benchmark datasets from S3/CDN, or bundle them in the Docker image? Trade-off: image size vs. freshness.

2. **Key rotation**: How frequently should probe auth tokens be rotated? Per-run or long-lived?

3. **Provider ToS**: Some LLM providers may restrict automated benchmarking from multiple IPs. Need per-provider compliance review.

4. **Baseline definition**: Which probe's score is the "baseline" for degradation calculation? Options:
   - Best-performing probe
   - Provider's home region (e.g., US for OpenAI)
   - Historical average

5. **Cost management**: Running benchmarks (hundreds of API calls) from N probes × M repetitions. Budget controls needed?

---

## Appendix A: Comparison with Multica Approach

| Aspect | Multica Daemon | NTA Probe Agent |
|--------|---------------|-----------------|
| **Purpose** | Execute AI agent tasks (coding, PR reviews) | Execute evalscope benchmarks |
| **Runtime** | Claude Code / Codex CLI | evalscope evaluator |
| **Registration** | Auto-detect AI CLIs | Auto-detect network identity |
| **Task type** | Issue → code changes | Benchmark → score + metrics |
| **Concurrency** | 20 parallel tasks | 1 task (benchmark needs isolation) |
| **Workspace** | Git repo checkout per task | Benchmark data cache |
| **Output** | Code diff, PR, comments | Scores, latency, network metrics |
| **Borrowed** | Registration/heartbeat, poll-based claiming, task state machine | — |
| **Not borrowed** | Workspace management, session reuse, skill injection | — |

## Appendix B: Relevant Existing Files

```
backend/src/nta_backend/
├── evaluation_v2/
│   ├── compiler.py                    # compile_run_request() — reuse
│   ├── engine_registry.py             # get_engine_adapter() — reuse
│   └── execution/
│       ├── contracts.py               # CanonicalExecutionResult — reuse
│       └── evalscope_builtin.py       # EvalScopeBuiltinExecutor — extract core
├── workflows/
│   └── evaluation_run.py              # Pattern to follow for ProbeRunWorkflow
├── activities/
│   └── evaluation_run.py              # Pattern to follow for probe activities
├── models/
│   └── evaluation_v2.py               # EvaluationRun — delegated to by ProbeRunItem
├── schemas/
│   └── evaluation_v2.py               # CompiledRunItemPlan, ModelBindingSnapshot — reuse
└── services/
    └── evaluation_run_v2_service.py   # Execution pipeline — reuse for result persistence
```
