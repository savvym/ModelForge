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
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createEvalTemplate, updateEvalTemplate } from "@/features/eval/api";
import {
  defaultFailTags,
  defaultPassTags,
  getPresetLabel,
  getPresetsForTemplateType,
  getTemplateTypeLabel,
  getTemplateTypeMeta,
  LLM_CATEGORICAL_PRESETS,
  LLM_NUMERIC_PRESETS,
  parseTagList,
  stringifyTagList,
  STRING_MATCH_OPERATORS,
  TEMPLATE_TYPES,
  type TemplatePresetMeta,
  type TemplateTypeId,
  TEXT_SIMILARITY_METRICS,
} from "@/features/eval/eval-template-meta";
import { cn } from "@/lib/utils";
import type { EvalTemplateSummary } from "@/types/api";

const TEMPLATE_VAR_PATTERN = /\{\{(\w+)\}\}/g;

type NumericState = {
  scoreMin: string;
  scoreMax: string;
  passThreshold: string;
};

type EvalTemplateCreateFormProps = {
  initialTemplate?: EvalTemplateSummary | null;
  mode?: "create" | "edit";
};

export function EvalTemplateCreateForm({
  initialTemplate = null,
  mode = "create",
}: EvalTemplateCreateFormProps) {
  const router = useRouter();
  const isEdit = mode === "edit" && initialTemplate != null;
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const initialTemplateType = readTemplateType(initialTemplate?.template_type);
  const initialOutputConfig = initialTemplate?.output_config ?? {};

  const [selectedTemplateType, setSelectedTemplateType] = React.useState<TemplateTypeId | null>(
    initialTemplateType
  );
  const [selectedPresetId, setSelectedPresetId] = React.useState<string | null>(
    initialTemplate?.preset_id ?? null
  );

  const [name, setName] = React.useState(initialTemplate?.name ?? "");
  const [description, setDescription] = React.useState(initialTemplate?.description ?? "");
  const [model, setModel] = React.useState(initialTemplate?.model ?? "");
  const [provider, setProvider] = React.useState(initialTemplate?.provider ?? "");
  const [prompt, setPrompt] = React.useState(initialTemplate?.prompt ?? "");

  const [passLabelsText, setPassLabelsText] = React.useState(
    readLabelGroupText(initialOutputConfig, "pass", defaultPassTags())
  );
  const [failLabelsText, setFailLabelsText] = React.useState(
    readLabelGroupText(initialOutputConfig, "fail", defaultFailTags())
  );

  const [numericState, setNumericState] = React.useState<NumericState>(
    readNumericState(initialOutputConfig, initialTemplateType)
  );

  const [leftTemplate, setLeftTemplate] = React.useState(
    readTextSource(initialOutputConfig, "left_template", "{{output}}")
  );
  const [rightTemplate, setRightTemplate] = React.useState(
    readTextSource(initialOutputConfig, "right_template", "{{target}}")
  );
  const [stringOperator, setStringOperator] = React.useState(
    readRuleConfigValue(initialOutputConfig, "operator", "equals")
  );
  const [similarityMetric, setSimilarityMetric] = React.useState(
    readRuleConfigValue(initialOutputConfig, "metric", "ROUGE_L")
  );

  const selectedTypeMeta = getTemplateTypeMeta(selectedTemplateType);
  const requiresPresetSelection = Boolean(selectedTypeMeta?.supportsPresets);

  const vars = React.useMemo(() => {
    const sources: string[] = [];
    if (selectedTemplateType === "llm_categorical" || selectedTemplateType === "llm_numeric") {
      sources.push(prompt);
    }
    if (
      selectedTemplateType === "rule_string_match" ||
      selectedTemplateType === "rule_text_similarity"
    ) {
      sources.push(leftTemplate, rightTemplate);
    }
    return extractTemplateVars(sources);
  }, [leftTemplate, prompt, rightTemplate, selectedTemplateType]);

  function applyTemplateType(type: TemplateTypeId) {
    setSelectedTemplateType(type);
    setSelectedPresetId(null);
    setError(null);
    resetTypeSpecificState(type);
  }

  function resetTypeSpecificState(type: TemplateTypeId) {
    setPrompt("");
    setModel("");
    setProvider("");
    setPassLabelsText(defaultPassTags());
    setFailLabelsText(defaultFailTags());
    setNumericState({
      scoreMin: "1",
      scoreMax: "5",
      passThreshold: "3",
    });
    setLeftTemplate("{{output}}");
    setRightTemplate("{{target}}");
    setStringOperator("equals");
    setSimilarityMetric("ROUGE_L");

    if (type === "rule_text_similarity") {
      setNumericState({
        scoreMin: "0",
        scoreMax: "1",
        passThreshold: "0.8",
      });
    }
  }

  function applyPreset(preset: TemplatePresetMeta) {
    setSelectedPresetId(preset.id);
    setError(null);
    setPrompt(preset.prompt);

    if (selectedTemplateType === "llm_categorical") {
      setPassLabelsText((preset.passLabels ?? [defaultPassTags()]).join(", "));
      setFailLabelsText((preset.failLabels ?? [defaultFailTags()]).join(", "));
    }

    if (selectedTemplateType === "llm_numeric") {
      setNumericState({
        scoreMin: preset.scoreMin ?? "1",
        scoreMax: preset.scoreMax ?? "5",
        passThreshold: preset.passThreshold ?? "3",
      });
    }
  }

  function updateNumericState(key: keyof NumericState, value: string) {
    setNumericState((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!selectedTemplateType || !selectedTypeMeta) {
      setError("请先选择评测类型。");
      return;
    }
    if (!name.trim()) {
      setError("请输入模板名称。");
      return;
    }

    const passLabels = parseTagList(passLabelsText);
    const failLabels = parseTagList(failLabelsText);

    if (selectedTemplateType === "llm_categorical" || selectedTemplateType === "llm_numeric") {
      if (!prompt.trim()) {
        setError("LLM 自动评测模板需要填写 Prompt。");
        return;
      }
      if (vars.length === 0) {
        setError("请在模板中至少引用一个运行时变量，例如 {{input}}、{{target}} 或 {{output}}。");
        return;
      }
    }

    if (selectedTemplateType === "llm_categorical" || selectedTemplateType === "manual_categorical") {
      if (passLabels.length === 0 || failLabels.length === 0) {
        setError("请至少为 Pass 组和 Fail 组各配置一个标签。");
        return;
      }
    }

    if (selectedTemplateType === "llm_numeric") {
      const scoreMin = Number(numericState.scoreMin);
      const scoreMax = Number(numericState.scoreMax);
      const passThreshold = Number(numericState.passThreshold);

      if (!Number.isFinite(scoreMin) || !Number.isFinite(scoreMax) || !Number.isFinite(passThreshold)) {
        setError("请填写有效的评分范围和通过阈值。");
        return;
      }
      if (scoreMax <= scoreMin) {
        setError("评分范围要求最高分大于最低分。");
        return;
      }
      if (passThreshold < scoreMin || passThreshold > scoreMax) {
        setError("通过阈值必须落在评分范围内。");
        return;
      }
    }

    if (
      selectedTemplateType === "rule_string_match" ||
      selectedTemplateType === "rule_text_similarity"
    ) {
      if (!leftTemplate.trim() || !rightTemplate.trim()) {
        setError("规则评测需要同时填写左右两侧的文本模板。");
        return;
      }
      if (vars.length === 0) {
        setError("请在规则模板中至少引用一个运行时变量，例如 {{output}} 或 {{target}}。");
        return;
      }
    }

    if (selectedTemplateType === "rule_text_similarity") {
      const passThreshold = Number(numericState.passThreshold);
      if (!Number.isFinite(passThreshold)) {
        setError("请填写有效的相似度阈值。");
        return;
      }
    }

    setSubmitting(true);
    try {
      const modelValue = model.trim();
      const providerValue = provider.trim();
      const descriptionValue = description.trim();
      const payload = {
        prompt: selectedTypeMeta.requiresModel ? prompt.trim() : "",
        template_type: selectedTemplateType,
        preset_id: selectedPresetId,
        output_type: selectedTypeMeta.outputType,
        output_config: buildOutputConfig({
          failLabels,
          leftTemplate,
          numericState,
          passLabels,
          rightTemplate,
          selectedTemplateType,
          similarityMetric,
          stringOperator,
        }),
        model: selectedTypeMeta.requiresModel
          ? modelValue || (isEdit ? null : undefined)
          : isEdit ? null : undefined,
        provider: selectedTypeMeta.requiresModel
          ? providerValue || (isEdit ? null : undefined)
          : isEdit ? null : undefined,
        description: descriptionValue || (isEdit ? null : undefined),
      };

      if (isEdit && initialTemplate) {
        await updateEvalTemplate(initialTemplate.name, payload);
      } else {
        await createEvalTemplate({
          ...payload,
          name: name.trim().toLowerCase().replace(/\s+/g, "_"),
        });
      }
      router.push("/model/eval?tab=dimensions");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  if (!selectedTemplateType) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          先选择评测类型，再进入对应的模板配置。LLM 自动评测支持类型内预设，规则评测和人工评测直接配置。
        </p>
        <div className="grid gap-3">
          {TEMPLATE_TYPES.map((type) => (
            <button
              key={type.id}
              type="button"
              onClick={() => applyTemplateType(type.id)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors",
                "border-border hover:border-primary/50 hover:bg-primary/5",
              )}
            >
              <span className="text-sm font-medium">{type.label}</span>
              <span className="text-xs text-muted-foreground">{type.description}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!isEdit && requiresPresetSelection && !selectedPresetId) {
    const presets = getPresetsForTemplateType(selectedTemplateType);
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">已选择评测类型</p>
            <div className="mt-1 text-sm font-medium text-foreground">
              {getTemplateTypeLabel(selectedTemplateType)}
            </div>
          </div>
          {!isEdit ? (
            <Button type="button" variant="outline" onClick={() => setSelectedTemplateType(null)}>
              重新选择类型
            </Button>
          ) : null}
        </div>

        <p className="text-sm text-muted-foreground">
          选择一个类型内预设作为起点，也可以使用“自定义评分器”从零开始配置。
        </p>

        <div className="grid gap-3">
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => applyPreset(preset)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors",
                "border-border hover:border-primary/50 hover:bg-primary/5",
              )}
            >
              <span className="text-sm font-medium">{preset.label}</span>
              <span className="text-xs text-muted-foreground">{preset.description}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (!selectedTypeMeta) {
    return null;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>评测类型：{getTemplateTypeLabel(selectedTemplateType)}</span>
        {requiresPresetSelection ? <span>预设：{getPresetLabel(selectedPresetId)}</span> : null}
        {!isEdit ? (
          <button
            type="button"
            className="text-primary hover:underline"
            onClick={() => {
              if (requiresPresetSelection) {
                setSelectedPresetId(null);
              } else {
                setSelectedTemplateType(null);
              }
            }}
          >
            {requiresPresetSelection ? "重新选择预设" : "重新选择类型"}
          </button>
        ) : (
          <span>保存后会生成新版本</span>
        )}
      </div>

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">基础信息</legend>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="name">模板名称</Label>
            <Input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={isEdit}
              placeholder="如 answer_quality_v1"
            />
            <p className="text-xs text-muted-foreground">
              {isEdit ? "模板名称创建后不可修改。" : "作为模板 ID 保存，建议使用英文、数字和下划线。"}
            </p>
          </div>

          {selectedTypeMeta.requiresModel ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="model">Judge 模型（可选）</Label>
                <Input
                  id="model"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder="留空使用任务级 Judge 模型"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider">Provider（可选）</Label>
                <Input
                  id="provider"
                  value={provider}
                  onChange={(event) => setProvider(event.target.value)}
                  placeholder="例如 openai-compatible"
                />
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
              当前类型不依赖 Judge 模型。
            </div>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">描述</Label>
          <Input
            id="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="说明模板用途、适用场景和评分意图"
          />
        </div>
      </fieldset>

      {(selectedTemplateType === "llm_categorical" || selectedTemplateType === "llm_numeric") && (
        <fieldset className="space-y-4 rounded-lg border border-border p-4">
          <legend className="px-2 text-sm font-medium">Prompt 模板</legend>
          <div className="space-y-2">
            <Label htmlFor="prompt">Judge Prompt</Label>
            <Textarea
              id="prompt"
              rows={12}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="编写 Judge LLM 的评分规则和判断标准"
              className="min-h-[240px] font-mono text-sm"
            />
          </div>
          <VariableHint vars={vars} />
        </fieldset>
      )}

      {(selectedTemplateType === "llm_categorical" || selectedTemplateType === "manual_categorical") && (
        <fieldset className="space-y-4 rounded-lg border border-border p-4">
          <legend className="px-2 text-sm font-medium">标签分组</legend>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="pass-labels">Pass 组标签（逗号分隔）</Label>
              <Input
                id="pass-labels"
                value={passLabelsText}
                onChange={(event) => setPassLabelsText(event.target.value)}
                placeholder="Pass"
              />
              <p className="text-xs text-muted-foreground">这些标签会被视作通过结果。</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fail-labels">Fail 组标签（逗号分隔）</Label>
              <Input
                id="fail-labels"
                value={failLabelsText}
                onChange={(event) => setFailLabelsText(event.target.value)}
                placeholder="Fail"
              />
              <p className="text-xs text-muted-foreground">这些标签会被视作未通过结果。</p>
            </div>
          </div>
        </fieldset>
      )}

      {selectedTemplateType === "llm_numeric" && (
        <fieldset className="space-y-4 rounded-lg border border-border p-4">
          <legend className="px-2 text-sm font-medium">评分配置</legend>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="score-min">最低分</Label>
              <Input
                id="score-min"
                value={numericState.scoreMin}
                onChange={(event) => updateNumericState("scoreMin", event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="score-max">最高分</Label>
              <Input
                id="score-max"
                value={numericState.scoreMax}
                onChange={(event) => updateNumericState("scoreMax", event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pass-threshold">通过阈值</Label>
              <Input
                id="pass-threshold"
                value={numericState.passThreshold}
                onChange={(event) => updateNumericState("passThreshold", event.target.value)}
              />
            </div>
          </div>
        </fieldset>
      )}

      {selectedTemplateType === "rule_string_match" && (
        <fieldset className="space-y-4 rounded-lg border border-border p-4">
          <legend className="px-2 text-sm font-medium">文本对比</legend>
          <p className="text-xs text-muted-foreground">
            使用 {"{{input}}"}、{"{{target}}"}、{"{{output}}"} 等变量构造左右两侧文本，再选择匹配规则。
          </p>
          <div className="grid gap-4 xl:grid-cols-[1fr_220px_1fr]">
            <div className="space-y-2">
              <Label htmlFor="left-template">左侧文本模板</Label>
              <Textarea
                id="left-template"
                rows={12}
                value={leftTemplate}
                onChange={(event) => setLeftTemplate(event.target.value)}
                className="min-h-[220px] font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label>比较算子</Label>
              <Select value={stringOperator} onValueChange={setStringOperator}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STRING_MATCH_OPERATORS.map((operator) => (
                    <SelectItem key={operator.value} value={operator.value}>
                      {operator.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="right-template">右侧文本模板</Label>
              <Textarea
                id="right-template"
                rows={12}
                value={rightTemplate}
                onChange={(event) => setRightTemplate(event.target.value)}
                className="min-h-[220px] font-mono text-sm"
              />
            </div>
          </div>
          <VariableHint vars={vars} />
        </fieldset>
      )}

      {selectedTemplateType === "rule_text_similarity" && (
        <>
          <fieldset className="space-y-4 rounded-lg border border-border p-4">
            <legend className="px-2 text-sm font-medium">文本对比</legend>
            <p className="text-xs text-muted-foreground">
              使用 {"{{input}}"}、{"{{target}}"}、{"{{output}}"} 等变量构造左右两侧文本，再选择相似度指标。
            </p>
            <div className="grid gap-4 xl:grid-cols-[1fr_220px_1fr]">
              <div className="space-y-2">
                <Label htmlFor="left-similarity-template">左侧文本模板</Label>
                <Textarea
                  id="left-similarity-template"
                  rows={12}
                  value={leftTemplate}
                  onChange={(event) => setLeftTemplate(event.target.value)}
                  className="min-h-[220px] font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label>相似度指标</Label>
                <Select value={similarityMetric} onValueChange={setSimilarityMetric}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TEXT_SIMILARITY_METRICS.map((metric) => (
                      <SelectItem key={metric.value} value={metric.value}>
                        {metric.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="space-y-2 pt-2">
                  <Label htmlFor="similarity-threshold">通过阈值</Label>
                  <Input
                    id="similarity-threshold"
                    value={numericState.passThreshold}
                    onChange={(event) => updateNumericState("passThreshold", event.target.value)}
                    placeholder="0.8"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="right-similarity-template">右侧文本模板</Label>
                <Textarea
                  id="right-similarity-template"
                  rows={12}
                  value={rightTemplate}
                  onChange={(event) => setRightTemplate(event.target.value)}
                  className="min-h-[220px] font-mono text-sm"
                />
              </div>
            </div>
            <VariableHint vars={vars} />
          </fieldset>
        </>
      )}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="flex gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting
            ? isEdit
              ? "保存中..."
              : "创建中..."
            : isEdit
              ? "保存新版本"
              : "创建模板"}
        </Button>
        <Button type="button" variant="outline" onClick={() => router.back()}>
          取消
        </Button>
      </div>
    </form>
  );
}

function VariableHint({ vars }: { vars: string[] }) {
  if (vars.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        当前还没有识别到变量。请使用 {"{{input}}"}、{"{{target}}"}、{"{{output}}"} 等占位符。
      </p>
    );
  }

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">自动提取的变量：</p>
      <div className="flex flex-wrap gap-2">
        {vars.map((variable) => (
          <code key={variable} className="rounded bg-muted px-2 py-0.5 text-xs">
            {`{{${variable}}}`}
          </code>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        运行时会自动从 Sample 的 input、target、output 和 metadata 字段填充这些变量。
      </p>
    </div>
  );
}

function extractTemplateVars(values: string[]) {
  const variables: string[] = [];
  for (const value of values) {
    for (const match of value.matchAll(TEMPLATE_VAR_PATTERN)) {
      variables.push(match[1]);
    }
  }
  return [...new Set(variables)];
}

function readTemplateType(value: string | null | undefined): TemplateTypeId | null {
  return TEMPLATE_TYPES.some((type) => type.id === value) ? (value as TemplateTypeId) : null;
}

function readLabelGroupText(
  outputConfig: Record<string, unknown>,
  scorePolicy: "pass" | "fail",
  fallback: string
) {
  const groups = outputConfig.label_groups;
  if (!Array.isArray(groups)) {
    return fallback;
  }

  const match = groups.find((group) => {
    if (!isRecord(group)) {
      return false;
    }
    return group.score_policy === scorePolicy || group.key === scorePolicy;
  });
  if (!isRecord(match) || !Array.isArray(match.labels)) {
    return fallback;
  }

  const labels = match.labels.filter((label): label is string => typeof label === "string");
  return labels.length > 0 ? stringifyTagList(labels) : fallback;
}

function readNumericState(
  outputConfig: Record<string, unknown>,
  templateType: TemplateTypeId | null
): NumericState {
  const numericRange = isRecord(outputConfig.numeric_range) ? outputConfig.numeric_range : {};
  const defaultState =
    templateType === "rule_text_similarity"
      ? { scoreMin: "0", scoreMax: "1", passThreshold: "0.8" }
      : { scoreMin: "1", scoreMax: "5", passThreshold: "3" };

  return {
    scoreMin: stringifyConfigValue(outputConfig.score_min ?? numericRange.min, defaultState.scoreMin),
    scoreMax: stringifyConfigValue(outputConfig.score_max ?? numericRange.max, defaultState.scoreMax),
    passThreshold: stringifyConfigValue(
      outputConfig.pass_threshold ?? outputConfig.similarity_threshold ?? numericRange.pass_threshold,
      defaultState.passThreshold
    ),
  };
}

function readTextSource(
  outputConfig: Record<string, unknown>,
  key: "left_template" | "right_template",
  fallback: string
) {
  const textSources = isRecord(outputConfig.text_sources) ? outputConfig.text_sources : {};
  return typeof textSources[key] === "string" ? textSources[key] : fallback;
}

function readRuleConfigValue(
  outputConfig: Record<string, unknown>,
  key: "operator" | "metric",
  fallback: string
) {
  const ruleConfig = isRecord(outputConfig.rule_config) ? outputConfig.rule_config : {};
  return typeof ruleConfig[key] === "string" ? ruleConfig[key] : fallback;
}

function stringifyConfigValue(value: unknown, fallback: string) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function buildLabelGroups(passLabels: string[], failLabels: string[]) {
  return [
    {
      key: "pass",
      label: "Pass",
      score_policy: "pass",
      labels: passLabels,
    },
    {
      key: "fail",
      label: "Fail",
      score_policy: "fail",
      labels: failLabels,
    },
  ];
}

function buildOutputConfig({
  failLabels,
  leftTemplate,
  numericState,
  passLabels,
  rightTemplate,
  selectedTemplateType,
  similarityMetric,
  stringOperator,
}: {
  failLabels: string[];
  leftTemplate: string;
  numericState: NumericState;
  passLabels: string[];
  rightTemplate: string;
  selectedTemplateType: TemplateTypeId;
  similarityMetric: string;
  stringOperator: string;
}) {
  if (selectedTemplateType === "llm_categorical" || selectedTemplateType === "manual_categorical") {
    const labelGroups = buildLabelGroups(passLabels, failLabels);
    return {
      mode: selectedTemplateType === "manual_categorical" ? "manual" : "llm",
      label_groups: labelGroups,
      categories: [...passLabels, ...failLabels],
      reasoning_hint: "Explain your judgment",
      score_hint: "Select one configured label",
    };
  }

  if (selectedTemplateType === "llm_numeric") {
    const scoreMin = Number(numericState.scoreMin);
    const scoreMax = Number(numericState.scoreMax);
    const passThreshold = Number(numericState.passThreshold);
    return {
      mode: "llm",
      numeric_range: {
        min: scoreMin,
        max: scoreMax,
        pass_threshold: passThreshold,
      },
      score_min: scoreMin,
      score_max: scoreMax,
      pass_threshold: passThreshold,
      reasoning_hint: "Explain your reasoning",
      score_hint: `Rate ${scoreMin}-${scoreMax}`,
    };
  }

  if (selectedTemplateType === "rule_string_match") {
    return {
      mode: "rule",
      rule_config: {
        operator: stringOperator,
      },
      text_sources: {
        left_template: leftTemplate.trim(),
        right_template: rightTemplate.trim(),
      },
      reasoning_hint: "Explain the matching result",
      score_hint: "true if the rule matches, false otherwise",
    };
  }

  const passThreshold = Number(numericState.passThreshold);
  return {
    mode: "rule",
    rule_config: {
      metric: similarityMetric,
    },
    text_sources: {
      left_template: leftTemplate.trim(),
      right_template: rightTemplate.trim(),
    },
    pass_threshold: passThreshold,
    similarity_threshold: passThreshold,
    reasoning_hint: "Explain the similarity result",
    score_hint: `true if similarity is greater than or equal to ${numericState.passThreshold}`,
  };
}

export const __presetsForTests = {
  llmCategorical: LLM_CATEGORICAL_PRESETS,
  llmNumeric: LLM_NUMERIC_PRESETS,
};
