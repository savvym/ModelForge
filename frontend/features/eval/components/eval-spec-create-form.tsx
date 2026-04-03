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
import { Textarea } from "@/components/ui/textarea";
import { createEvalSpec, updateEvalSpec } from "@/features/eval/api";
import type { EvaluationCatalogResponseV2, EvalSpecSummaryV2, EvalSpecVersionSummaryV2 } from "@/types/api";

const NONE_VALUE = "__none__";

type EvalSpecFormProps = {
  catalog: EvaluationCatalogResponseV2;
  initialValue?: EvalSpecSummaryV2;
  mode?: "create" | "edit";
};

export function EvalSpecCreateForm({
  catalog,
  initialValue,
  mode = "create"
}: EvalSpecFormProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const templateOptions = React.useMemo(
    () =>
      catalog.templates.flatMap((template) =>
        template.versions.map((version) => ({
          id: version.id,
          label: `${template.display_name} · v${version.version}`
        }))
      ),
    [catalog.templates]
  );

  const managedVersion = React.useMemo(
    () => getManagedSpecVersion(initialValue),
    [initialValue]
  );

  const [name, setName] = React.useState(initialValue?.name ?? "");
  const [displayName, setDisplayName] = React.useState(initialValue?.display_name ?? "");
  const [description, setDescription] = React.useState(initialValue?.description ?? "");
  const [capabilityGroup, setCapabilityGroup] = React.useState(initialValue?.capability_group ?? "综合");
  const [capabilityCategory, setCapabilityCategory] = React.useState(initialValue?.capability_category ?? "通用");
  const [tagsText, setTagsText] = React.useState(
    Array.isArray(initialValue?.tags_json) && initialValue?.tags_json.length
      ? initialValue.tags_json.map((item) => String(item)).join(",")
      : "evalscope,builtin"
  );
  const [version, setVersion] = React.useState(managedVersion?.version ?? "builtin-v1");
  const [versionDisplayName, setVersionDisplayName] = React.useState(
    managedVersion?.display_name ?? "内置版本"
  );
  const [engine, setEngine] = React.useState(managedVersion?.engine ?? "evalscope");
  const [executionMode, setExecutionMode] = React.useState(managedVersion?.execution_mode ?? "builtin");
  const [engineBenchmarkName, setEngineBenchmarkName] = React.useState(
    managedVersion?.engine_benchmark_name ?? ""
  );
  const [sampleCount, setSampleCount] = React.useState(
    managedVersion?.sample_count != null ? String(managedVersion.sample_count) : ""
  );
  const [templateVersionId, setTemplateVersionId] = React.useState(
    managedVersion?.template_spec_version_id ?? NONE_VALUE
  );
  const [judgePolicyId, setJudgePolicyId] = React.useState(
    managedVersion?.default_judge_policy_id ?? NONE_VALUE
  );
  const [engineConfigText, setEngineConfigText] = React.useState(
    JSON.stringify(managedVersion?.engine_config_json ?? {}, null, 2)
  );
  const [scoringConfigText, setScoringConfigText] = React.useState(
    JSON.stringify(managedVersion?.scoring_config_json ?? {}, null, 2)
  );
  const [inputSchemaText, setInputSchemaText] = React.useState(
    JSON.stringify(initialValue?.input_schema_json ?? {}, null, 2)
  );
  const [outputSchemaText, setOutputSchemaText] = React.useState(
    JSON.stringify(initialValue?.output_schema_json ?? {}, null, 2)
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim() || !displayName.trim() || !version.trim() || !versionDisplayName.trim()) {
      setError("请填写评测类型名称、显示名称、版本号和版本显示名称。");
      return;
    }

    try {
      setSubmitting(true);
      const commonPayload = {
        display_name: displayName.trim(),
        description: normalizeOptional(description),
        capability_group: normalizeOptional(capabilityGroup),
        capability_category: normalizeOptional(capabilityCategory),
        tags_json: splitCsv(tagsText),
        input_schema_json: parseJsonObject(inputSchemaText, "输入 Schema"),
        output_schema_json: parseJsonObject(outputSchemaText, "输出 Schema")
      };
      if (mode === "edit") {
        if (!initialValue || !managedVersion) {
          throw new Error("缺少可编辑的评测类型版本。");
        }
        await updateEvalSpec(initialValue.name, {
          ...commonPayload,
          version: {
            version_id: managedVersion.id,
            version: version.trim(),
            display_name: versionDisplayName.trim(),
            description: normalizeOptional(description),
            engine: engine.trim(),
            execution_mode: executionMode.trim(),
            engine_benchmark_name: normalizeOptional(engineBenchmarkName),
            engine_config_json: parseJsonObject(engineConfigText, "Engine 配置"),
            scoring_config_json: parseJsonObject(scoringConfigText, "Scoring 配置"),
            template_spec_version_id: templateVersionId === NONE_VALUE ? undefined : templateVersionId,
            default_judge_policy_id: judgePolicyId === NONE_VALUE ? undefined : judgePolicyId,
            sample_count: parseOptionalInteger(sampleCount, "样本量"),
            enabled: true,
            is_recommended: true
          }
        });
      } else {
        await createEvalSpec({
          name: normalizeName(name),
          ...commonPayload,
          initial_version: {
            version: version.trim(),
            display_name: versionDisplayName.trim(),
            description: normalizeOptional(description),
            engine: engine.trim(),
            execution_mode: executionMode.trim(),
            engine_benchmark_name: normalizeOptional(engineBenchmarkName),
            engine_config_json: parseJsonObject(engineConfigText, "Engine 配置"),
            scoring_config_json: parseJsonObject(scoringConfigText, "Scoring 配置"),
            template_spec_version_id: templateVersionId === NONE_VALUE ? undefined : templateVersionId,
            default_judge_policy_id: judgePolicyId === NONE_VALUE ? undefined : judgePolicyId,
            sample_count: parseOptionalInteger(sampleCount, "样本量"),
            enabled: true,
            is_recommended: true
          }
        });
      }
      router.push("/model/eval?tab=catalog");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : `${mode === "edit" ? "更新" : "创建"}评测类型失败`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="grid gap-6 md:grid-cols-2">
        <Field label="评测类型名称">
          <Input
            disabled={mode === "edit"}
            onChange={(event) => setName(event.target.value)}
            placeholder="mmlu_cn"
            value={name}
          />
        </Field>
        <Field label="显示名称">
          <Input onChange={(event) => setDisplayName(event.target.value)} placeholder="MMLU 中文版" value={displayName} />
        </Field>
      </div>

      <Field label="描述">
        <Textarea
          className="min-h-[96px]"
          onChange={(event) => setDescription(event.target.value)}
          placeholder="说明这个评测类型覆盖的能力与适用场景。"
          value={description}
        />
      </Field>

      <div className="grid gap-6 md:grid-cols-3">
        <Field label="能力分组">
          <Input onChange={(event) => setCapabilityGroup(event.target.value)} value={capabilityGroup} />
        </Field>
        <Field label="能力分类">
          <Input onChange={(event) => setCapabilityCategory(event.target.value)} value={capabilityCategory} />
        </Field>
        <Field label="标签">
          <Input onChange={(event) => setTagsText(event.target.value)} value={tagsText} />
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="版本号">
          <Input onChange={(event) => setVersion(event.target.value)} value={version} />
        </Field>
        <Field label="版本显示名称">
          <Input onChange={(event) => setVersionDisplayName(event.target.value)} value={versionDisplayName} />
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Field label="执行引擎">
          <Select onValueChange={setEngine} value={engine}>
            <SelectTrigger>
              <SelectValue placeholder="选择引擎" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="evalscope">evalscope</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="执行模式">
          <Select onValueChange={setExecutionMode} value={executionMode}>
            <SelectTrigger>
              <SelectValue placeholder="选择模式" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="builtin">builtin</SelectItem>
              <SelectItem value="dataset">dataset</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label="样本量">
          <Input onChange={(event) => setSampleCount(event.target.value)} placeholder="可选" value={sampleCount} />
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="EvalScope Benchmark Name">
          <Input
            onChange={(event) => setEngineBenchmarkName(event.target.value)}
            placeholder="例如 mmlu / gsm8k / ceval"
            value={engineBenchmarkName}
          />
        </Field>
        <Field label="默认 Judge Policy">
          <Select onValueChange={setJudgePolicyId} value={judgePolicyId}>
            <SelectTrigger>
              <SelectValue placeholder="不绑定" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>不绑定默认策略</SelectItem>
              {catalog.judge_policies.map((policy) => (
                <SelectItem key={policy.id} value={policy.id}>
                  {policy.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="模板版本">
          <Select onValueChange={setTemplateVersionId} value={templateVersionId}>
            <SelectTrigger>
              <SelectValue placeholder="不绑定" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>不绑定模板版本</SelectItem>
              {templateOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="Engine 配置 (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setEngineConfigText(event.target.value)}
            value={engineConfigText}
          />
        </Field>
        <Field label="Scoring 配置 (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setScoringConfigText(event.target.value)}
            value={scoringConfigText}
          />
        </Field>
        <Field label="输入 Schema (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setInputSchemaText(event.target.value)}
            value={inputSchemaText}
          />
        </Field>
        <Field label="输出 Schema (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setOutputSchemaText(event.target.value)}
            value={outputSchemaText}
          />
        </Field>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button disabled={submitting} type="submit">
          {submitting ? `${mode === "edit" ? "保存" : "创建"}中...` : mode === "edit" ? "保存评测类型" : "创建评测类型"}
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-sm text-slate-200">{label}</Label>
      {children}
    </div>
  );
}

function normalizeName(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function normalizeOptional(value: string) {
  const normalized = value.trim();
  return normalized || undefined;
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseJsonObject(value: string, label: string) {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} 必须是 JSON 对象。`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof Error && error.message.includes(label)) {
      throw error;
    }
    throw new Error(`${label} 不是合法 JSON。`);
  }
}

function parseOptionalInteger(value: string, label: string) {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0 || !Number.isInteger(parsed)) {
    throw new Error(`${label} 必须是大于等于 0 的整数。`);
  }
  return parsed;
}

function getManagedSpecVersion(spec?: EvalSpecSummaryV2): EvalSpecVersionSummaryV2 | undefined {
  return (
    spec?.versions.find((version) => version.is_recommended && version.enabled) ??
    spec?.versions.find((version) => version.enabled) ??
    spec?.versions[0]
  );
}
