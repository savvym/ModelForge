# 模型评测真实 Workflow 设计草案

## 1. 目标

把当前演示型模型评测链路升级为可实际运行的评测系统，满足以下目标：

- 支持真实推理，不再使用 mock 输出和 mock 指标。
- 支持统一的评测数据内部标准，同时兼容多种外部导入格式。
- 支持 `accuracy`、`rule-based`、`judge-model` 三类 scorer。
- 支持结构化 rubric 打分，而不是仅保存一段自由文本。
- 支持样本级结果存储、任务级指标聚合和可追溯报告。
- 保持 workflow 可重试、可恢复、可观测。

非目标：

- 本文不覆盖前端最终 UI 细节。
- 本文不覆盖所有 benchmark 适配器的具体实现。
- 本文不直接提交运行时代码，仅给出落地方案和接口草案。

## 2. 当前缺口

当前仓库的主要问题：

- 数据集导入没有执行评测 schema 校验，只是存文件和计行数。
- `eval_job_workflow` 虽然有 validate / inference / score / archive 四个阶段，但 inference 和 score 都是 mock。
- `judge-model` 只有字段，没有真实评分执行器。
- `rubric` 只是字符串，不能稳定支持维度、权重、范围和版本化。
- 没有样本级结果表，无法支持失败样本、复核、评分解释。

## 3. 数据标准

### 3.1 设计原则

评测数据格式分成两层：

- 外部导入格式：允许 benchmark 原始格式、平台上传格式、Excel 转换格式。
- 内部运行格式：统一归一化成 canonical JSONL。

不要把某一个 benchmark 的原始字段结构当成平台标准。平台标准只服务于 workflow 运行。

### 3.2 Canonical Eval Sample

建议内部统一样本格式如下：

```json
{
  "sample_id": "mmlu-abstract-algebra-0001",
  "task_type": "single-turn",
  "input": {
    "system": "You are taking an MMLU-style multiple-choice exam.",
    "messages": [
      {
        "role": "user",
        "content": "Question text"
      }
    ],
    "prompt": "optional flattened prompt"
  },
  "reference": {
    "answer": "B",
    "answers": ["B"],
    "label": null,
    "reference_text": null
  },
  "scoring": {
    "method": "judge-model",
    "weight": 1.0,
    "rubric_id": "rb_123",
    "rubric_overrides": null
  },
  "metadata": {
    "dataset": "mmlu",
    "subject": "abstract_algebra",
    "difficulty": null,
    "tags": ["multiple-choice"]
  }
}
```

### 3.3 字段约束

- `sample_id`：每个数据集版本内唯一，要求稳定。
- `task_type`：初期限制为 `single-turn` 或 `multi-turn`。
- `input.messages`：至少一条消息。
- `reference`：`judge-model` 可选，`accuracy` 和大多数 `rule-based` 必填。
- `scoring.method`：允许样本级覆盖，但默认继承任务级配置。
- `metadata`：只承载补充信息，不参与主流程控制。

### 3.4 允许的外部导入格式

初期建议支持以下三类：

1. 平台原生格式

```json
{"sample_id":"1","input":{"messages":[{"role":"user","content":"..."}]},"reference":{"answer":"..."}}
```

2. 简化 QA 格式

```json
{"input":"...","answer":"..."}
```

3. MMLU 风格格式

```json
{"system":"...","prompt":"...","answer":"B"}
```

导入阶段统一转换为 canonical JSONL。

## 4. Pydantic Schema 草案

建议新增模块：

- `backend/src/nta_backend/schemas/eval_dataset.py`
- `backend/src/nta_backend/schemas/eval_rubric.py`

### 4.1 评测样本 Schema

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EvalMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)


class EvalSampleInput(BaseModel):
    system: str | None = None
    messages: list[EvalMessage] = Field(min_length=1)
    prompt: str | None = None


class EvalSampleReference(BaseModel):
    answer: str | None = None
    answers: list[str] | None = None
    label: str | None = None
    reference_text: str | None = None

    @model_validator(mode="after")
    def ensure_any_reference(self):
        if self.answer or self.answers or self.label or self.reference_text:
            return self
        return self


class EvalSampleScoring(BaseModel):
    method: Literal["accuracy", "rule-based", "judge-model"]
    weight: float = Field(default=1.0, gt=0)
    rubric_id: str | None = None
    rubric_overrides: dict | None = None


class EvalSample(BaseModel):
    sample_id: str = Field(min_length=1, max_length=255)
    task_type: Literal["single-turn", "multi-turn"] = "single-turn"
    input: EvalSampleInput
    reference: EvalSampleReference = Field(default_factory=EvalSampleReference)
    scoring: EvalSampleScoring
    metadata: dict = Field(default_factory=dict)
```

### 4.2 Rubric Schema

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RubricDimension(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    description: str | None = None
    weight: float = Field(gt=0)
    min_score: float = 1.0
    max_score: float = 5.0
    required: bool = False


class RubricPassRule(BaseModel):
    min_weighted_score: float | None = None
    required_dimensions: list[str] = Field(default_factory=list)


class EvalRubricDefinition(BaseModel):
    version: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    task_type: Literal["single-turn", "multi-turn"] = "single-turn"
    dimensions: list[RubricDimension] = Field(min_length=1)
    pass_rule: RubricPassRule | None = None
    judge_instructions: str | None = None
```

### 4.3 Judge 输出 Schema

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class JudgeDimensionResult(BaseModel):
    score: float
    passed: bool | None = None
    reason: str | None = None


class JudgeModelResult(BaseModel):
    overall_score: float
    pass_: bool = Field(alias="pass")
    dimension_scores: dict[str, JudgeDimensionResult]
    reason: str
```

## 5. 数据导入与归一化

### 5.1 新增导入阶段

建议把 `dataset_import_workflow` 扩成真实的五步：

1. 校验对象存在
2. 识别文件格式
3. 解析原始样本
4. 转换为 canonical JSONL
5. 写入 normalized artifact 和校验结果

### 5.2 新增 Artifact

对评测数据集版本新增归一化产物：

- `normalized/eval-samples.jsonl`
- `normalized/schema-report.json`

其中 `schema-report.json` 至少包含：

```json
{
  "format": "mmlu-jsonl",
  "record_count": 20,
  "normalized": true,
  "warnings": [],
  "errors": []
}
```

### 5.3 导入校验规则

最小校验建议：

- JSONL 每行必须是合法 JSON 对象
- 每条样本必须能转换成 canonical sample
- `sample_id` 必须唯一
- `judge-model` 缺少 rubric 时报警或禁止提交
- `accuracy` 缺少 reference 时直接失败

## 6. Workflow 设计

### 6.1 目标编排

建议把 `eval_job_workflow` 调整为：

1. `validate_eval_request`
2. `prepare_eval_inputs`
3. `run_eval_inference`
4. `wait_eval_inference_completion`
5. `score_eval_outputs`
6. `aggregate_eval_metrics`
7. `archive_eval_artifacts`

### 6.2 Activity / Subworkflow 划分

建议结构：

- `prepare_eval_inputs`
  - 读取数据集归一化产物
  - 结合任务配置生成运行时输入文件
- `run_eval_inference`
  - 根据 `inference_mode` 分流
  - `batch` 走批量推理子 workflow
  - `endpoint` 走在线推理批处理 activity
- `score_eval_outputs`
  - 选择 scorer
  - fan-out 样本级评分
- `aggregate_eval_metrics`
  - 聚合任务级 metrics
  - 写 DB 和报告

### 6.3 Judge Scoring 是否属于评分 Workflow

属于评分阶段，建议放在 `score_eval_outputs` 里，后续量大时可拆 `judge_scoring_subworkflow`。

推荐拆分阈值：

- 样本数 > 500
- 评分请求需要并发控制
- 需要对 judge 调用做重试和断点恢复

## 7. 模块拆分建议

建议新增目录：

```text
backend/src/nta_backend/eval/
  canonical.py
  normalizers/
    base.py
    simple_qa.py
    mmlu.py
  inference/
    base.py
    batch.py
    endpoint.py
  scorers/
    base.py
    accuracy.py
    rule_based.py
    judge_model.py
  rubrics/
    service.py
    templates.py
  reports/
    metrics.py
    samples.py
```

### 7.1 EvalScorer 接口

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class EvalScorer(ABC):
    method: str

    @abstractmethod
    async def score_sample(
        self,
        *,
        sample: dict,
        prediction: dict,
        rubric: dict | None,
        job_context: dict,
    ) -> dict:
        raise NotImplementedError

    async def score_batch(
        self,
        *,
        samples: list[dict],
        predictions: list[dict],
        rubric: dict | None,
        job_context: dict,
    ) -> list[dict]:
        results = []
        for sample, prediction in zip(samples, predictions, strict=True):
            results.append(
                await self.score_sample(
                    sample=sample,
                    prediction=prediction,
                    rubric=rubric,
                    job_context=job_context,
                )
            )
        return results
```

### 7.2 各 Scorer 责任

- `AccuracyScorer`
  - 支持精确匹配、大小写归一、选项标准化
- `RuleBasedScorer`
  - 支持关键词包含、正则、简单规则 DSL
- `JudgeModelScorer`
  - 构造 judge prompt
  - 调裁判模型
  - 解析结构化响应
  - 落原始响应和解析结果

## 8. Rubric 原生支持设计

### 8.1 为什么不能只存字符串

如果 rubric 只是文本，会导致：

- 无法做维度聚合
- 无法做权重加总
- 无法做版本对比
- 无法稳定解析 judge 输出

因此 `rubric` 必须拆成：

- `rubric_id`
- `rubric_snapshot_json`
- `rubric_rendered_prompt`

其中：

- `rubric_id` 用于引用可复用模板
- `rubric_snapshot_json` 用于任务创建时固化
- `rubric_rendered_prompt` 用于实际 judge 调用时记录

### 8.2 任务创建时的行为

提交评测任务时：

1. 读取选中的 rubric 模板
2. 应用用户临时修改
3. 生成 `rubric_snapshot_json`
4. 挂到 `eval_jobs`

这样历史任务不会被后续 rubric 编辑影响。

## 9. Judge Prompt 模板

### 9.1 Prompt 设计原则

- 要求裁判模型只返回 JSON
- 给清晰评分维度、范围和含义
- 给 reference 时显式说明可参考，不给时说明仅按 rubric 打分
- 避免让 judge 自由发挥成散文

### 9.2 系统提示词模板

```text
You are an evaluation judge for LLM outputs.
Score the candidate answer strictly according to the provided rubric.
Return only valid JSON. Do not include markdown, code fences, or extra commentary.
```

### 9.3 用户提示词模板

```text
Task type: {{ task_type }}

Rubric:
{{ rendered_rubric }}

Input:
{{ normalized_input }}

Reference answer:
{{ reference_answer_or_null }}

Candidate answer:
{{ candidate_answer }}

Return a JSON object with this shape:
{
  "overall_score": number,
  "pass": boolean,
  "dimension_scores": {
    "<dimension_key>": {
      "score": number,
      "passed": boolean | null,
      "reason": string
    }
  },
  "reason": string
}

Rules:
- overall_score must be within the rubric score range
- every rubric dimension must appear exactly once
- do not output any text outside JSON
```

## 10. Judge 响应解析与失败处理

### 10.1 解析策略

建议分三层：

1. 直接 JSON 解析
2. 去除首尾噪声后二次 JSON 解析
3. 失败则重试

### 10.2 重试建议

- JSON 解析失败：最多重试 2 次
- 缺维度 / 分值越界：最多重试 1 次
- provider 超时：按指数退避重试 3 次

### 10.3 落盘内容

每个样本建议保存：

- judge request body
- judge raw response
- parsed result
- parse error
- retry count

## 11. 数据库增量方案

### 11.1 `eval_jobs` 新增字段

建议新增：

- `judge_model_id UUID NULL`
- `rubric_id UUID NULL`
- `rubric_snapshot_json JSONB NULL`
- `normalized_source_object_uri TEXT NULL`
- `error_message TEXT NULL`
- `completed_samples BIGINT NULL`
- `total_samples BIGINT NULL`

### 11.2 新表 `eval_rubrics`

字段建议：

- `id`
- `project_id`
- `name`
- `version`
- `description`
- `task_type`
- `definition_json`
- `status`
- `created_by`
- `created_at`
- `updated_at`

### 11.3 新表 `eval_job_sample_results`

字段建议：

- `id`
- `eval_job_id`
- `sample_id`
- `sample_index`
- `status`
- `prediction_text`
- `reference_json`
- `score_json`
- `overall_score`
- `passed`
- `judge_reason`
- `judge_request_id`
- `judge_latency_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `created_at`
- `updated_at`

### 11.4 新表 `eval_job_artifacts`

如果不想在 `eval_jobs` 堆太多 URI，可单独建表：

- `id`
- `eval_job_id`
- `artifact_type`
- `object_uri`
- `content_type`
- `created_at`

可选 `artifact_type`：

- `normalized-input`
- `inference-input`
- `inference-output`
- `judge-request`
- `judge-response`
- `scored-samples`
- `report`

## 12. Alembic 迁移草案

```python
def upgrade() -> None:
    op.add_column("eval_jobs", sa.Column("judge_model_id", sa.UUID(), nullable=True))
    op.add_column("eval_jobs", sa.Column("rubric_id", sa.UUID(), nullable=True))
    op.add_column("eval_jobs", sa.Column("rubric_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("eval_jobs", sa.Column("normalized_source_object_uri", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("eval_jobs", sa.Column("completed_samples", sa.BigInteger(), nullable=True))
    op.add_column("eval_jobs", sa.Column("total_samples", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_eval_jobs_judge_model_id_models"),
        "eval_jobs",
        "models",
        ["judge_model_id"],
        ["id"],
    )

    op.create_table(
        "eval_rubrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("definition_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_rubrics_project_id"), "eval_rubrics", ["project_id"], unique=False)

    op.create_table(
        "eval_job_sample_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("eval_job_id", sa.UUID(), nullable=False),
        sa.Column("sample_id", sa.String(length=255), nullable=False),
        sa.Column("sample_index", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prediction_text", sa.Text(), nullable=True),
        sa.Column("reference_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("judge_reason", sa.Text(), nullable=True),
        sa.Column("judge_request_id", sa.String(length=128), nullable=True),
        sa.Column("judge_latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("total_tokens", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["eval_job_id"], ["eval_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("eval_job_id", "sample_id", name="uq_eval_job_sample_results_job_sample"),
    )
    op.create_index(
        op.f("ix_eval_job_sample_results_eval_job_id"),
        "eval_job_sample_results",
        ["eval_job_id"],
        unique=False,
    )
```

## 13. 报告与可观测性

任务级报告建议至少输出：

- 完成样本数 / 失败样本数
- 平均分 / 中位数 / P90
- 各 rubric 维度均值
- pass rate
- token usage
- latency 分布

样本级报告建议至少支持：

- 失败样本列表
- 低分样本列表
- judge 解释
- 原始 prediction / reference 对照

## 14. 分阶段实施建议

### Phase 1

- 引入 canonical sample schema
- 数据集导入做强校验和归一化
- 先打通 `accuracy`

### Phase 2

- 打通真实 inference
- 把批量推理 workflow 接到 eval workflow
- 补 `rule-based`

### Phase 3

- 上 `eval_rubrics`
- 上 `JudgeModelScorer`
- 上样本级结果存储

### Phase 4

- 报告页支持样本分析
- 加人工复核和回归比较

## 15. 推荐的第一批实现任务

建议按以下顺序拆开发任务：

1. 新增 canonical schema 和 normalizer 模块
2. 扩充 dataset import workflow，产出 normalized JSONL
3. 新增 `judge_model_id`、`rubric_snapshot_json` 和样本级结果表
4. 抽 `EvalScorer` 接口，先实现 `AccuracyScorer`
5. 接真实 inference runner
6. 实现 `JudgeModelScorer`
7. 接任务级聚合和报告输出

## 16. 需要同步调整的前端字段

前端创建任务表单应补齐这些字段提交：

- `judge_model_id`
- `rubric_id`
- `rubric_snapshot_json` 或结构化 `rubric_definition`

当前只传 `judge_model_name` 不足以驱动真实评分调用。

