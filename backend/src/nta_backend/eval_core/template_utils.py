"""Utilities for EvalTemplate prompt compilation and output schema building.

These are kept separate from the service layer to avoid importing database
dependencies in eval_core code.
"""

from __future__ import annotations

import re

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def extract_template_vars(prompt: str) -> list[str]:
    """Extract ``{{variable}}`` placeholder names from a prompt template."""
    return list(dict.fromkeys(_VAR_PATTERN.findall(prompt)))


def extract_output_config_vars(output_config: dict | None) -> list[str]:
    """Extract template variables referenced from non-prompt config fields."""
    if not isinstance(output_config, dict):
        return []

    text_sources = output_config.get("text_sources")
    if not isinstance(text_sources, dict):
        return []

    values: list[str] = []
    for key in ("left_template", "right_template"):
        value = text_sources.get(key)
        if isinstance(value, str) and value:
            values.extend(extract_template_vars(value))

    return list(dict.fromkeys(values))


def collect_template_vars(prompt: str, output_config: dict | None = None) -> list[str]:
    """Collect variables referenced by the prompt and additional config fields."""
    vars_: list[str] = []
    vars_.extend(extract_template_vars(prompt))
    vars_.extend(extract_output_config_vars(output_config))
    return list(dict.fromkeys(vars_))


def compile_template(prompt: str, variables: dict[str, str]) -> str:
    """Replace ``{{var}}`` placeholders with actual values."""
    return _VAR_PATTERN.sub(lambda m: variables.get(m.group(1), ""), prompt)


def _extract_categories(output_config: dict) -> list[str]:
    categories = output_config.get("categories", [])
    if isinstance(categories, list):
        normalized = [str(category) for category in categories if str(category).strip()]
        if normalized:
            return normalized

    label_groups = output_config.get("label_groups", [])
    if not isinstance(label_groups, list):
        return []

    flattened: list[str] = []
    for group in label_groups:
        if not isinstance(group, dict):
            continue
        labels = group.get("labels", [])
        if not isinstance(labels, list):
            continue
        for label in labels:
            label_text = str(label).strip()
            if label_text:
                flattened.append(label_text)

    return list(dict.fromkeys(flattened))


def build_output_instruction(output_type: str, output_config: dict) -> str:
    """Build a JSON schema instruction string for the judge LLM response."""
    reasoning_hint = output_config.get("reasoning_hint", "Explain your reasoning")
    score_hint = output_config.get("score_hint", "Your score")

    if output_type == "boolean":
        return (
            f"Return only valid JSON with this schema:\n"
            f'{{"reasoning": "{reasoning_hint}", "score": true or false}}'
        )

    if output_type == "categorical":
        categories = _extract_categories(output_config)
        cat_str = " | ".join(f'"{c}"' for c in categories)
        return (
            f"Return only valid JSON with this schema:\n"
            f'{{"reasoning": "{reasoning_hint}", "score": {cat_str}}}'
        )

    # numeric (default)
    score_min = output_config.get("score_min", 1)
    score_max = output_config.get("score_max", 5)
    return (
        f"Return only valid JSON with this schema:\n"
        f'{{"reasoning": "{reasoning_hint}", "score": <integer {score_min}-{score_max}>}}'
    )
