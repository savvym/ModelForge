
重新理解场景

  Probe Beijing  ──┐
  Probe Tokyo    ──┼──→  同一个 Provider API (e.g. OpenAI)
  Probe Virginia ──┘          ↓
                       响应是否一致？
                       - 延迟差异
                       - 模型路由差异（是否给了同一个模型）
                       - 输出质量/分数差异
                       - 限流策略差异
                       - 内容审核差异

  核心问题是：同 prompt 同 provider，不同来源的请求，拿到的结果有没有区别？

  架构设计

  ┌─────────────────────────────────────────────┐
  │             Bench Control Plane             │
  │                                             │
  │  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
  │  │ Task    │  │ Compare  │  │ Dashboard │  │
  │  │ Dispatch│  │ Engine   │  │ (diff view)│  │
  │  └─────────┘  └──────────┘  └───────────┘  │
  └──────┬──────────────┬───────────────┬───────┘
         │              │               │
     ┌───▼───┐    ┌─────▼────┐   ┌──────▼─────┐
     │ Probe │    │  Probe   │   │   Probe    │
     │Beijing│    │  Tokyo   │   │  Virginia  │
     │ IP: x │    │  IP: y   │   │   IP: z    │
     └───┬───┘    └────┬─────┘   └─────┬──────┘
         │             │               │
         └─────────────┼───────────────┘
                       ▼
              Provider API (OpenAI / Claude / ...)

  关键设计差异（对比之前的方案）

  1. 任务模型变了：一个"实验"派发给多个 probe

  之前是"一个任务一个 probe 跑"，现在是：

  # Experiment（实验） —— 控制面的核心实体
  {
      "id": "exp-uuid",
      "name": "GPT-4o MMLU 地域差异测试",
      "provider": "openai",
      "model": "gpt-4o",
      "eval_config": {
          "datasets": ["mmlu"],
          "limit": 200,
          "temperature": 0,        # 固定参数，消除随机性
          "seed": 42,              # 如果 provider 支持
      },
      "dispatch": {
          "target_probes": ["beijing-01", "tokyo-01", "virginia-01"],
          # 或者按标签：
          "target_tags": ["region:asia", "region:us"],
          "repeat": 3,             # 每个 probe 跑 3 次（检测一致性）
      }
  }

  # 一个实验展开成 N 个 Task（每个 probe 一个）
  # Experiment 1:N Task

  2. Probe 注册：地域/网络信息是一等公民

  # POST /api/probes/register
  {
      "probe_id": "beijing-01",
      "device_name": "Aliyun ECS Beijing",

      # 这些是核心维度，不是附属信息
      "location": {
          "region": "cn-beijing",
          "provider": "aliyun",        # 机器在哪个云
          "ip": "47.93.xx.xx",         # 出口 IP
          "geo": {"lat": 39.9, "lon": 116.4},
      },

      "network": {
          "asn": "AS37963",
          "isp": "Alibaba Cloud",
      },

      "capabilities": {
          "reachable_providers": ["openai", "dashscope", "anthropic"],
          "evalscope_version": "0.6.4",
          "max_concurrent": 3,
      }
  }

  Probe 启动时可以自动探测这些：

  async def detect_location(self) -> LocationInfo:
      """自动探测 probe 的网络环境"""
      # 调一个 IP 地理位置 API
      info = await self.http.get("https://ipinfo.io/json")
      return LocationInfo(
          ip=info["ip"],
          region=info["region"],
          country=info["country"],
          asn=info["org"],
          geo={"lat": ..., "lon": ...},
      )

  3. 任务执行：必须记录请求级元数据

  普通评测只关心分数，你需要每个请求都记录网络层信息：

  @dataclass
  class ProbeRequestRecord:
      """每次 API 调用的完整记录"""
      # 请求标识
      prompt_hash: str            # 同一 prompt 跨 probe 对比的 key
      dataset: str
      sample_index: int

      # 响应内容
      response_text: str
      finish_reason: str

      # 网络/延迟指标 —— 这是核心
      latency_ms: float           # 总延迟
      ttfb_ms: float              # Time to First Byte（首 token 延迟）
      dns_resolve_ms: float       # DNS 解析
      tcp_connect_ms: float       # TCP 握手
      tls_handshake_ms: float     # TLS 握手
      server_ip: str              # 实际连接的服务器 IP（检测 CDN 路由）

      # 响应头信息 —— 检测路由差异
      response_headers: dict      # 例如 x-ratelimit-*, cf-ray, server 等
      http_status: int

      # 模型指纹 —— 检测是否给了同一个模型
      token_count: int
      model_id_returned: str      # API 返回的实际 model ID
      system_fingerprint: str     # OpenAI 返回的 system_fingerprint

      timestamp: datetime

  4. Executor 改造：包装 HTTP 层

  不能直接用 evalscope 的默认 HTTP client，需要加一层采集网络指标：

  class InstrumentedModelClient:
      """包装 API 调用，采集请求级元数据"""

      def __init__(self, base_client, recorder: RequestRecorder):
          self.base_client = base_client
          self.recorder = recorder

      async def chat_completion(self, messages, **kwargs):
          start = time.monotonic()

          # 用 urllib3/httpx 的底层 hook 采集网络指标
          with self.recorder.trace() as trace:
              response = await self.base_client.chat_completion(messages, **kwargs)

          trace.record(
              latency_ms=(time.monotonic() - start) * 1000,
              ttfb_ms=trace.ttfb_ms,
              server_ip=trace.peer_address,
              response_headers=dict(response.headers),
              model_id_returned=response.model,
              system_fingerprint=response.system_fingerprint,
          )

          return response

  5. 结果上报：按 probe 维度

  # POST /api/tasks/{task_id}/complete
  {
      "probe_id": "beijing-01",
      "experiment_id": "exp-uuid",

      # 聚合分数
      "scores": {"mmlu": 0.872},

      # 网络指标聚合
      "network_stats": {
          "latency_p50_ms": 320,
          "latency_p99_ms": 890,
          "ttfb_p50_ms": 180,
          "dns_resolve_avg_ms": 12,
          "server_ips_seen": ["104.18.1.1", "104.18.1.2"],  # 看路由了几个节点
          "error_rate": 0.02,
          "rate_limited_count": 3,
      },

      # 模型指纹
      "model_fingerprints": {
          "model_ids_returned": ["gpt-4o-2024-08-06"],
          "system_fingerprints": ["fp_abc123", "fp_def456"],  # 多个说明后端有切换
      },

      # 逐条记录（用于详细对比）
      "request_records_url": "/artifacts/exp-uuid/beijing-01/records.jsonl"
  }

  6. 对比引擎（Control Plane 新增）

  这是 multica 完全没有的，是你系统的核心价值：

  class CompareEngine:
      """跨 probe 对比同一实验的结果"""

      def compare(self, experiment_id: str) -> CompareReport:
          results = self.db.get_results_by_experiment(experiment_id)

          return CompareReport(
              # 分数差异 —— 同 prompt 不同 probe 得分是否一致
              score_diff=self.compare_scores(results),

              # 延迟差异
              latency_diff=self.compare_latency(results),

              # 路由差异 —— 不同 probe 连接的服务器 IP 是否相同
              routing_diff=self.compare_server_ips(results),

              # 模型差异 —— system_fingerprint 是否一致
              model_diff=self.compare_fingerprints(results),

              # 输出一致性 —— 同 prompt + seed，不同 probe 的输出是否相同
              output_consistency=self.compare_outputs(results),

              # 限流差异 —— 某些地区是否更容易被限流
              rate_limit_diff=self.compare_rate_limits(results),
          )

  最终数据模型

  Experiment (实验)
   ├── provider: "openai"
   ├── model: "gpt-4o"
   ├── eval_config: { datasets, limit, seed, temperature }
   │
   ├── Task (beijing-01, run #1)
   │    ├── probe_location: { region, ip, asn }
   │    ├── scores: { mmlu: 0.872 }
   │    ├── network_stats: { latency_p50, server_ips, ... }
   │    └── request_records: [ {prompt_hash, response, latency, server_ip, ...}, ... ]
   │
   ├── Task (tokyo-01, run #1)
   │    └── ...
   │
   ├── Task (virginia-01, run #1)
   │    └── ...
   │
   └── CompareReport
        ├── score_diff: { max_delta: 0.03, significant: false }
        ├── latency_diff: { beijing: 320ms, tokyo: 180ms, virginia: 45ms }
        ├── routing_diff: { beijing→104.18.1.1, virginia→104.18.2.5 }
        └── output_consistency: 0.97 (97% 输出完全一致)

  推荐目录结构

  llm-bench/
  ├── server/
  │   ├── api/
  │   │   ├── experiments.py     # 实验 CRUD + 派发
  │   │   ├── probes.py          # probe 注册/心跳
  │   │   ├── tasks.py           # 任务 claim/complete
  │   │   └── compare.py         # 对比结果查询
  │   ├── engine/
  │   │   └── compare.py         # 跨 probe 对比引擎
  │   └── models/
  │       ├── experiment.py
  │       ├── task.py
  │       └── probe.py
  │
  ├── probe/
  │   ├── daemon.py              # 主循环
  │   ├── client.py              # server API 调用
  │   ├── executor.py            # evalscope 执行
  │   ├── instrument.py          # HTTP 层插桩，采集网络指标
  │   ├── location.py            # 自动探测 IP/地域/ASN
  │   └── config.py
  │
  └── cli/
      └── main.py                # probe start | server start

  一句话总结

  和 multica daemon 的本质区别：multica 是"一个任务派给一个 daemon
  执行"，你是**"一个实验同时派给多个 probe，对比它们看到的世界是否一样"**。Probe
  的身份（IP、地域、ASN）不是运维信息，而是实验的核心自变量。
