# Eval Core Roadmap

## 1. 目标

把当前模型评测能力收敛到一条更接近 `EvalScope` 的主线：

- 平台里选择的是 `Benchmark`，不是把 benchmark 冒充成 dataset
- 评测内核围绕统一 `Sample`、注册表、`Evaluator`、`Metric` 组织
- 平台任务系统只负责创建、调度、状态和结果展示
- benchmark、dataset、model、report 四层边界清晰

## 2. 当前结论

### 2.1 现在已经完成的部分

- 已有独立评测内核：`backend/src/nta_backend/eval_core/`
- 已有统一入口：`run_task()`
- 已有注册表骨架：benchmark / model / metric / evaluator
- 已有第一个真实 benchmark：`cl_bench`
- 已有 OpenAI-compatible model，支持 `responses`
- 已能从系统创建页真实发起任务
- 已能后台执行 `CL-bench Smoke (1条/10条)` 并把状态写回列表
- 已把聚合指标写入 `eval_job_metrics`
- 已把 `report.json` 落到本地 `.evalruns`
- 已有数据库版 `Benchmark Catalog`
- 已有 `Benchmark` / `Benchmark Version` 管理目录与详情页
- `EvalJob` 已有 benchmark/version 一等持久化字段
- `Benchmark` 已持久化样本 schema、prompt schema、prompt 默认配置
- `Benchmark Version` 在创建/更新时会校验数据格式并自动计算 `sample_count`

### 2.2 现在还不是最终形态的部分

- 当前只有 `CL-bench` 及其 smoke version，Benchmark 查看与 Version 管理仍处于第一版
- 详情页、导出、停止、删除仍未恢复
- `eval_core` 还只有一个 benchmark 和一个 judge metric
- 结果目前主要落本地文件，没有形成统一 artifacts 读取层
- Benchmark Catalog 还没有删除、审计和权限控制

结论：

当前版本是“系统链路已打通”的里程碑，不是“EvalScope 风格架构已经完成”。

## 3. 正确的领域模型

后续应该把下面四个概念分开：

### 3.1 Benchmark

代码里注册的评测定义，例如：

- `cl_bench`
- `mmlu_mcq`
- `generic_qa`

它决定：

- 支持什么样本格式
- prompt 相关配置长什么样
- 默认 prompt 配置是什么
- 用哪个 adapter
- 默认 metric 是什么
- 默认 aggregator 是什么
- 有哪些 subset / version / variant

### 3.2 Benchmark Version

benchmark 的一个可直接运行配置，例如：

- `cl_bench_smoke_1`
- `cl_bench_smoke_10`
- `mmlu_abstract_algebra_20`

它不是用户上传 dataset，也不是 DB 里的 dataset version。

它应该描述：

- benchmark 名称
- 数据源 URI
- 数据校验后的 `sample_count`
- 展示名称和说明

它在创建或更新时应该做：

- 按 benchmark 的 sample schema 校验 JSONL 每一行
- 计算样本总数
- 把规范化后的数据源信息和 `sample_count` 落库

### 3.3 Dataset Asset

用户上传或从对象存储导入的真实数据文件。

它服务于：

- 自定义 benchmark 输入
- benchmark 的外部数据源
- 训练/评测数据管理

它不应该替代 benchmark catalog。

### 3.4 Eval Run

一次真实评测任务。

它关联：

- benchmark
- benchmark version
- model
- judge model
- 输出 artifacts
- 聚合指标

## 4. 对照总规划的进度

### 4.1 已完成

#### Phase A: 单机评测内核

- `Sample`
- registry
- `DefaultEvaluator`
- `OpenAICompatibleModel`
- `CLBenchBenchmark`
- `CLBenchJudgeMetric`
- `MeanAggregator`
- `report.json`

#### Phase B: 系统触发最小闭环

- 创建页真实提交
- `POST /eval-jobs` 真实创建
- 后台异步执行 `eval_core`
- 任务状态从 `queued -> inferencing -> completed`
- 指标回写数据库

### 4.2 部分完成

#### Phase C: 平台桥接

已做：

- 可以从平台选 provider/model
- 可以把平台里的 model/provider 配置映射到 `eval_core`
- 已有数据库版 benchmark catalog
- 已有 benchmark/version 管理 API
- 已有 benchmark/version 创建与编辑页面
- `EvalJob` 已持久化 benchmark/version 字段
- `Benchmark` 已支持 schema / prompt contract 管理
- `Benchmark Version` 已支持入库校验和样本数自动计算

未做：

- 统一 artifacts 读取层

### 4.3 未开始或基本未开始

#### Phase D: EvalScope 风格产品层

- 详情页展示样本级结果
- subset/version/metric 可视化
- 报告导出
- 停止/删除/重跑

#### Phase E: 扩展层

- 多 benchmark
- 多 adapter
- 多 metric
- judge 模板管理
- 缓存
- 并发
- Temporal / distributed execution

## 5. 当前偏差

### 5.1 最大偏差

目前系统虽然已经能按 Benchmark 运行，也已经有数据库版 catalog，但 catalog 还只完成了第一版 CRUD。

这在产品语义上是错位的。

正确方式应该是：

1. 先选 `Benchmark`
2. 再选 `Benchmark Version`
3. 数据集版本统一在 Benchmark 查看页下维护，不在创建任务页临时上传或导入

### 5.2 为什么我现在先这么做

因为这能以最小改动打通整条系统链路：

- 不用先大改数据库
- 不用先重做整个创建页
- 不用先完成 benchmark catalog
- 可以尽快验证真实 provider + model + judge + report 是否跑得通

这个阶段的价值是“验证主线可行”，不是“定义最终产品形态”。

## 6. 下一步建议

接下来不要继续横向加很多 benchmark。优先把模型从“打通”收紧到“组织正确”。

建议顺序如下。

### Step 1: 完善 Benchmark 查看与 Version 管理

当前已支持：

- 查看代码定义的 Benchmark 类型
- 新增 Benchmark Version
- 编辑 Benchmark Version

接下来建议补：

- 删除 Version
- 操作审计
- 更细的启停与权限控制

### Step 2: 恢复评测详情结果面

优先恢复：

- 任务详情页展示 benchmark/version
- 聚合指标
- sample-level reason
- report/artifacts 路径

### Step 3: 统一 artifacts 读取层

把当前本地 `.evalruns` 读取收敛成稳定接口，避免前端或服务层直接耦合文件路径。

### Step 4: 扩 benchmark 与 metric

不要先做很多页面功能，优先继续扩：

- benchmark
- adapter
- metric
- judge 模板管理

### Step 4: 详情页恢复最小版

先恢复只读 detail，不恢复操作按钮。

最小版展示：

- benchmark / version / model / judge model
- status / timing
- 聚合指标
- `report.json` 中的 sample-level `reason`

### Step 5: 抽出 artifacts 读取层

不要让 detail 页直接读本地 `.evalruns` 路径字符串。

建议抽出：

- `EvalArtifactService`

统一负责：

- report 读取
- sample_scores 读取
- 结果路径解析
- 未来迁移到对象存储

## 7. 不建议的下一步

当前阶段不建议优先做这些：

- 一口气接很多 benchmark
- 先做 Temporal 恢复
- 先做分布式并发
- 先做复杂 rubric 管理后台
- 继续把 benchmark version 伪装成 dataset 选择

这些都不是现在的主矛盾。

## 8. 推荐的近期里程碑

### Milestone 1

- 引入 benchmark catalog
- `CL-bench` 从“预置评测集”改成 `benchmark -> version`
- 创建页结构改正

### Milestone 2

- 详情页可读
- 可以查看聚合指标和样本级 `reason`

### Milestone 3

- 建立 Benchmark 与 Benchmark Version 的管理界面
- benchmark 与 dataset 的边界稳定

### Milestone 4

- 再扩第二个 benchmark
- 例如 `mmlu_mcq`

只有到 Milestone 3 以后，再继续横向扩 benchmark 才是健康的。

## 9. 当前建议

下一步主线应该是：

1. 把 `Benchmark Catalog` 建起来
2. 把创建页从“评测集驱动”改成“Benchmark 驱动”
3. 给 `EvalJob` 增加 benchmark 字段
4. 恢复最小 detail 页

这四步完成后，系统组织形式才真正开始接近最初的 EvalScope 风格规划。
