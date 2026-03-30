from __future__ import annotations

from typing import Any

CL_BENCH_SAMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["messages", "rubrics"],
    "properties": {
        "id": {"type": "string"},
        "messages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["role", "content"],
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["system", "user", "assistant", "tool"],
                    },
                    "content": {"type": "string"},
                },
            },
        },
        "rubrics": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "metadata": {"type": "object"},
        "group_id": {"type": "string"},
    },
}

CL_BENCH_PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "judge_prompt_template": {"type": "string"},
    },
}

CL_BENCH_PROMPT_CONFIG: dict[str, Any] = {}

GROUNDED_RUBRIC_QA_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["rubrics"],
    "properties": {
        "id": {"type": "string"},
        "context": {"type": "string"},
        "question": {"type": "string"},
        "messages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["role", "content"],
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["system", "user", "assistant", "tool"],
                    },
                    "content": {"type": "string"},
                },
            },
        },
        "rubrics": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "metadata": {"type": "object"},
    },
}

GROUNDED_RUBRIC_QA_PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "system_prompt": {"type": "string"},
        "user_prompt_template": {"type": "string"},
        "judge_prompt_template": {"type": "string"},
    },
}

GROUNDED_RUBRIC_QA_PROMPT_CONFIG: dict[str, Any] = {
    "system_prompt": (
        "你是一位领域专家。请结合题目中给出的背景信息作答，"
        "回答应准确、完整，并优先使用该领域的专业表述。"
    ),
    "user_prompt_template": (
        "以下是与问题相关的背景信息：\n\n"
        "【背景信息】\n"
        "{context}\n"
        "【背景信息结束】\n\n"
        "问题：{question}"
    ),
}

MMLU_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["question", "subject", "choices", "answer"],
    "properties": {
        "question": {"type": "string"},
        "subject": {"type": "string"},
        "choices": {"type": "array", "minItems": 2, "items": {"type": "string"}},
        "answer": {"type": "integer"},
    },
}

ARC_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["id", "question", "choices", "answerKey"],
    "properties": {
        "id": {"type": "string"},
        "question": {},
        "choices": {},
        "answerKey": {"type": "string"},
        "metadata": {"type": "object"},
    },
}

CEVAL_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["question", "A", "B", "C", "D", "answer"],
    "properties": {
        "id": {},
        "question": {"type": "string"},
        "A": {"type": "string"},
        "B": {"type": "string"},
        "C": {"type": "string"},
        "D": {"type": "string"},
        "answer": {"type": "string"},
        "explanation": {"type": "string"},
        "subject": {"type": "string"},
        "metadata": {"type": "object"},
    },
}

CMMLU_SOURCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["Question", "A", "B", "C", "D", "Answer"],
    "properties": {
        "Unnamed: 0": {},
        "Question": {"type": "string"},
        "A": {"type": "string"},
        "B": {"type": "string"},
        "C": {"type": "string"},
        "D": {"type": "string"},
        "Answer": {"type": "string"},
        "subject": {"type": "string"},
        "metadata": {"type": "object"},
    },
}

GENERAL_MCQ_PROMPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}

GENERAL_MCQ_PROMPT_CONFIG: dict[str, Any] = {}
