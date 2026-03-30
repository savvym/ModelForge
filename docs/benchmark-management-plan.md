# Benchmark Management Plan

## 1. 目标

把当前平台里的 `Benchmark` 管理收敛成更接近 `EvalScope` 的形式：

- `Benchmark Type` 由代码定义
- 系统里只做查看，不在线创建新的 benchmark 类型
- 系统里可管理的是各 benchmark type 下的 `Benchmark Version`
- 每个 version 在入库时完成格式校验和样本数统计

## 2. 对齐 EvalScope

在 `EvalScope` 里，一个 benchmark 本质上包含两部分：

- 代码实现
  - benchmark 目录
  - adapter / `to_sample`
  - evaluator / metric 逻辑
- 元信息
  - `_meta`
  - 数据格式约束
  - prompt 相关配置

映射到当前系统后，建议拆成两层：

### 2.1 Benchmark Type

这是代码里的 benchmark 类型，等价于“已经接入系统的一类可执行 benchmark”。

它由后端代码定义，至少包含：

- `name`
- `display_name`
- `description`
- `default_eval_method`
- `requires_judge_model`
- `supports_custom_dataset`
- `sample_schema_json`
- `prompt_schema_json`
- `prompt_config_json`

它还负责：

- adapter / `to_sample`
- benchmark 执行逻辑
- metric 装配
- 原始数据如何转成统一 `Sample`

### 2.2 Benchmark Version

这是某个 benchmark type 的一个具体数据集版本。

它在系统里可被新增、编辑、启停，并至少包含：

- `benchmark_name`
- `version_id`
- `display_name`
- `description`
- `dataset_source_uri`
- `sample_count`
- `enabled`

## 3. 当前产品语义

当前系统里：

- `Benchmark` 页面是“Benchmark 查看”
- 展示的是代码里已经注册的 benchmark type
- 用户不能在 UI 里在线创建一个新的 benchmark type

如果要新增一个 benchmark type，正确流程是：

1. 在后端代码里新增 benchmark runtime
2. 在代码里补上它的 schema / prompt contract / 元信息
3. 部署后，前端自动能看到这个 benchmark type
4. 再在系统里为它上传或登记不同的 version

这更适合后续把 `EvalScope benchmarks/` 下的 benchmark 逐步移植过来。

## 4. 为什么这样更合适

这样做的好处是：

- benchmark 的执行逻辑仍然是代码资产，边界清晰
- 不需要先做在线 adapter 编辑器
- 不会让 UI 承担“发明新 benchmark 逻辑”的职责
- 可以快速把 `EvalScope` 里的 benchmark 类型按代码方式迁进来
- 产品层只需要专注在 version 数据管理和评测入口

## 5. Benchmark Type 暴露什么

每个代码 benchmark type 至少要暴露两类 contract：

### 5.1 Sample Contract

用于约束原始数据集每一行的格式。

对应：

- `sample_schema_json`

注意：

这不是统一 `Sample` 的 schema，
而是“这个 benchmark 接受的原始输入格式”。

真正统一成 `Sample`，发生在代码里的 adapter `to_sample`。

### 5.2 Prompt Contract

用于约束该 benchmark 允许的 prompt 相关配置。

对应：

- `prompt_schema_json`
- `prompt_config_json`

作用：

- 给页面展示 benchmark 的 prompt 约束
- 给执行层提供默认 prompt 配置
- 避免向不支持的 benchmark 注入任意 prompt 参数

## 6. Benchmark Version 的入库流程

`Benchmark Version` 创建或更新时，后端固定走这条流程：

1. 根据 `benchmark_name` 找到代码定义的 benchmark type
2. 读取这个 benchmark type 的 `sample_schema_json`
3. 读取 `dataset_source_uri`
4. 逐行校验 JSONL
5. 统计 `sample_count`
6. 记录规范化后的数据源信息
7. 落库 version

当前不在线管理 `to_sample` 逻辑，这一步仍然由 benchmark runtime 自己负责。

## 7. 当前实现原则

### 7.1 Benchmark Type

- 来源：代码注册表
- 页面能力：只读查看
- 不提供在线新增/编辑入口

### 7.2 Benchmark Version

- 来源：数据库
- 页面能力：新增、编辑、启停
- 创建时按 benchmark type 的 schema 自动校验和统计

## 8. 这条线如何支持移植 EvalScope

后续移植 `EvalScope` 的 benchmark 时，流程会非常直接：

1. 把某个 benchmark 的执行逻辑移植成代码 benchmark type
2. 给它补对应的 sample schema 和 prompt contract
3. 部署后，系统自动能看到这个 benchmark type
4. 在平台里登记它的一个或多个 version
5. 创建评测任务时选择：
   - eval model
   - judge model
   - benchmark
   - benchmark version

## 9. 下一步建议

### Step 1

继续完善代码 benchmark type 的元信息导出，让 benchmark 页面完全基于代码注册表。

### Step 2

把 version 数据源进一步收口到对象存储 URI，逐步去掉本地路径兼容。

### Step 3

补充更多 `EvalScope` benchmark type 的代码移植。

### Step 4

再继续完善评测详情页、artifacts 读取层和结果展示。

## 10. 结论

当前更合理的组织方式是：

- Benchmark Type = 代码定义的 benchmark 类型，系统只查看
- Benchmark Version = 系统里管理的数据集版本
- adapter `to_sample` 仍然属于代码 benchmark type
- version 入库时负责格式校验和样本统计

这条线最适合当前阶段，也最利于后续批量移植 `EvalScope` 的 benchmark。
