# NTA Probe Agent

`probe/` 是独立分发的探针项目，负责：

- 节点自动注册
- 心跳和健康信息上报
- 拉取并执行分配给本节点的任务
- 回传任务结果

当前任务执行器先对接 `evalscope perf`。

## Quick Start

```bash
cd probe
export NTA_PROBE_SERVER_BASE_URL=http://127.0.0.1:8000
export NTA_PROBE_PROJECT_ID=<project-id>
export OPENAI_API_KEY=<api-key>
uv run nta-probe-agent run
```

## Environment Variables

- `NTA_PROBE_SERVER_BASE_URL`: 控制面地址
- `NTA_PROBE_PROJECT_ID`: 项目标识，可选
- `NTA_PROBE_REGISTRATION_TOKEN`: 注册 token，可选
- `NTA_PROBE_NAME`: 探针名，可选
- `NTA_PROBE_DISPLAY_NAME`: 展示名，可选
- `NTA_PROBE_TAGS`: 逗号分隔标签，可选
- `NTA_PROBE_STATE_ROOT`: 默认状态目录
- `NTA_PROBE_STATE_PATH`: 状态文件路径
- `NTA_PROBE_WORK_DIR`: 任务工作目录
- `NTA_PROBE_EVALSCOPE_BIN`: 自定义 `evalscope` 可执行文件路径
