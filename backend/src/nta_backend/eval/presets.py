from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class PresetEvalSuite:
    id: str
    name: str
    description: str
    capability_group: str
    capability_category: str
    eval_method: Literal["accuracy", "exact-match"]
    local_path: Path | None = None
    record_count: int | None = None

    @property
    def available(self) -> bool:
        return self.local_path is not None and self.local_path.exists()

    @property
    def file_name(self) -> str:
        if self.local_path is not None:
            return self.local_path.name
        return f"{self.name}.jsonl"


PRESET_EVAL_SUITES: tuple[PresetEvalSuite, ...] = (
    PresetEvalSuite(
        id="11111111-1111-5111-8111-111111111111",
        name="MMLU",
        description="综合学科多项选择题，覆盖 57 个任务，用于评估广泛世界知识和问题求解能力。",
        capability_group="综合能力",
        capability_category="综合能力",
        eval_method="accuracy",
        local_path=(
            REPO_ROOT / "docs" / "tmp" / "mmlu" / "mmlu-abstract_algebra-20-for-volc-ark.jsonl"
        ),
        record_count=20,
    ),
    PresetEvalSuite(
        id="22222222-2222-5222-8222-222222222222",
        name="BBH",
        description="BIG-Bench Hard，涵盖数学、常识推理和代码等高难任务。",
        capability_group="基础能力",
        capability_category="推理数学",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="33333333-3333-5333-8333-333333333333",
        name="GSM8K",
        description="小学数学多步推理题，常用于检验算术和分步求解能力。",
        capability_group="基础能力",
        capability_category="推理数学",
        eval_method="exact-match",
    ),
    PresetEvalSuite(
        id="44444444-4444-5444-8444-444444444444",
        name="WinoGrande",
        description="常识推理数据集，要求模型判断代词指代对象。",
        capability_group="基础能力",
        capability_category="推理数学",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="55555555-5555-5555-8555-555555555555",
        name="LSAT分析推理",
        description="法学院入学考试分析推理题，测试复杂条件关系理解与推理能力。",
        capability_group="基础能力",
        capability_category="推理数学",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="66666666-6666-5666-8666-666666666666",
        name="LSAT逻辑推理",
        description="法学院入学考试逻辑推理题，测试从前提到结论的推导能力。",
        capability_group="基础能力",
        capability_category="推理数学",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="77777777-7777-5777-8777-777777777777",
        name="高考语文",
        description="2010 到 2022 年高考语文试题，用于检验阅读与语言理解能力。",
        capability_group="基础能力",
        capability_category="语言创作",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="88888888-8888-5888-8888-888888888888",
        name="高考英语",
        description="2010 到 2022 年高考英语试题，用于检验语言理解与应用能力。",
        capability_group="基础能力",
        capability_category="语言创作",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="99999999-9999-5999-8999-999999999999",
        name="LSAT阅读理解",
        description="法学院入学考试阅读理解题，测试长文理解和证据组织能力。",
        capability_group="基础能力",
        capability_category="语言创作",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa",
        name="Hellaswag",
        description="常识自然语言理解挑战集，需要从多个结局中选出最合理的一项。",
        capability_group="基础能力",
        capability_category="语言创作",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb",
        name="BoolQ",
        description="基于维基百科段落的问答集，模型需要回答是/否。",
        capability_group="基础能力",
        capability_category="语言创作",
        eval_method="accuracy",
    ),
    PresetEvalSuite(
        id="cccccccc-cccc-5ccc-8ccc-cccccccccccc",
        name="Natural Questions",
        description="来源于真实 Google 查询的问题回答数据集。",
        capability_group="基础能力",
        capability_category="知识能力",
        eval_method="exact-match",
    ),
    PresetEvalSuite(
        id="dddddddd-dddd-5ddd-8ddd-dddddddddddd",
        name="TriviaQA",
        description="基于维基百科文本的事实问答数据集。",
        capability_group="基础能力",
        capability_category="知识能力",
        eval_method="exact-match",
    ),
    PresetEvalSuite(
        id="eeeeeeee-eeee-5eee-8eee-eeeeeeeeeeee",
        name="高考文理综",
        description="2010 到 2022 年高考文综和理综试题，覆盖多学科知识与综合应用。",
        capability_group="基础能力",
        capability_category="知识能力",
        eval_method="accuracy",
    ),
)


def list_preset_eval_suites() -> list[PresetEvalSuite]:
    return list(PRESET_EVAL_SUITES)


def get_preset_eval_suite(key: str | None) -> PresetEvalSuite | None:
    if not key:
        return None
    normalized = key.strip().lower()
    for suite in PRESET_EVAL_SUITES:
        if suite.id == key or suite.name.lower() == normalized:
            return suite
    return None
