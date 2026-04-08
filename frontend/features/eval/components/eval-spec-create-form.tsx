"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
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
import type {
  EvaluationCatalogResponseV2,
  EvalSpecDatasetFileSummaryV2,
  EvalSpecSummaryV2,
  EvalSpecVersionSummaryV2
} from "@/types/api";

const NONE_VALUE = "__none__";

type EvalSpecFormProps = {
  catalog: EvaluationCatalogResponseV2;
  initialValue?: EvalSpecSummaryV2;
  mode?: "create" | "edit";
};

type DatasetFileState = {
  id: string;
  fileKey: string;
  displayName: string;
  role: string;
  fileName: string;
  format: string;
  sourceUri: string;
  isRequired: boolean;
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
  const [datasetFiles, setDatasetFiles] = React.useState<DatasetFileState[]>(() =>
    getInitialDatasetFiles(managedVersion)
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
      const datasetFilePayload = datasetFiles
        .map((item, index) => serializeDatasetFile(item, index))
        .filter((item): item is NonNullable<typeof item> => item != null);
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
            is_recommended: true,
            dataset_files: datasetFilePayload
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
            is_recommended: true,
            dataset_files: datasetFilePayload
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

  function handleAddDatasetFile() {
    setDatasetFiles((current) => [...current, createEmptyDatasetFile()]);
  }

  function updateDatasetFile(fileId: string, patch: Partial<DatasetFileState>) {
    setDatasetFiles((current) =>
      current.map((item) => (item.id === fileId ? { ...item, ...patch } : item))
    );
  }

  function removeDatasetFile(fileId: string) {
    setDatasetFiles((current) => current.filter((item) => item.id !== fileId));
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

      <div className="space-y-4 rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium text-slate-100">版本数据集文件</div>
            <div className="mt-1 text-sm text-slate-400">
              每个评测版本由一个或多个数据集文件组成。内置 EvalScope benchmark 可留空，系统会自动生成内置数据集引用。
            </div>
          </div>
          <Button onClick={handleAddDatasetFile} type="button" variant="outline">
            <Plus className="mr-2 h-4 w-4" />
            添加文件
          </Button>
        </div>

        {!datasetFiles.length ? (
          <div className="rounded-xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
            当前版本还没有显式的数据集文件。若是平台内置 benchmark，可以直接保存；若依赖自定义数据，请添加文件来源。
          </div>
        ) : null}

        <div className="space-y-4">
          {datasetFiles.map((datasetFile, index) => (
            <div
              className="rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] p-4"
              key={datasetFile.id}
            >
              <div className="grid gap-4 md:grid-cols-[1fr_1fr_140px_auto]">
                <Field label={`文件 Key #${index + 1}`}>
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { fileKey: event.target.value })}
                    placeholder="questions"
                    value={datasetFile.fileKey}
                  />
                </Field>
                <Field label="显示名称">
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { displayName: event.target.value })}
                    placeholder="题目集"
                    value={datasetFile.displayName}
                  />
                </Field>
                <Field label="角色">
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { role: event.target.value })}
                    placeholder="dataset"
                    value={datasetFile.role}
                  />
                </Field>
                <div className="flex items-end">
                  <Button onClick={() => removeDatasetFile(datasetFile.id)} type="button" variant="ghost">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <Field label="文件名">
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { fileName: event.target.value })}
                    placeholder="mmlu.jsonl"
                    value={datasetFile.fileName}
                  />
                </Field>
                <Field label="格式">
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { format: event.target.value })}
                    placeholder="jsonl / parquet / csv"
                    value={datasetFile.format}
                  />
                </Field>
                <Field label="是否必需">
                  <label className="flex h-10 items-center gap-2 rounded-md border border-slate-800/80 px-3 text-sm text-slate-300">
                    <input
                      checked={datasetFile.isRequired}
                      className="h-4 w-4"
                      onChange={(event) => updateDatasetFile(datasetFile.id, { isRequired: event.target.checked })}
                      type="checkbox"
                    />
                    运行前强校验
                  </label>
                </Field>
              </div>

              <div className="mt-4">
                <Field label="来源 URI">
                  <Input
                    onChange={(event) => updateDatasetFile(datasetFile.id, { sourceUri: event.target.value })}
                    placeholder="支持 s3://、file://、绝对路径、http(s):// 或 evalscope://"
                    value={datasetFile.sourceUri}
                  />
                </Field>
              </div>
            </div>
          ))}
        </div>
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

function getInitialDatasetFiles(version?: EvalSpecVersionSummaryV2): DatasetFileState[] {
  return (version?.dataset_files ?? []).map((item) => datasetFileSummaryToState(item));
}

function datasetFileSummaryToState(item: EvalSpecDatasetFileSummaryV2): DatasetFileState {
  return {
    id: crypto.randomUUID(),
    fileKey: item.file_key,
    displayName: item.display_name,
    role: item.role,
    fileName: item.file_name ?? "",
    format: item.format ?? "",
    sourceUri: item.source_uri ?? "",
    isRequired: item.is_required
  };
}

function createEmptyDatasetFile(): DatasetFileState {
  return {
    id: crypto.randomUUID(),
    fileKey: "",
    displayName: "",
    role: "dataset",
    fileName: "",
    format: "",
    sourceUri: "",
    isRequired: true
  };
}

function serializeDatasetFile(item: DatasetFileState, index: number) {
  const fileKey = item.fileKey.trim();
  const displayName = item.displayName.trim();
  const sourceUri = item.sourceUri.trim();
  if (!fileKey && !displayName && !sourceUri) {
    return null;
  }
  if (!fileKey || !displayName) {
    throw new Error("数据集文件至少需要 file_key 和显示名称。");
  }
  return {
    file_key: fileKey,
    display_name: displayName,
    role: item.role.trim() || "dataset",
    position: index,
    file_name: normalizeOptional(item.fileName),
    format: normalizeOptional(item.format),
    source_uri: normalizeOptional(sourceUri),
    is_required: item.isRequired
  };
}
