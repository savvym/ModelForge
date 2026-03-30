# Eval Template Bailian Alignment Plan

## 1. 目标

把当前 NTA 的“创建评测模板”能力，从“选择一个预设 prompt”升级成更接近阿里百炼“创建评测维度”的结构：

- 先选 `评测类型`
- 再进入该类型自己的配置表单
- 只有部分类型再细分为二级 `模板/预设`
- 数据结构能表达：
  - 自动评测 / 规则评测 / 人工评测
  - 布尔型 / 数值型 / 分类型
  - 规则算子 / 相似度指标 / 标签分组 / 数值范围 / 阈值

这条线既能对齐百炼，也能保留当前 NTA 的“评测模板可复用”设计。

## 2. 百炼调研结论

通过页面实测，百炼当前的“创建评测维度”有 5 个顶层类型：

1. `大模型评估-分类型`
2. `大模型评估-数值型`
3. `规则评估-字符串匹配`
4. `规则评估-文本相似度`
5. `人工评估-分类型`

其中只有前两类存在二级模板：

### 2.1 大模型评估-分类型

- 公共字段：
  - `维度名称`
  - `描述`
  - `类型`
- 专属字段：
  - `裁判模型`
  - `评分器模板`
  - `Prompt`
  - `标签`
- 二级模板：
  - `标准匹配`
  - `情感分析`
  - `自定义评分器`

观察到的创建逻辑：

- 模板切换不仅切换默认 Prompt，还会联动默认标签。
- `标准匹配` 默认标签为 `Pass / Fail`。
- `情感分析` 默认标签为 `积极 / 中性 / 消极`。
- `自定义评分器` 会保留空标签，让用户自行定义。

### 2.2 大模型评估-数值型

- 公共字段：
  - `维度名称`
  - `描述`
  - `类型`
- 专属字段：
  - `裁判模型`
  - `评分器模板`
  - `Prompt`
  - `评分范围`
  - `通过阈值`
- 二级模板：
  - `综合评测`
  - `语义相似度`
  - `自定义评分器`

观察到的创建逻辑：

- 模板切换主要联动默认 Prompt。
- 页面会保留数值评分配置，例如 `min/max/pass_threshold`。

### 2.3 规则评估-字符串匹配

- 没有裁判模型
- 没有 Prompt
- 由两个文本输入区和一个比较算子组成

实测算子包括：

- `相等`
- `不相等`
- `包含`
- `开头包含`
- `结尾包含`

### 2.4 规则评估-文本相似度

- 没有裁判模型
- 没有 Prompt
- 由两个文本输入区、一个相似度指标下拉和一个 `通过阈值` 组成

实测指标包括：

- `FUZZY_MATCH`
- `BLEU_4`
- `COSINE`
- `ROUGE_1`
- `ROUGE_2`
- `ROUGE_L`
- `ACCURACY`

### 2.5 人工评估-分类型

- 没有裁判模型
- 没有 Prompt
- 核心是标签分组
- 默认分成：
  - `Pass` 组
  - `Fail` 组

每组可以动态添加多个标签。

## 3. 当前 NTA 的实现现状

当前实现主要在：

- 创建页：[page.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/app/(console)/model/eval-templates/create/page.tsx)
- 创建表单：[eval-template-create-form.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/features/eval/components/eval-template-create-form.tsx)
- 后端 schema：[eval_template.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/schemas/eval_template.py)
- 后端 service：[eval_template_service.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/services/eval_template_service.py)

当前模型可以概括为：

- 先选一个 `Preset`
- 再编辑：
  - `name`
  - `description`
  - `prompt`
  - `output_type`
  - `output_config`
  - `model`

当前的 5 张卡片：

1. `Rubric 标准核查`
2. `质量评分 (1-5)`
3. `相关性判断`
4. `正确性分类`
5. `自定义模板`

这套设计的问题不是不能用，而是层级混了：

- `Rubric 标准核查` 和 `质量评分` 更像某类评测下的预设模板
- `相关性判断` 和 `正确性分类` 本质上也是 Prompt + 输出配置预设
- `自定义模板` 则混合了多种输出模式

也就是说，当前 NTA 直接把“顶层类型”和“类型内模板”放在了同一层。

## 4. 推荐的目标信息架构

建议把当前创建页重构成两层：

### Step 1：选择评测类型

首页不再展示当前 5 个 prompt preset，而是展示 5 个顶层类型卡片：

1. `LLM 自动评测 - 分类型`
2. `LLM 自动评测 - 数值型`
3. `规则评测 - 字符串匹配`
4. `规则评测 - 文本相似度`
5. `人工评测 - 分类型`

### Step 2：配置该类型

进入对应类型的配置页后，再根据类型决定显示哪些表单模块。

### Step 3：仅在需要时显示“模板预设”

只有 LLM 自动评测类需要展示二级模板：

- 分类型：
  - `标准核查`
  - `相关性判断`
  - `情感分析`
  - `正确性分类`
  - `自定义`
- 数值型：
  - `质量评分 (1-5)`
  - `语义相似度`
  - `自定义`

这样能把你们当前已有卡片自然吸收到新结构里。

## 5. 当前卡片到新结构的映射

### 5.1 建议映射关系

- `Rubric 标准核查`
  - 迁移为：`LLM 自动评测 - 分类型 / 标准核查`
- `质量评分 (1-5)`
  - 迁移为：`LLM 自动评测 - 数值型 / 质量评分`
- `相关性判断`
  - 迁移为：`LLM 自动评测 - 分类型 / 相关性判断`
- `正确性分类`
  - 迁移为：`LLM 自动评测 - 分类型 / 正确性分类`
- `自定义模板`
  - 拆成三条入口：
    - `LLM 自动评测 - 分类型 / 自定义`
    - `LLM 自动评测 - 数值型 / 自定义`
    - `人工评测 - 分类型`

### 5.2 为什么不要继续保留现在这 5 张卡片

如果继续保留，后面会遇到三个问题：

- 无法自然扩展规则评测
- 无法清晰区分“输出模式”和“评分方法”
- 模板详情页也很难表达模板真实语义

## 6. 推荐的数据模型

当前后端只有：

- `output_type`
- `output_config`

这足够兼容旧数据，但不足以清晰表达新结构。

建议保持数据库表不大改，优先扩展 `output_config`，并新增更明确的高层字段。

### 6.1 推荐新增字段

在 `EvalTemplateCreate` / `EvalTemplateSummary` / `EvalTemplate` 中新增：

- `template_type: str`
  - 值建议：
    - `llm_categorical`
    - `llm_numeric`
    - `rule_string_match`
    - `rule_text_similarity`
    - `manual_categorical`
- `preset_id: str | None`
  - 例如：
    - `rubric-check`
    - `relevance-check`
    - `quality-score-1-5`
    - `semantic-similarity`
    - `sentiment-analysis`
    - `correctness-category`
    - `custom`

`output_type` 仍保留，用于表达最终输出形态：

- `boolean`
- `numeric`
- `categorical`

### 6.2 推荐的 output_config 结构

```json
{
  "mode": "llm" | "rule" | "manual",
  "label_groups": [
    {
      "key": "pass",
      "label": "Pass",
      "score_policy": "pass",
      "labels": ["Pass", "Relevant", "Correct"]
    },
    {
      "key": "fail",
      "label": "Fail",
      "score_policy": "fail",
      "labels": ["Fail", "Irrelevant", "Wrong"]
    }
  ],
  "numeric_range": {
    "min": 1,
    "max": 5,
    "pass_threshold": 3
  },
  "rule_config": {
    "operator": "equals",
    "metric": "ROUGE_L"
  },
  "text_sources": {
    "left_template": "{{output}}",
    "right_template": "{{target}}"
  }
}
```

### 6.3 各类型的建议表达

#### `llm_categorical`

- `output_type = "categorical"`
- `output_config.mode = "llm"`
- `output_config.label_groups` 必填
- `prompt` 必填
- `model` 可选但推荐

#### `llm_numeric`

- `output_type = "numeric"`
- `output_config.mode = "llm"`
- `output_config.numeric_range` 必填
- `prompt` 必填
- `model` 可选但推荐

#### `rule_string_match`

- `output_type = "boolean"` 或 `categorical`
- `output_config.mode = "rule"`
- `output_config.rule_config.operator` 必填
- `output_config.text_sources.left_template/right_template` 必填
- `prompt` 可为空

建议第一版直接固定为 `boolean`，语义最清晰。

#### `rule_text_similarity`

- `output_type = "numeric"` 或 `boolean`
- `output_config.mode = "rule"`
- `output_config.rule_config.metric` 必填
- `output_config.numeric_range` 可选
- `output_config.pass_threshold` 必填

建议第一版内部计算原始相似度，再根据阈值输出 pass/fail，同时保留原始数值用于展示。

#### `manual_categorical`

- `output_type = "categorical"`
- `output_config.mode = "manual"`
- `output_config.label_groups` 必填
- `prompt` 可为空

## 7. 前端页面改造建议

### 7.1 创建页结构

建议把当前 [eval-template-create-form.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/features/eval/components/eval-template-create-form.tsx) 拆成：

- `eval-template-type-picker.tsx`
- `eval-template-editor.tsx`
- `eval-template-sections/basic-info.tsx`
- `eval-template-sections/llm-config.tsx`
- `eval-template-sections/rule-string-match.tsx`
- `eval-template-sections/rule-text-similarity.tsx`
- `eval-template-sections/manual-label-groups.tsx`
- `eval-template-sections/preset-selector.tsx`

### 7.2 页面交互流

推荐交互：

1. 进入创建页
2. 先选 `评测类型`
3. 若该类型有预设，再选 `模板预设`
4. 表单根据类型动态展开
5. 提交时统一生成：
   - `template_type`
   - `preset_id`
   - `prompt`
   - `output_type`
   - `output_config`

### 7.3 不同类型应展示的表单模块

#### `LLM 自动评测 - 分类型`

- 基础信息
- Judge 模型
- 预设选择
- Prompt 编辑器
- 标签分组编辑器

#### `LLM 自动评测 - 数值型`

- 基础信息
- Judge 模型
- 预设选择
- Prompt 编辑器
- 评分范围
- 通过阈值

#### `规则评测 - 字符串匹配`

- 基础信息
- 左文本模板
- 比较算子
- 右文本模板

#### `规则评测 - 文本相似度`

- 基础信息
- 左文本模板
- 相似度指标
- 右文本模板
- 阈值

#### `人工评测 - 分类型`

- 基础信息
- 标签分组编辑器

### 7.4 复用现有组件的建议

当前页里已有可复用能力：

- `name / description / model` 基础输入
- `Prompt` 变量提取逻辑
- `output_config` 构造逻辑

建议保留：

- Prompt 中 `{{variable}}` 自动提取
- 最终提交时仍然走 `createEvalTemplate`

建议重写：

- 顶部 preset 卡片
- 输出类型选择区
- category 逗号输入

其中“分类列表（逗号分隔）”需要升级成真正的标签分组编辑器。

## 8. 详情页和列表页也要同步改

当前详情页和列表页只理解：

- `output_type`
- `output_config`

建议同步补下面几个展示维度：

### 列表页增加

- `模板类型`
- `预设`
- `Judge 模型`

### 详情页增加

- `评测类型`
- `预设`
- `标签分组`
- `规则算子 / 相似度指标`
- `评分范围 / 阈值`

对应文件：

- 列表页：[eval-template-list-table.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/features/eval/components/eval-template-list-table.tsx)
- 详情页：[page.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/app/(console)/model/eval-templates/[name]/page.tsx)

## 9. 后端改造建议

### 9.1 Phase 1：兼容式扩展

第一阶段不要推翻数据库表，做兼容式扩展：

- `eval_templates` 表新增：
  - `template_type`
  - `preset_id`
- 保留：
  - `prompt`
  - `output_type`
  - `output_config`
  - `model`
  - `description`

这样旧模板仍可继续读取。

### 9.2 Service 层增加校验

在 [eval_template_service.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/services/eval_template_service.py) 增加按 `template_type` 的 schema 校验：

- `llm_categorical`
  - 必须有 `prompt`
  - 必须有 `label_groups`
- `llm_numeric`
  - 必须有 `prompt`
  - 必须有 `numeric_range`
- `rule_string_match`
  - 必须有 `left_template`
  - 必须有 `right_template`
  - 必须有 `operator`
- `rule_text_similarity`
  - 必须有 `left_template`
  - 必须有 `right_template`
  - 必须有 `metric`
  - 必须有 `pass_threshold`
- `manual_categorical`
  - 必须有 `label_groups`

### 9.3 Prompt 变量提取逻辑要扩展

当前变量提取只扫描 `prompt`。

如果支持规则型模板，建议把这些字段也纳入变量提取：

- `output_config.text_sources.left_template`
- `output_config.text_sources.right_template`

否则规则型模板会显示“没有变量”，不利于用户理解。

## 10. 推荐的实施顺序

### Phase A：页面重构，不改执行引擎

先完成：

- 创建页改成“类型优先”
- 后端保存 `template_type / preset_id`
- 新模板详情和列表页展示新字段

这一阶段可以先把规则型和人工型模板“定义出来”，即使执行链路还没完全接通。

### Phase B：补规则型执行链路

再补：

- 字符串匹配执行器
- 文本相似度执行器
- 评测结果的阈值判定和中间值展示

### Phase C：补人工评测任务链路

最后补：

- 人工标注界面
- 标签选择器
- 人工结果写回和聚合

## 11. MVP 建议

如果这轮只做一版能上线的 MVP，我建议范围收成：

1. 创建页先支持 4 类：
   - `LLM 自动评测 - 分类型`
   - `LLM 自动评测 - 数值型`
   - `规则评测 - 字符串匹配`
   - `规则评测 - 文本相似度`
2. `人工评测 - 分类型` 先只支持模板定义，不接任务执行
3. LLM 分类型内置预设：
   - `标准核查`
   - `相关性判断`
   - `正确性分类`
   - `情感分析`
   - `自定义`
4. LLM 数值型内置预设：
   - `质量评分 (1-5)`
   - `语义相似度`
   - `自定义`

这样一版就已经能覆盖百炼的主要能力结构。

## 12. 对当前代码的直接改造建议

### 第一刀

先改 [eval-template-create-form.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/features/eval/components/eval-template-create-form.tsx)：

- 去掉当前顶层 `PRESETS`
- 改为：
  - `TEMPLATE_TYPES`
  - `LLM_CATEGORICAL_PRESETS`
  - `LLM_NUMERIC_PRESETS`

### 第二刀

扩 `frontend/types/api.ts` 和后端 schema：

- 给 `EvalTemplateSummary`
- `EvalTemplateCreateInput`
- `EvalTemplateUpdateInput`
- `EvalTemplateCreate`
- `EvalTemplateUpdate`
- `EvalTemplateSummary`

新增：

- `template_type`
- `preset_id`

### 第三刀

改详情和列表展示：

- [eval-template-list-table.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/features/eval/components/eval-template-list-table.tsx)
- [page.tsx](/Users/zhanghaodong/Desktop/nta-platform/frontend/app/(console)/model/eval-templates/[name]/page.tsx)

### 第四刀

后端补校验和变量提取：

- [eval_template_service.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/services/eval_template_service.py)
- [template_utils.py](/Users/zhanghaodong/Desktop/nta-platform/backend/src/nta_backend/eval_core/template_utils.py)

## 13. 结论

这次对标百炼，最重要的不是“照抄 5 张卡片”，而是把你们当前的评测模板体系重新分层：

- 第一层：`评测类型`
- 第二层：`类型内预设`
- 第三层：`具体模板配置`

从现有代码出发，最稳的方案不是推翻 `EvalTemplate`，而是：

- 保留 `prompt + output_type + output_config`
- 新增 `template_type + preset_id`
- 把 UI 改成 `type-first`
- 把规则评测和人工评测纳入统一模板系统

这样能最大化复用现在的模板能力，同时把后续演进空间打开。
