"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { createBenchmarkEvaluationRun } from "@/features/eval/api";
import type {
  BenchmarkDefinitionSummary,
  BenchmarkVersionSummary,
  RegistryModelSummary
} from "@/types/api";

const PREFERRED_PROVIDER_NAME = "ai.zhanghd.com";
const PREFERRED_MODEL_NAME = "GPT-5.4";

type BenchmarkMode = "builtin" | "custom";

export function BenchmarkEvaluationRunCreateForm({
  benchmarks,
  models,
}: {
  benchmarks: BenchmarkDefinitionSummary[];
  models: RegistryModelSummary[];
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const builtinBenchmarks = useMemo(
    () => benchmarks.filter((benchmark) => benchmark.source_type === "builtin" && hasEnabledVersion(benchmark)),
    [benchmarks]
  );
  const customBenchmarks = useMemo(
    () => benchmarks.filter((benchmark) => benchmark.source_type !== "builtin" && hasEnabledVersion(benchmark)),
    [benchmarks]
  );
  const activeModels = useMemo(
    () => models.filter((model) => model.status === "active" && Boolean(model.provider_id)),
    [models]
  );

  const defaultMode: BenchmarkMode = builtinBenchmarks.length ? "builtin" : "custom";
  const [mode, setMode] = useState<BenchmarkMode>(defaultMode);
  const [benchmarkName, setBenchmarkName] = useState<string>(
    pickInitialBenchmarkName(defaultMode, builtinBenchmarks, customBenchmarks)
  );
  const [versionId, setVersionId] = useState<string>(
    pickInitialVersionId(defaultMode, benchmarkName, builtinBenchmarks, customBenchmarks)
  );
  const [modelId, setModelId] = useState<string>(pickDefaultModel(activeModels)?.id ?? "");
  const benchmarkOptions = mode === "builtin" ? builtinBenchmarks : customBenchmarks;

  useEffect(() => {
    if (!benchmarkOptions.length) {
      setBenchmarkName("");
      setVersionId("");
      return;
    }
    if (benchmarkOptions.some((benchmark) => benchmark.name === benchmarkName)) {
      return;
    }
    setBenchmarkName(benchmarkOptions[0]?.name ?? "");
  }, [benchmarkName, benchmarkOptions]);

  useEffect(() => {
    const selectedOption =
      benchmarkOptions.find((benchmark) => benchmark.name === benchmarkName) ?? benchmarkOptions[0] ?? null;
    const enabledVersions = selectedOption?.versions.filter((version) => version.enabled) ?? [];

    if (!enabledVersions.length) {
      if (versionId) {
        setVersionId("");
      }
      return;
    }

    if (enabledVersions.some((version) => version.id === versionId)) {
      return;
    }

    const nextVersion = enabledVersions[0]?.id ?? "";
    if (nextVersion !== versionId) {
      setVersionId(nextVersion);
      return;
    }
  }, [benchmarkName, benchmarkOptions, versionId]);

  useEffect(() => {
    if (!modelId && activeModels.length) {
      setModelId(pickDefaultModel(activeModels)?.id ?? "");
    }
  }, [activeModels, modelId]);

  const selectedBenchmark =
    benchmarkOptions.find((benchmark) => benchmark.name === benchmarkName) ??
    benchmarkOptions[0] ??
    null;
  const versionOptions = selectedBenchmark?.versions.filter((version) => version.enabled) ?? [];
  const selectedVersion =
    versionOptions.find((version) => version.id === versionId) ?? versionOptions[0] ?? null;
  const selectedModel =
    activeModels.find((model) => model.id === modelId) ?? pickDefaultModel(activeModels) ?? null;

  const formDisabled =
    submitting || activeModels.length === 0 || (builtinBenchmarks.length === 0 && customBenchmarks.length === 0);

  async function handleSubmit() {
    if (!selectedBenchmark || !selectedVersion || !selectedModel) {
      toast.error("请先选择评测方式、Benchmark、版本和模型。");
      return;
    }

    setSubmitting(true);
    try {
      const run = await createBenchmarkEvaluationRun({
        name: buildRunName(selectedBenchmark, selectedVersion, selectedModel),
        description: buildRunDescription(selectedBenchmark, selectedVersion),
        benchmark_name: selectedBenchmark.name,
        benchmark_version_id: selectedVersion.id,
        model_id: selectedModel.id,
      });
      toast.success("评测任务已创建");
      router.push(`/model/eval-detail/${run.id}`);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建评测任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-6">
      {builtinBenchmarks.length === 0 && customBenchmarks.length === 0 ? (
        <EmptyHint>
          当前项目没有可用的 Benchmark。请先创建一个自定义 Benchmark，或等待基线 Benchmark 就绪。
        </EmptyHint>
      ) : null}

      {activeModels.length === 0 ? (
        <EmptyHint>当前项目没有可用模型。请先在模型接入中同步可用模型。</EmptyHint>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <ModeCard
          active={mode === "builtin"}
          description="像百炼一样选择平台预置的基线 Benchmark，直接发起标准能力评测。"
          disabled={!builtinBenchmarks.length}
          onClick={() => setMode("builtin")}
          title="基线评测"
        />
        <ModeCard
          active={mode === "custom"}
          description="选择自定义 Benchmark 与对应 Version，按绑定的评测维度运行。"
          disabled={!customBenchmarks.length}
          onClick={() => setMode("custom")}
          title="自定义评测"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <FieldBlock
          description={mode === "builtin" ? "选择一个预置基线 Benchmark。" : "选择一个自定义 Benchmark。"}
          label="Benchmark"
        >
          <Select disabled={formDisabled} onValueChange={setBenchmarkName} value={benchmarkName}>
            <SelectTrigger>
              <SelectValue placeholder="选择 Benchmark" />
            </SelectTrigger>
            <SelectContent>
              {benchmarkOptions.map((benchmark) => (
                <SelectItem key={benchmark.name} value={benchmark.name}>
                  {benchmark.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock
          description={mode === "builtin" ? "默认展示该 Benchmark 当前开放的版本。" : "Version 对应这个 Benchmark 的某个数据集版本。"}
          label="Benchmark Version"
        >
          <Select
            disabled={formDisabled || versionOptions.length === 0}
            onValueChange={setVersionId}
            value={versionId}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择 Benchmark Version" />
            </SelectTrigger>
            <SelectContent>
              {versionOptions.map((version) => (
                <SelectItem key={version.id} value={version.id}>
                  {formatVersionLabel(version)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock
          description="任务执行时会冻结当前模型绑定快照。"
          label="评测模型"
        >
          <Select disabled={formDisabled} onValueChange={setModelId} value={modelId}>
            <SelectTrigger>
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              {activeModels.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  {model.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock
          description={
            mode === "builtin"
              ? "基线 Benchmark 直接使用平台预置规则。"
              : "自定义 Benchmark 会继承所绑定评测维度的评分模板与裁判配置。"
          }
          label="评测维度"
        >
          <div className="rounded-2xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] px-4 py-3 text-sm text-slate-300">
            {selectedBenchmark?.eval_template_name
              ? `${selectedBenchmark.eval_template_name}${selectedBenchmark.eval_template_version != null ? ` · v${selectedBenchmark.eval_template_version}` : ""}`
              : mode === "builtin"
                ? "平台预置"
                : "未绑定"}
          </div>
        </FieldBlock>
      </div>

      <div className="rounded-2xl border border-slate-800/80 bg-[rgba(12,18,26,0.72)] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Execution Plan</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">
              {selectedBenchmark?.display_name ?? "未选择 Benchmark"}
            </div>
            <div className="mt-1 text-sm text-slate-400">
              {selectedBenchmark?.description || "当前 Benchmark 没有额外描述。"}
            </div>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] px-4 py-3 text-right">
            <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Model Binding</div>
            <div className="mt-2 text-sm font-medium text-slate-100">
              {selectedModel?.name ?? "未选择模型"}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {mode === "builtin" ? "Benchmark 类型 · 基线评测" : "Benchmark 类型 · 自定义评测"}
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <InfoCard
            label="版本信息"
            value={
              selectedVersion
                ? `${selectedVersion.display_name}${selectedVersion.sample_count > 0 ? ` · ${selectedVersion.sample_count} samples` : ""}`
                : "未选择版本"
            }
          />
          <InfoCard
            label="评测维度"
            value={
              selectedBenchmark?.eval_template_name
                ? `${selectedBenchmark.eval_template_name}${selectedBenchmark.eval_template_type ? ` · ${selectedBenchmark.eval_template_type}` : ""}`
                : mode === "builtin"
                  ? "平台预置"
                  : "未绑定"
            }
          />
        </div>
      </div>

      <div className="flex justify-end">
        <Button disabled={formDisabled || !selectedVersion || !selectedModel} onClick={() => void handleSubmit()}>
          {submitting ? "创建中..." : "创建评测任务"}
        </Button>
      </div>
    </div>
  );
}

function hasEnabledVersion(benchmark: BenchmarkDefinitionSummary) {
  return benchmark.versions.some((version) => version.enabled);
}

function pickInitialBenchmarkName(
  mode: BenchmarkMode,
  builtinBenchmarks: BenchmarkDefinitionSummary[],
  customBenchmarks: BenchmarkDefinitionSummary[]
) {
  return (mode === "builtin" ? builtinBenchmarks : customBenchmarks)[0]?.name ?? "";
}

function pickInitialVersionId(
  mode: BenchmarkMode,
  benchmarkName: string,
  builtinBenchmarks: BenchmarkDefinitionSummary[],
  customBenchmarks: BenchmarkDefinitionSummary[]
) {
  const options = mode === "builtin" ? builtinBenchmarks : customBenchmarks;
  const selected = options.find((benchmark) => benchmark.name === benchmarkName) ?? options[0];
  return selected?.versions.find((version) => version.enabled)?.id ?? "";
}

function pickDefaultModel(models: RegistryModelSummary[]) {
  return (
    models.find(
      (model) =>
        model.name === PREFERRED_MODEL_NAME &&
        (model.provider_name ?? "").toLowerCase().includes(PREFERRED_PROVIDER_NAME)
    ) ??
    models.find((model) => model.name === PREFERRED_MODEL_NAME) ??
    models[0] ??
    null
  );
}

function buildRunName(
  benchmark: BenchmarkDefinitionSummary,
  version: BenchmarkVersionSummary,
  model: RegistryModelSummary
) {
  return `${benchmark.display_name} · ${version.display_name} · ${model.name}`;
}

function buildRunDescription(
  benchmark: BenchmarkDefinitionSummary,
  version: BenchmarkVersionSummary
) {
  return `${benchmark.display_name} / ${version.display_name}`;
}

function formatVersionLabel(version: BenchmarkVersionSummary) {
  const parts = [version.display_name];
  if (version.sample_count > 0) {
    parts.push(`${version.sample_count} samples`);
  }
  return parts.join(" · ");
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-8 text-sm text-slate-400">
      {children}
    </div>
  );
}

function ModeCard({
  active,
  description,
  disabled,
  onClick,
  title
}: {
  active: boolean;
  description: string;
  disabled: boolean;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      className={`rounded-2xl border px-4 py-4 text-left transition-colors ${
        active
          ? "border-[#8fffcf]/60 bg-[rgba(16,30,34,0.84)]"
          : "border-slate-800/80 bg-[rgba(10,15,22,0.72)]"
      } ${disabled ? "cursor-not-allowed opacity-50" : "hover:border-slate-700 hover:bg-[rgba(14,20,29,0.76)]"}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <div className="text-sm font-semibold text-slate-100">{title}</div>
      <div className="mt-2 text-sm leading-6 text-slate-400">{description}</div>
    </button>
  );
}

function FieldBlock({
  children,
  description,
  label
}: {
  children: React.ReactNode;
  description?: string;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
      {description ? <p className="text-xs leading-5 text-slate-500">{description}</p> : null}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm text-slate-100">{value}</div>
    </div>
  );
}
