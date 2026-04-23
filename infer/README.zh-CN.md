# NTA Infer Agent

`infer-agent` 部署在推理机器上，负责接收控制面下发的部署期望态，下载模型制品，启动或切换 vLLM 容器，并把整个部署过程记录为可查询事件。

当前 MVP 的目标：

- 控制面能访问 H20 机器，H20 不需要访问控制面。
- H20 暴露 `infer-agent` HTTP 服务给控制面。
- 一台机器同时维护一个 active vLLM 部署。
- 模型目录若已缓存则直接切换；未缓存则从 Hugging Face 或 COS/S3 下载。
- 部署过程通过 `/v1/deployments/current` 和 `/v1/events/recent` 追踪。

## 1. H20 机器前置条件

在 H20 机器上准备：

```bash
nvidia-smi
docker --version
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

如果 Docker 容器看不到 GPU，需要先安装 NVIDIA Container Toolkit。

建议目录：

```bash
sudo mkdir -p /data/model-cache /data/nta-runtime /var/lib/infer-agent
sudo chown -R "$USER":"$USER" /data/model-cache /data/nta-runtime /var/lib/infer-agent
```

## 2. 安装 agent

在仓库根目录执行：

```bash
cd infer
uv sync
```

本地试运行：

```bash
cp .env.example .env
vim .env
uv run nta-infer-agent
```

`.env` 至少需要确认这几项，其中 `INFER_AGENT_TOKEN` 必须配置，不能为空：

```bash
INFER_AGENT_TOKEN=replace-with-a-long-random-token
NODE_NAME=h20-node-01
MODEL_CACHE_DIR=/data/model-cache
RUNTIME_DIR=/data/nta-runtime
RUNTIME_PUBLIC_HOST=10.0.0.12
HF_TOKEN=hf_xxx_optional_for_private_repos
MAX_RUNTIME_RESTARTS=3
```

`RUNTIME_PUBLIC_HOST` 必须填写控制面可访问到的 H20 地址。否则 agent 会把 vLLM endpoint 报成 `http://127.0.0.1:8000/v1`，控制面从自己的本机访问这个地址时会命中错误服务。

`MAX_RUNTIME_RESTARTS` 控制 vLLM 容器异常退出后的 Docker 重试次数，默认 3 次。超过次数后 infer-agent 会把当前部署标记为失败，并清理 vLLM 容器，避免无限重启。

infer-agent 的 `9000` 管理端口会保护所有 HTTP URL，包括 `/v1/*` 和不存在的路径。所有请求都必须带：

```http
Authorization: Bearer $INFER_AGENT_TOKEN
```

`/docs`、`/redoc` 和 `/openapi.json` 不开放；无论是否带 token，访问都会返回 404。

默认监听：

```text
http://0.0.0.0:9000
```

控制面需要能访问：

```text
http://10.0.0.12:9000
```

## 3. systemd 部署

复制服务文件：

```bash
sudo cp infer/systemd/infer-agent.service /etc/systemd/system/infer-agent.service
sudo mkdir -p /etc/infer-agent
sudo cp infer/.env.example /etc/infer-agent/env
sudo vim /etc/infer-agent/env
```

`/etc/infer-agent/env` 使用和 `infer/.env` 相同的格式。最小示例：

```bash
HOST=0.0.0.0
PORT=9000
NODE_NAME=h20-node-01
INFER_AGENT_TOKEN=replace-with-a-long-random-token
MODEL_CACHE_DIR=/data/model-cache
RUNTIME_DIR=/data/nta-runtime
RUNTIME_PUBLIC_HOST=10.0.0.12
DEFAULT_VLLM_IMAGE=vllm/vllm-openai:latest
HF_TOKEN=hf_xxx_optional_for_private_repos
MAX_RUNTIME_RESTARTS=3
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now infer-agent
sudo systemctl status infer-agent
```

查看日志：

```bash
journalctl -u infer-agent -f
```

## 4. 控制面配置

在控制面进入“在线推理 / 推理机器”，新增已经部署 infer-agent 的机器：

- Agent URL：例如 `http://10.0.0.12:9000`
- Agent Token：与 H20 机器上 `INFER_AGENT_TOKEN` 保持一致
- Runtime API Key：由控制面下发给 vLLM，调用 `:8000/v1/*` 时使用 `Authorization: Bearer <Runtime API Key>`
- Runtime Public Host：例如 `10.0.0.12`
- vLLM Image：例如 `vllm/vllm-openai:latest`
- Tensor Parallel Size：例如 `8`
- Dtype：例如 `bfloat16`
- GPU Memory Utilization：例如 `0.85`
- Listen Port：例如 `8000`

infer-agent 启动 vLLM 容器时会直接使用 Docker `--gpus all`，机器上的 GPU 明细由健康检查接口回传给控制面展示。

控制面仍保留 `INFER_AGENT_BASE_URL`、`INFER_AGENT_TOKEN` 等环境变量作为历史兼容兜底；新部署建议在“推理机器”里维护资源池，并在“我的模型”点击部署时选择目标机器。

如果 H20 能稳定访问 Hugging Face，推荐优先在“系统管理 / 系统配置”里配置 Hugging Face Token，然后在“我的模型”里选择 Hugging Face，登记 `repo_id` 和 `revision` 后直接部署。私有仓库可以二选一：

- 在 H20 的 `/etc/infer-agent/env` 中配置 `HF_TOKEN`，由 agent 本机使用。
- 在控制面的“系统配置”里配置 HF Token，部署时随 spec 下发给 agent。

如果后续恢复 COS 内网访问，也可以继续配置 `INFER_OBJECT_STORAGE_ENDPOINT_URL` 走 COS/S3 源。控制面会把对象存储只读凭据随部署 spec 下发给 agent。生产环境建议改成 STS 临时凭据，限制 bucket/prefix 和有效期。

## 5. API 验证

健康检查：

```bash
curl -H "Authorization: Bearer $INFER_AGENT_TOKEN" \
  http://10.0.0.12:9000/v1/health
```

查看当前部署状态：

```bash
curl -H "Authorization: Bearer $INFER_AGENT_TOKEN" \
  http://10.0.0.12:9000/v1/deployments/current
```

查看最近事件：

```bash
curl -H "Authorization: Bearer $INFER_AGENT_TOKEN" \
  'http://10.0.0.12:9000/v1/events/recent?limit=50'
```

停止当前 vLLM：

```bash
curl -X DELETE -H "Authorization: Bearer $INFER_AGENT_TOKEN" \
  http://10.0.0.12:9000/v1/deployments/current
```

## 6. 部署流程

控制面点击“部署”后：

```text
Backend
  -> 创建 endpoint 部署记录
  -> 生成 DeploymentSpec
  -> PUT /v1/deployments/current 到 H20 infer-agent

infer-agent
  -> SQLite 保存 desired_state
  -> Reconciler 检查本地缓存
  -> 未命中则从 Hugging Face 或 COS/S3 下载模型
  -> 停止旧 nta-vllm 容器
  -> docker run vllm/vllm-openai
  -> 等待 /health 和 /v1/models
  -> smoke test
  -> 状态 ready，返回访问链接
```

vLLM 对外地址：

```text
http://{RUNTIME_PUBLIC_HOST}:8000/v1
```

## 7. 端口与安全

建议：

- `9000` 只允许控制面 Backend 访问。
- `8000` 只允许控制面、评测服务和需要调用模型的内网服务访问，并必须带 Runtime API Key。
- 不要暴露 Docker socket。
- `INFER_AGENT_TOKEN` 是必填项，使用长随机字符串；未配置或为空时 infer-agent 不会启动。
- `9000` 上所有 HTTP URL 都必须使用 `Authorization: Bearer $INFER_AGENT_TOKEN` 访问。
- vLLM runtime 启动时必须带 `--api-key`，`/v1/models`、`/v1/chat/completions` 等 runtime API 都必须使用 Runtime API Key。
- 生产环境把对象存储长期 AK/SK 替换为 STS 临时凭据。
