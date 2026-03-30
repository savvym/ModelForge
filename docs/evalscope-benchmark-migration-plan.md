# EvalScope Benchmark Migration Plan

## 1. 当前判断

### 1.1 Benchmark prompt 现在是不是写在代码里

当前这套实现里，**是的，benchmark 的 prompt 相关定义主要在代码里**。

以 `cl_bench` 为例：

- benchmark type 元信息在 [cl_bench.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_core/benchmarks/cl_bench.py)
- sample schema / prompt schema / 默认 prompt config 在 [contracts.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_catalog/contracts.py)
- judge 的默认 grading prompt 在 [cl_bench_judge.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_core/metrics/cl_bench_judge.py)

也就是说，当前不是“数据库里定义 benchmark prompt”，而是“代码里定义 benchmark type 的 contract 和默认 prompt 行为”。

### 1.2 Benchmark 列表是不是通过 DB 记录读取

**现在不是。**

当前 benchmark 列表接口的事实来源是代码注册表，而不是数据库定义表。

对应实现：

- benchmark type 从 `BenchmarkMeta` 注册表导出，在 [benchmark.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_core/api/benchmark.py) 和 [registry.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_core/api/registry.py)
- catalog 接口在 [benchmark_catalog_service.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/services/benchmark_catalog_service.py) 里读取代码 benchmark type，再拼接数据库中的 version 和使用统计

数据库当前只承担：

- `Benchmark Version`
- version 样本数
- version 启停状态
- 项目内运行统计

## 2. 和 EvalScope 对齐后的正确模型

更接近 `EvalScope` 的方式应该是：

- `Benchmark Type`：代码定义
- `Benchmark Version`：数据库管理

### 2.1 Benchmark Type

应该对应 `EvalScope` 仓库里的：

- `benchmarks/<benchmark_name>/`
- `benchmarks/_meta/<benchmark_name>.json`

它负责：

- adapter / `to_sample`
- 执行逻辑
- metric 装配
- prompt 模板或 prompt 资产
- 原始数据格式 contract

### 2.2 Benchmark Version

系统里只管理某个 benchmark type 的数据版本：

- 数据源 URI
- 样本数
- 启停状态
- 说明

## 3. 一个关键澄清

“prompt 写在代码里”这句话要更精确一点。

在 `EvalScope` 里，prompt 不一定全部写成 Python 字符串常量：

- 有些在 adapter 代码里
- 有些在 benchmark 目录下的 prompt 资源文件里
- 有些依赖 `_meta` 里的说明和 sample example

例如：

- `cl_bench` 的 grading prompt 主要在 adapter 代码里
- `bbh` 有单独的 `cot_prompts/` 目录

所以我们后续的目标不应该是“所有 prompt 都写死在 Python 里”，而应该是：

- **benchmark type 的全部定义都来自代码仓库**
- 可以是 Python 代码
- 也可以是代码仓库里的 sidecar manifest / prompt asset 文件

## 4. 当前系统最适合的实现方式

建议收成下面这条线：

### 4.1 代码仓库是 Benchmark Type 的唯一来源

后续 benchmark type 统一来自：

- `backend/src/nta_backend/eval_core/benchmarks/<benchmark_name>/`
- `backend/src/nta_backend/eval_core/benchmarks/_meta/<benchmark_name>.json`

数据库不再创建或编辑 benchmark type。

### 4.2 数据库只管理 Benchmark Version

数据库只保留：

- 某个 benchmark type 的多个 version
- 每个 version 的数据源 URI
- `sample_count`
- 启停状态
- 使用统计

## 5. 全量移植 EvalScope benchmarks 的现实边界

`references/evalscope/evalscope/benchmarks/` 当前有 **119** 个 benchmark 目录。

这件事不能简单理解成“把 119 个目录原样 copy 过来就能跑”。

因为这些 benchmark 分成完全不同的执行家族：

### 5.1 纯文本 QA / MCQ 家族

这类最容易先迁：

- `mmlu`
- `ceval`
- `cmmlu`
- `arc`
- `hellaswag`
- `gsm8k`
- `truthful_qa`
- `piqa`
- `qasc`
- `sciq`
- `race`

这类通常能复用少量通用 adapter family。

### 5.2 通用配置型 benchmark

- `general_qa`
- `general_mcq`
- `general_vqa`
- `general_vmcq`
- `general_fc`
- `general_arena`

这类实际上最适合先做成平台里的通用 benchmark type 基座。

### 5.3 Judge 型 / 指令遵循型

- `cl_bench`
- `ifeval`
- `arena_hard`
- `alpaca_eval`
- `eq_bench`
- `healthbench`

这类重点是 judge prompt、评分协议和解释抽取。

### 5.4 代码执行型

- `humaneval`
- `humanevalplus`
- `mbpp`
- `mbppplus`
- `live_code_bench`
- `scicode`
- `swe_bench`
- `terminal_bench`

这类不只是 adapter 问题，还涉及：

- 沙箱
- 执行环境
- docker / runner
- 安全边界

### 5.5 多模态视觉 / 文档 / OCR

- `mmmu`
- `mmmu_pro`
- `mmmu_pro`
- `docvqa`
- `chartqa`
- `math_vista`
- `math_vision`
- `ocr_bench`
- `hallusion_bench`
- `seed_bench_2_plus`

这类要求：

- 图片/文档输入管线
- 媒体文件 version 管理
- 可能不同的 model API 能力

### 5.6 工具 / Agent / 环境交互

- `bfcl`
- `tool_bench`
- `tau_bench`
- `ifbench`
- `multi_if`
- `openai_mrcr`

这类需要工具执行环境，不适合在当前版本一次做完。

### 5.7 音频 / 语音

- `librispeech`
- `fleurs`
- `torgo`

这类要求音频输入链路。

## 6. 所以“全部移植”应该怎么做

正确方式不是一次性全部实现执行逻辑，而是分三层推进：

### Phase 1

先把 **所有 EvalScope benchmark type 元信息** 接进来。

也就是：

- 把 `_meta/*.json` 映射成平台里的 benchmark type 展示信息
- 让系统先能“看见所有 benchmark type”

这一步是 metadata migration，不是 full runtime migration。

### Phase 2

按 benchmark family 逐步补 runtime。

优先级建议：

1. `general_qa` / `general_mcq`
2. `mmlu` / `ceval` / `cmmlu` / `arc` / `hellaswag`
3. `gsm8k` / `math_500` / `truthful_qa`
4. `cl_bench` / `ifeval` / `alpaca_eval`

### Phase 3

再补高复杂度 benchmark：

- code execution
- multimodal
- tool / agent
- audio

## 7. 推荐的目标形态

我建议后续改成：

```text
backend/src/nta_backend/eval_core/benchmarks/
  _meta/
    cl_bench.json
    mmlu.json
    general_qa.json
    ...
  cl_bench/
    __init__.py
    adapter.py
    prompts/
  mmlu/
    __init__.py
    adapter.py
  general_mcq/
    __init__.py
    adapter.py
```

然后：

- benchmark list API 读取代码侧 manifest + runtime registry
- benchmark detail 展示 manifest、schema、prompt contract
- DB 只保存 version

## 8. 结论

对你刚才两个问题，答案是：

1. **当前实现里，benchmark 的 prompt/contract 主要是写在代码里的。**
2. **当前 benchmark 列表接口也已经不是 DB 事实来源，而是代码注册表来源，DB 只承担 version 和统计。**

而“把 EvalScope benchmarks 下所有 benchmark type 都移植过来”这件事，最合理的做法是：

- 先全量移植 **benchmark type metadata**
- 再按 family 分批移植 **runtime**

这样才是可落地的，不会一开始就把 119 个 benchmark 的执行复杂度全部压进当前系统。
