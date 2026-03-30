"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { createEvalJob } from "@/features/eval/api";
import type {
  BenchmarkDefinitionSummary,
  BenchmarkVersionSummary,
  EvalJobCreateInput,
  RegistryModelSummary
} from "@/types/api";

const PREFERRED_PROVIDER_NAME = "ai.zhanghd.com";
const PREFERRED_MODEL_NAME = "GPT-5.4";

const evalJobSchema = z.object({
  benchmark_name: z.string().min(1, "请选择 Benchmark"),
  benchmark_version_id: z.string().min(1, "请选择 Benchmark Version"),
  model_id: z.string().min(1, "请选择评测模型"),
  judge_model_id: z.string().optional()
});

type EvalJobFormValues = z.infer<typeof evalJobSchema>;

export function EvalJobCreateForm({
  benchmarks,
  models,
}: {
  benchmarks: BenchmarkDefinitionSummary[];
  models: RegistryModelSummary[];
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const availableBenchmarks = useMemo(
    () =>
      benchmarks.filter(
        (benchmark) =>
          benchmark.runtime_available && benchmark.versions.some((version) => version.enabled)
      ),
    [benchmarks]
  );
  const activeModels = useMemo(
    () => models.filter((model) => model.status === "active" && Boolean(model.provider_id)),
    [models]
  );
  const defaultBenchmark = availableBenchmarks[0] ?? benchmarks[0] ?? null;
  const defaultVersion = pickDefaultVersion(defaultBenchmark);
  const defaultModel = pickDefaultModel(activeModels);

  const form = useForm<EvalJobFormValues>({
    resolver: zodResolver(evalJobSchema),
    defaultValues: {
      benchmark_name: defaultBenchmark?.name ?? "",
      benchmark_version_id: defaultVersion?.id ?? "",
      model_id: defaultModel?.id ?? "",
      judge_model_id: defaultModel?.id ?? ""
    }
  });

  const selectedBenchmarkName = form.watch("benchmark_name");
  const selectedVersionId = form.watch("benchmark_version_id");
  const selectedModelId = form.watch("model_id");
  const selectedJudgeModelId = form.watch("judge_model_id");
  const selectedBenchmark =
    availableBenchmarks.find((benchmark) => benchmark.name === selectedBenchmarkName) ??
    defaultBenchmark;
  const requiresJudgeModel = selectedBenchmark?.requires_judge_model ?? false;
  const versionOptions = useMemo(
    () => selectedBenchmark?.versions.filter((version) => version.enabled) ?? [],
    [selectedBenchmark]
  );
  const selectedVersion =
    versionOptions.find((version) => version.id === selectedVersionId) ??
    versionOptions[0] ??
    null;
  const selectedModel = activeModels.find((model) => model.id === selectedModelId) ?? defaultModel ?? null;
  const selectedJudgeModel =
    activeModels.find((model) => model.id === selectedJudgeModelId) ??
    defaultModel ??
    null;

  useEffect(() => {
    if (!selectedBenchmark) {
      return;
    }
    const currentVersionId = form.getValues("benchmark_version_id");
    const hasCurrentVersion = selectedBenchmark.versions.some(
      (version) => version.enabled && version.id === currentVersionId
    );
    if (hasCurrentVersion) {
      return;
    }

    const nextVersion = pickDefaultVersion(selectedBenchmark);
    form.setValue("benchmark_version_id", nextVersion?.id ?? "", {
      shouldDirty: true,
      shouldValidate: true
    });
  }, [form, selectedBenchmark]);

  useEffect(() => {
    if (!selectedModel && defaultModel) {
      form.setValue("model_id", defaultModel.id, { shouldValidate: true });
    }
    if (!requiresJudgeModel) {
      form.clearErrors("judge_model_id");
      return;
    }
    if (!selectedJudgeModel && defaultModel) {
      form.setValue("judge_model_id", defaultModel.id, { shouldValidate: true });
    }
  }, [defaultModel, form, requiresJudgeModel, selectedJudgeModel, selectedModel]);

  async function handleSubmit(values: EvalJobFormValues) {
    const benchmark =
      availableBenchmarks.find((item) => item.name === values.benchmark_name) ?? null;
    const version =
      benchmark?.versions.find((item) => item.id === values.benchmark_version_id) ?? null;
    const evalModel = activeModels.find((item) => item.id === values.model_id) ?? null;
    const judgeModel =
      benchmark?.requires_judge_model
        ? activeModels.find((item) => item.id === values.judge_model_id) ?? null
        : null;

    if (!benchmark || !version || !evalModel) {
      toast.error("评测任务配置不完整，请重新选择 Benchmark、Version 和模型。");
      return;
    }

    if (benchmark.requires_judge_model && !judgeModel) {
      form.setError("judge_model_id", {
        type: "manual",
        message: "请选择 Judge 模型"
      });
      return;
    }
    form.clearErrors("judge_model_id");

    const payload: EvalJobCreateInput = {
      name: buildJobName(benchmark, version, evalModel, judgeModel),
      description: `${benchmark.display_name} / ${version.display_name}`,
      benchmark_name: benchmark.name,
      benchmark_version_id: version.id,
      benchmark_config: null,
      model_id: evalModel.id,
      model_name: evalModel.name,
      model_source: "model-square",
      access_source: "nta",
      dataset_source_type: "benchmark-version",
      dataset_name: version.display_name,
      dataset_source_uri: `benchmark://${benchmark.name}/versions/${version.id}`,
      inference_mode: "batch",
      task_type: "single-turn",
      eval_mode: "infer-auto",
      eval_method: benchmark.default_eval_method,
      judge_model_id: judgeModel?.id ?? null,
      judge_model_name: judgeModel?.name ?? null,
      judge_prompt: null,
      rubric: null
    };

    setSubmitting(true);
    try {
      const job = await createEvalJob(payload);
      toast.success("评测任务已创建");
      router.push(`/model/eval-detail/${job.id}`);
      router.refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "创建评测任务失败";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const benchmarkError = form.formState.errors.benchmark_name?.message;
  const versionError = form.formState.errors.benchmark_version_id?.message;
  const modelError = form.formState.errors.model_id?.message;
  const judgeModelError = form.formState.errors.judge_model_id?.message;
  const formDisabled =
    submitting || !defaultBenchmark || !defaultVersion || activeModels.length === 0;

  return (
    <div className="flex w-full max-w-4xl flex-col gap-5">
      {!availableBenchmarks.length ? (
        <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-8 text-sm text-slate-400">
          当前还没有可用的 Benchmark Version。请先到评测管理页为该类型登记数据集 Version。
        </div>
      ) : null}

      {!activeModels.length ? (
        <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-8 text-sm text-slate-400">
          当前项目没有可用模型。请先在模型接入中同步可用模型。
        </div>
      ) : null}

      <form className="space-y-6" onSubmit={form.handleSubmit(handleSubmit)}>
        <div className="grid gap-6 lg:grid-cols-2">
          <FieldBlock
            description={selectedBenchmark?.description ?? "选择一个 Benchmark。"}
            error={benchmarkError}
            label="Benchmark"
          >
            <Select
              disabled={formDisabled}
              onValueChange={(value) =>
                form.setValue("benchmark_name", value, { shouldValidate: true })
              }
              value={selectedBenchmarkName}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择 Benchmark" />
              </SelectTrigger>
              <SelectContent>
                {availableBenchmarks.map((benchmark) => (
                  <SelectItem key={benchmark.name} value={benchmark.name}>
                    {benchmark.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldBlock>

          <FieldBlock
            error={versionError}
            label="Benchmark Version"
          >
            <Select
              disabled={formDisabled || versionOptions.length === 0}
              onValueChange={(value) =>
                form.setValue("benchmark_version_id", value, { shouldValidate: true })
              }
              value={selectedVersionId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择 Benchmark Version" />
              </SelectTrigger>
              <SelectContent>
                {versionOptions.map((version) => (
                  <SelectItem key={version.id} value={version.id}>
                    {formatVersionOption(version)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldBlock>

          <FieldBlock
            description={selectedModel ? describeModel(selectedModel) : "选择要被评测的模型。"}
            error={modelError}
            label="评测模型"
          >
            <Select
              disabled={formDisabled}
              onValueChange={(value) => form.setValue("model_id", value, { shouldValidate: true })}
              value={selectedModelId}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择评测模型" />
              </SelectTrigger>
              <SelectContent>
                {activeModels.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {formatModelOption(model)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FieldBlock>

          {requiresJudgeModel ? (
            <FieldBlock
              description={
                selectedJudgeModel
                  ? describeModel(selectedJudgeModel)
                  : "选择作为裁判员的评测模型。"
              }
              error={judgeModelError}
              label="Judge 模型"
            >
              <Select
                disabled={formDisabled}
                onValueChange={(value) =>
                  form.setValue("judge_model_id", value, { shouldValidate: true })
                }
                value={selectedJudgeModelId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择 Judge 模型" />
                </SelectTrigger>
                <SelectContent>
                  {activeModels.map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {formatModelOption(model)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FieldBlock>
          ) : null}
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <SummaryCard
            label="将要创建的任务"
            value={
              selectedBenchmark &&
              selectedVersion &&
              selectedModel &&
              (!requiresJudgeModel || selectedJudgeModel)
                ? buildJobName(
                    selectedBenchmark,
                    selectedVersion,
                    selectedModel,
                    requiresJudgeModel ? selectedJudgeModel : null
                  )
                : "--"
            }
          />
          <SummaryCard
            label="执行配置"
            value={
              selectedBenchmark
                ? `${selectedBenchmark.default_eval_method} / batch / infer-auto`
                : "--"
            }
          />
        </div>

        <div className="flex justify-end">
          <Button disabled={formDisabled} type="submit">
            {submitting ? "创建中..." : "创建评测任务"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function FieldBlock({
  label,
  description,
  error,
  children
}: {
  label: string;
  description?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium text-slate-200">{label}</Label>
      {children}
      {error || description ? (
        <p className="text-xs leading-5 text-slate-500">{error ?? description}</p>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 break-all text-sm text-slate-100">{value}</div>
    </div>
  );
}

function pickDefaultVersion(
  benchmark: BenchmarkDefinitionSummary | null | undefined
): BenchmarkVersionSummary | null {
  if (!benchmark) {
    return null;
  }
  return benchmark.versions.find((version) => version.enabled) ?? benchmark.versions[0] ?? null;
}

function pickDefaultModel(models: RegistryModelSummary[]): RegistryModelSummary | null {
  return (
    models.find(
      (model) =>
        model.name === PREFERRED_MODEL_NAME && model.provider_name === PREFERRED_PROVIDER_NAME
    ) ??
    models.find((model) => model.name === PREFERRED_MODEL_NAME) ??
    models[0] ??
    null
  );
}

function formatModelOption(model: RegistryModelSummary): string {
  const provider = model.provider_name?.trim() || "Unknown Provider";
  return `${model.name} · ${provider}`;
}

function describeModel(model: RegistryModelSummary): string {
  const provider = model.provider_name?.trim() || "Unknown Provider";
  const code = model.model_code?.trim();
  return code ? `${provider} / ${code}` : provider;
}

function formatVersionOption(version: BenchmarkVersionSummary): string {
  if (version.sample_count > 0) {
    return `${version.display_name} · ${version.sample_count} 条`;
  }
  return version.display_name;
}

function buildJobName(
  benchmark: BenchmarkDefinitionSummary,
  version: BenchmarkVersionSummary,
  evalModel: RegistryModelSummary,
  judgeModel?: RegistryModelSummary | null
): string {
  if (!judgeModel) {
    return `${benchmark.display_name} · ${version.display_name} · ${evalModel.name}`;
  }
  return `${benchmark.display_name} · ${version.display_name} · ${evalModel.name} vs ${judgeModel.name}`;
}
