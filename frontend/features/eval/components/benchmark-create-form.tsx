"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { createBenchmarkDefinition, updateBenchmarkDefinition } from "@/features/eval/api";
import { getPresetLabel, getTemplateTypeLabel } from "@/features/eval/eval-template-meta";
import { cn } from "@/lib/utils";
import type { BenchmarkDefinitionDetail, EvalTemplateSummary } from "@/types/api";

const CATEGORIES = [
  { value: "llm", label: "语言模型" },
  { value: "math", label: "数学推理" },
  { value: "code", label: "代码生成" },
  { value: "reasoning", label: "逻辑推理" },
  { value: "knowledge", label: "知识问答" },
  { value: "instruction", label: "指令遵循" },
  { value: "domain", label: "领域专业" },
  { value: "other", label: "其他" }
] as const;

const DEFAULT_PATHS: Record<string, string> = {
  input: "input",
  target: "target",
  id: "id"
};

type BenchmarkCreateFormProps = {
  evalTemplates: EvalTemplateSummary[];
  mode?: "create" | "edit";
  initialBenchmark?: BenchmarkDefinitionDetail | null;
};

export function BenchmarkCreateForm({
  evalTemplates,
  mode = "create",
  initialBenchmark = null
}: BenchmarkCreateFormProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const initialFieldMapping = React.useMemo(
    () => parseFieldMapping(initialBenchmark?.field_mapping_json),
    [initialBenchmark]
  );
  const [showAdvanced, setShowAdvanced] = React.useState(
    () =>
      Boolean(
        initialBenchmark?.field_mapping_json ||
          initialBenchmark?.prompt_template ||
          initialBenchmark?.system_prompt
      )
  );

  const name = initialBenchmark?.name ?? "";
  const [displayName, setDisplayName] = React.useState(initialBenchmark?.display_name ?? "");
  const [description, setDescription] = React.useState(initialBenchmark?.description ?? "");
  const [category, setCategory] = React.useState(initialBenchmark?.category ?? "llm");
  const [selectedTemplateId, setSelectedTemplateId] = React.useState<string>(
    initialBenchmark?.eval_template_id ??
      evalTemplates.find(
        (template) =>
          template.template_type === "llm_categorical" || template.template_type === "llm_numeric"
      )?.id ??
      "none"
  );

  // Advanced: field mapping paths
  const [paths, setPaths] = React.useState<Record<string, string>>(
    () => initialFieldMapping.paths
  );

  // Advanced: input template (multi-field concatenation)
  const [inputTemplate, setInputTemplate] = React.useState(initialFieldMapping.inputTemplate);

  // Advanced: prompt
  const [systemPrompt, setSystemPrompt] = React.useState(initialBenchmark?.system_prompt ?? "");
  const [promptTemplate, setPromptTemplate] = React.useState(initialBenchmark?.prompt_template ?? "");

  const benchmarkEvalTemplates = React.useMemo(
    () =>
      evalTemplates.filter(
        (template) =>
          template.template_type === "llm_categorical" || template.template_type === "llm_numeric"
      ),
    [evalTemplates]
  );
  const selectedTemplate =
    benchmarkEvalTemplates.find((template) => template.id === selectedTemplateId) ?? null;

  function updatePath(key: string, value: string) {
    setPaths((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!displayName.trim()) {
      setError("请输入显示名称。");
      return;
    }
    if (!selectedTemplate) {
      setError("请选择一个评测模板。");
      return;
    }

    const fieldMapping = buildFieldMapping(paths, inputTemplate.trim());

    setSubmitting(true);
    try {
      const optionalValue = (value: string) => {
        const trimmed = value.trim();
        if (trimmed) {
          return trimmed;
        }
        return mode === "edit" ? null : undefined;
      };
      const payload = {
        display_name: displayName.trim(),
        description: optionalValue(description),
        category: category || undefined,
        default_eval_method: "judge-template",
        requires_judge_model: true,
        field_mapping: fieldMapping ?? (mode === "edit" ? null : undefined),
        system_prompt: optionalValue(systemPrompt),
        prompt_template: optionalValue(promptTemplate),
        eval_template_id: selectedTemplate.id
      };

      if (mode === "edit" && initialBenchmark) {
        await updateBenchmarkDefinition(initialBenchmark.name, payload);
        router.push(`/model/eval-benchmarks/${initialBenchmark.name}`);
      } else {
        const created = await createBenchmarkDefinition(payload);
        router.push(`/model/eval-benchmarks/${created.name}`);
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Info */}
      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">基础信息</legend>

        <div className={cn("grid gap-4", mode === "edit" ? "md:grid-cols-2" : "")}>
          {mode === "edit" ? (
            <div className="space-y-2">
              <Label htmlFor="name">Benchmark ID</Label>
              <Input id="name" value={name} readOnly disabled />
              <p className="text-xs text-muted-foreground">Benchmark ID 创建后不可修改</p>
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="displayName">显示名称</Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="如 My MCQ Benchmark"
            />
            {mode === "create" ? (
              <p className="text-xs text-muted-foreground">
                系统会自动生成以 <code className="rounded bg-muted px-1">bench-</code> 开头的
                Benchmark ID。
              </p>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">描述</Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="评测内容和用途说明"
          />
        </div>

        <div className="space-y-2">
          <Label>分类</Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </fieldset>

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">评测模板</legend>

        <div className="space-y-2">
          <Label>选择模板</Label>
          <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
            <SelectTrigger>
              <SelectValue placeholder="选择评测模板" />
            </SelectTrigger>
            <SelectContent>
              {benchmarkEvalTemplates.length === 0 ? (
                <SelectItem value="none" disabled>
                  暂无可用模板
                </SelectItem>
              ) : null}
              {benchmarkEvalTemplates.map((template) => (
                <SelectItem key={template.id} value={template.id}>
                  {template.name} · v{template.version}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            创建后的 Benchmark 会作为模板驱动的数据集容器使用。你可以继续上传和管理它的
            Version 数据集，并在运行任务时复用这里选择的评测模板。
          </p>
        </div>

        {selectedTemplate ? (
          <div className="grid gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4 md:grid-cols-3">
            <TemplateSummaryItem label="模板名称" value={`${selectedTemplate.name} · v${selectedTemplate.version}`} />
            <TemplateSummaryItem
              label="评测类型"
              value={getTemplateTypeLabel(selectedTemplate.template_type)}
            />
            <TemplateSummaryItem
              label="预设"
              value={getPresetLabel(selectedTemplate.preset_id)}
            />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
            当前没有可用的 LLM 自动评测模板。请先到评测模板页创建模板，再回来创建 Benchmark。
          </div>
        )}
      </fieldset>

      {/* Advanced Options */}
      <div>
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? "收起" : "展开"}高级选项（字段映射 & Prompt 模板）
        </button>
      </div>

      {showAdvanced && (
        <>
          <fieldset className="space-y-4 rounded-lg border border-border p-4">
            <legend className="px-2 text-sm font-medium">
              字段映射
              <span className="ml-2 font-normal text-muted-foreground">
                数据集 JSONL 字段名 → 标准格式
              </span>
            </legend>

            <div className="mb-2 grid grid-cols-[100px_1fr] gap-3 text-xs font-medium text-muted-foreground">
              <span>目标字段</span>
              <span>数据路径</span>
            </div>

            <div className="space-y-3">
              <FieldMappingRow
                target="input"
                placeholder="input"
                hint="问题或对话内容"
                value={paths.input}
                onChange={(v) => updatePath("input", v)}
                disabled={!!inputTemplate.trim()}
              />
              <FieldMappingRow
                target="target"
                placeholder="target"
                hint="标准答案或 rubrics"
                value={paths.target}
                onChange={(v) => updatePath("target", v)}
              />
              <FieldMappingRow
                target="id"
                placeholder="id"
                hint="样本唯一标识（可选）"
                value={paths.id}
                onChange={(v) => updatePath("id", v)}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              填写 JSONL 中的数据路径。支持嵌套访问和数组索引，如{" "}
              <code className="rounded bg-muted px-1">question</code>、
              <code className="rounded bg-muted px-1">data.answer</code>、
              <code className="rounded bg-muted px-1">messages[-1].content</code>。
            </p>

            <div className="mt-4 space-y-2 border-t border-border pt-4">
              <Label htmlFor="inputTemplate">Input 模板拼接（可选）</Label>
              <Input
                id="inputTemplate"
                value={inputTemplate}
                onChange={(e) => setInputTemplate(e.target.value)}
                placeholder="如：背景：{context}\n问题：{question}"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                当数据集中的 input 需要从多个字段拼接时使用。用{" "}
                <code className="rounded bg-muted px-1">{"{字段名}"}</code>{" "}
                引用 JSONL 中的顶层字段。设置后将覆盖上方的 input 路径。
              </p>
            </div>
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-border p-4">
            <legend className="px-2 text-sm font-medium">Prompt 模板（可选）</legend>

            <div className="space-y-2">
              <Label htmlFor="systemPrompt">System Prompt</Label>
              <Input
                id="systemPrompt"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="如：你是一个评测助手..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="promptTemplate">Prompt Template</Label>
              <Input
                id="promptTemplate"
                value={promptTemplate}
                onChange={(e) => setPromptTemplate(e.target.value)}
                placeholder="如：请回答以下问题：{question}"
              />
            </div>
          </fieldset>
        </>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-3">
        <Button type="submit" disabled={submitting || benchmarkEvalTemplates.length === 0}>
          {submitting
            ? mode === "edit"
              ? "保存中..."
              : "创建中..."
            : mode === "edit"
              ? "保存 Benchmark"
              : "创建 Benchmark"}
        </Button>
        <Button type="button" variant="outline" onClick={() => router.back()}>
          取消
        </Button>
      </div>
    </form>
  );
}

function FieldMappingRow({
  target,
  placeholder,
  hint,
  value,
  onChange,
  disabled
}: {
  target: string;
  placeholder: string;
  hint: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className={cn("grid grid-cols-[100px_1fr] items-center gap-3", disabled && "opacity-40")}>
      <code className="rounded bg-muted px-2 py-1 text-center text-xs">{target}</code>
      <div className="flex items-center gap-2">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="font-mono text-xs"
          disabled={disabled}
        />
        <span className="shrink-0 text-xs text-muted-foreground">
          {disabled ? "由模板拼接覆盖" : hint}
        </span>
      </div>
    </div>
  );
}

function TemplateSummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm text-foreground">{value}</div>
    </div>
  );
}

/**
 * Convert user-facing paths into the backend field_mapping format.
 *
 * A simple path like ``"question"`` becomes ``{ input_field: "question" }``.
 * A nested path like ``"data.answer"`` is split into a top-level field and a
 * selector: ``{ target_field: "data", target_selector: "answer" }``.
 * If ``inputTemplate`` is set, it is included as ``input_template`` and the
 * input path is ignored.
 */
function buildFieldMapping(
  paths: Record<string, string>,
  inputTemplate?: string
): Record<string, string> | undefined {
  const result: Record<string, string> = {};
  let hasCustom = false;

  if (inputTemplate) {
    result.input_template = inputTemplate;
    hasCustom = true;
  }

  for (const [key, rawPath] of Object.entries(paths)) {
    // Skip input path when input_template is set
    if (key === "input" && inputTemplate) {
      continue;
    }

    const path = rawPath.trim();
    if (!path || path === key) {
      continue;
    }

    // Split on the first dot or bracket to separate top-level field from selector.
    const firstDot = path.indexOf(".");
    const firstBracket = path.indexOf("[");

    let splitAt = -1;
    if (firstDot >= 0 && firstBracket >= 0) {
      splitAt = Math.min(firstDot, firstBracket);
    } else if (firstDot >= 0) {
      splitAt = firstDot;
    } else if (firstBracket >= 0) {
      splitAt = firstBracket;
    }

    if (splitAt > 0) {
      result[`${key}_field`] = path.slice(0, splitAt);
      const selectorPart = path.slice(splitAt);
      result[`${key}_selector`] = selectorPart.startsWith(".")
        ? selectorPart.slice(1)
        : selectorPart;
    } else {
      result[`${key}_field`] = path;
    }
    hasCustom = true;
  }

  return hasCustom ? result : undefined;
}

function parseFieldMapping(rawFieldMapping: Record<string, unknown> | null | undefined): {
  paths: Record<string, string>;
  inputTemplate: string;
} {
  const fieldMapping = rawFieldMapping ?? {};
  const paths = { ...DEFAULT_PATHS };

  for (const key of ["input", "target", "id"] as const) {
    const field = fieldMapping[`${key}_field`];
    const selector = fieldMapping[`${key}_selector`];

    if (typeof field !== "string" || !field.trim()) {
      continue;
    }

    let combined = field.trim();
    if (typeof selector === "string" && selector.trim()) {
      const selectorValue = selector.trim();
      combined += selectorValue.startsWith("[") ? selectorValue : `.${selectorValue}`;
    }
    paths[key] = combined;
  }

  return {
    paths,
    inputTemplate:
      typeof fieldMapping.input_template === "string" ? fieldMapping.input_template : ""
  };
}
