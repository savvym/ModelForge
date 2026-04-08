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
import { createEvaluationRun } from "@/features/eval/api";
import type {
  EvalSpecSummaryV2,
  EvalSpecVersionSummaryV2,
  EvalSuiteSummaryV2,
  EvalSuiteVersionSummaryV2,
  EvaluationCatalogResponseV2,
  EvaluationRunCreateInputV2,
  JudgePolicySummaryV2,
  RegistryModelSummary
} from "@/types/api";

const DEFAULT_POLICY_VALUE = "__default__";
const PREFERRED_PROVIDER_NAME = "ai.zhanghd.com";
const PREFERRED_MODEL_NAME = "GPT-5.4";

type TargetKind = "suite" | "spec";

export function EvaluationRunCreateForm({
  catalog,
  models,
}: {
  catalog: EvaluationCatalogResponseV2;
  models: RegistryModelSummary[];
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  const suiteOptions = useMemo(
    () =>
      catalog.suites.filter((suite) =>
        suite.versions.some((version) => version.enabled && version.items.some((item) => item.enabled))
      ),
    [catalog.suites]
  );
  const specOptions = useMemo(
    () => catalog.specs.filter((spec) => spec.versions.some((version) => version.enabled)),
    [catalog.specs]
  );
  const activeModels = useMemo(
    () => models.filter((model) => model.status === "active" && Boolean(model.provider_id)),
    [models]
  );

  const defaultKind: TargetKind = suiteOptions.length ? "suite" : "spec";
  const [targetKind, setTargetKind] = useState<TargetKind>(defaultKind);
  const [targetName, setTargetName] = useState<string>(pickInitialTargetName(defaultKind, suiteOptions, specOptions));
  const [targetVersion, setTargetVersion] = useState<string>(
    pickInitialVersionValue(defaultKind, targetName, suiteOptions, specOptions)
  );
  const [modelId, setModelId] = useState<string>(pickDefaultModel(activeModels)?.id ?? "");
  const [judgePolicyId, setJudgePolicyId] = useState<string>(DEFAULT_POLICY_VALUE);

  useEffect(() => {
    const nextName = pickInitialTargetName(targetKind, suiteOptions, specOptions);
    if (!nextName) {
      setTargetName("");
      setTargetVersion("");
      return;
    }
    if (
      targetKind === "suite"
        ? suiteOptions.some((suite) => suite.name === targetName)
        : specOptions.some((spec) => spec.name === targetName)
    ) {
      return;
    }
    setTargetName(nextName);
  }, [specOptions, suiteOptions, targetKind, targetName]);

  useEffect(() => {
    const nextVersion = pickInitialVersionValue(targetKind, targetName, suiteOptions, specOptions);
    if (nextVersion && nextVersion !== targetVersion) {
      setTargetVersion(nextVersion);
      return;
    }
    if (!nextVersion) {
      setTargetVersion("");
    }
  }, [specOptions, suiteOptions, targetKind, targetName, targetVersion]);

  useEffect(() => {
    if (!modelId && activeModels.length) {
      setModelId(pickDefaultModel(activeModels)?.id ?? "");
    }
  }, [activeModels, modelId]);

  const selectedSuite =
    targetKind === "suite" ? suiteOptions.find((suite) => suite.name === targetName) ?? null : null;
  const selectedSpec =
    targetKind === "spec" ? specOptions.find((spec) => spec.name === targetName) ?? null : null;
  const versionOptions =
    targetKind === "suite" ? selectedSuite?.versions.filter((version) => version.enabled) ?? [] : selectedSpec?.versions.filter((version) => version.enabled) ?? [];
  const selectedVersion =
    versionOptions.find((version) => version.version === targetVersion) ?? versionOptions[0] ?? null;
  const selectedModel = activeModels.find((model) => model.id === modelId) ?? pickDefaultModel(activeModels) ?? null;
  const selectedJudgePolicy =
    catalog.judge_policies.find((policy) => policy.id === judgePolicyId) ?? null;

  const formDisabled =
    submitting ||
    (!suiteOptions.length && !specOptions.length) ||
    activeModels.length === 0;

  async function handleSubmit() {
    if (!targetName || !selectedVersion || !selectedModel) {
      toast.error("请先选择评测对象、版本和模型。");
      return;
    }

    const payload: EvaluationRunCreateInputV2 = {
      name: buildRunName({
        targetKind,
        suite: selectedSuite,
        spec: selectedSpec,
        version: selectedVersion,
        model: selectedModel
      }),
      description: buildRunDescription({
        targetKind,
        suite: selectedSuite,
        spec: selectedSpec,
        version: selectedVersion
      }),
      target: {
        kind: targetKind,
        name: targetName,
        version: selectedVersion.version
      },
      model_id: selectedModel.id,
      judge_policy_id: judgePolicyId === DEFAULT_POLICY_VALUE ? undefined : judgePolicyId,
      overrides: {}
    };

    setSubmitting(true);
    try {
      const run = await createEvaluationRun(payload);
      toast.success("评测任务已创建");
      router.push(`/model/eval-detail/${run.id}`);
      router.refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "创建评测任务失败";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex w-full max-w-4xl flex-col gap-6">
      {!suiteOptions.length && !specOptions.length ? (
        <EmptyHint>
          当前没有可用的评测目录。请先在评测管理中配置 Eval Spec 或 Eval Suite。
        </EmptyHint>
      ) : null}

      {!activeModels.length ? (
        <EmptyHint>当前项目没有可用模型。请先在模型接入中同步可用模型。</EmptyHint>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <ModeCard
          active={targetKind === "suite"}
          description="通过预置评测套件并发跑多个内置基准，适合模型基线评测。"
          disabled={!suiteOptions.length}
          onClick={() => setTargetKind("suite")}
          title="基线评测"
        />
        <ModeCard
          active={targetKind === "spec"}
          description="直接跑单个评测类型和指定版本，适合定向验证某项能力。"
          disabled={!specOptions.length}
          onClick={() => setTargetKind("spec")}
          title="单项评测"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <FieldBlock
          description={targetKind === "suite" ? "选择一个评测套件。" : "选择一个评测类型。"}
          label={targetKind === "suite" ? "评测套件" : "评测类型"}
        >
          <Select disabled={formDisabled} onValueChange={setTargetName} value={targetName}>
            <SelectTrigger>
              <SelectValue placeholder={targetKind === "suite" ? "选择评测套件" : "选择评测类型"} />
            </SelectTrigger>
            <SelectContent>
              {(targetKind === "suite" ? suiteOptions : specOptions).map((option) => (
                <SelectItem key={option.id} value={option.name}>
                  {option.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock label="版本">
          <Select
            disabled={formDisabled || versionOptions.length === 0}
            onValueChange={setTargetVersion}
            value={targetVersion}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择版本" />
            </SelectTrigger>
            <SelectContent>
              {versionOptions.map((version) => (
                <SelectItem key={version.id} value={version.version}>
                  {formatVersionLabel(version)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock
          description="任务执行时会把 Provider 绑定快照冻结到执行计划。"
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
          description="内置基线评测通常不需要额外 Judge Policy；自定义评测时可在后续版本启用。"
          label="Judge Policy"
        >
          <Select
            disabled={formDisabled}
            onValueChange={setJudgePolicyId}
            value={judgePolicyId}
          >
            <SelectTrigger>
              <SelectValue placeholder="使用默认策略" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DEFAULT_POLICY_VALUE}>使用默认策略</SelectItem>
              {catalog.judge_policies.map((policy) => (
                <SelectItem key={policy.id} value={policy.id}>
                  {policy.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>
      </div>

      <div className="rounded-2xl border border-slate-800/80 bg-[rgba(12,18,26,0.72)] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Execution Plan</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">
              {targetKind === "suite"
                ? selectedSuite?.display_name ?? "未选择套件"
                : selectedSpec?.display_name ?? "未选择评测类型"}
            </div>
            <div className="mt-1 text-sm text-slate-400">
              {selectedVersion?.description || "当前版本没有额外描述。"}
            </div>
          </div>
          <div className="rounded-xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] px-4 py-3 text-right">
            <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Model Binding</div>
            <div className="mt-2 text-sm font-medium text-slate-100">
              {selectedModel?.name ?? "未选择模型"}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {selectedJudgePolicy ? `Judge Policy · ${selectedJudgePolicy.display_name}` : "Judge Policy · 默认"}
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <InfoCard
            label={targetKind === "suite" ? "套件内容" : "版本信息"}
            value={
              targetKind === "suite"
                ? describeSuiteVersion(selectedSuite, selectedVersion as EvalSuiteVersionSummaryV2 | null)
                : describeSpecVersion(selectedSpec, selectedVersion as EvalSpecVersionSummaryV2 | null)
            }
          />
          <InfoCard
            label="执行引擎"
            value={describeExecutionMode(targetKind, selectedSpec, selectedVersion)}
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

function pickInitialTargetName(
  targetKind: TargetKind,
  suites: EvalSuiteSummaryV2[],
  specs: EvalSpecSummaryV2[]
) {
  return targetKind === "suite" ? suites[0]?.name ?? "" : specs[0]?.name ?? "";
}

function pickInitialVersionValue(
  targetKind: TargetKind,
  targetName: string,
  suites: EvalSuiteSummaryV2[],
  specs: EvalSpecSummaryV2[]
) {
  if (targetKind === "suite") {
    const suite = suites.find((item) => item.name === targetName) ?? suites[0];
    return suite?.versions.find((item) => item.enabled)?.version ?? "";
  }
  const spec = specs.find((item) => item.name === targetName) ?? specs[0];
  return (
    spec?.versions.find((item) => item.enabled && item.is_recommended)?.version ??
    spec?.versions.find((item) => item.enabled)?.version ??
    ""
  );
}

function buildRunName({
  targetKind,
  suite,
  spec,
  version,
  model
}: {
  targetKind: TargetKind;
  suite: EvalSuiteSummaryV2 | null;
  spec: EvalSpecSummaryV2 | null;
  version: EvalSuiteVersionSummaryV2 | EvalSpecVersionSummaryV2 | null;
  model: RegistryModelSummary;
}) {
  const targetDisplay =
    targetKind === "suite" ? suite?.display_name ?? "评测套件" : spec?.display_name ?? "评测类型";
  const versionDisplay = version?.display_name ?? version?.version ?? "版本";
  return `${targetDisplay} · ${versionDisplay} · ${model.name}`;
}

function buildRunDescription({
  targetKind,
  suite,
  spec,
  version
}: {
  targetKind: TargetKind;
  suite: EvalSuiteSummaryV2 | null;
  spec: EvalSpecSummaryV2 | null;
  version: EvalSuiteVersionSummaryV2 | EvalSpecVersionSummaryV2 | null;
}) {
  const targetDisplay =
    targetKind === "suite" ? suite?.display_name ?? "评测套件" : spec?.display_name ?? "评测类型";
  return `${targetDisplay} / ${version?.display_name ?? version?.version ?? "版本"}`;
}

function formatVersionLabel(version: EvalSuiteVersionSummaryV2 | EvalSpecVersionSummaryV2) {
  const parts = [version.display_name || version.version];
  if ("sample_count" in version && typeof version.sample_count === "number") {
    parts.push(`${version.sample_count} samples`);
  }
  return parts.join(" · ");
}

function describeSuiteVersion(
  suite: EvalSuiteSummaryV2 | null,
  version: EvalSuiteVersionSummaryV2 | null
) {
  if (!suite || !version) {
    return "待选择套件与版本。";
  }
  const enabledItems = version.items.filter((item) => item.enabled);
  const groups = Array.from(new Set(enabledItems.map((item) => item.group_name).filter(Boolean)));
  return `${enabledItems.length} 个评测项${groups.length ? `，分组：${groups.join(" / ")}` : ""}`;
}

function describeSpecVersion(
  spec: EvalSpecSummaryV2 | null,
  version: EvalSpecVersionSummaryV2 | null
) {
  if (!spec || !version) {
    return "待选择评测类型与版本。";
  }
  const extras = [spec.capability_category, version.engine_benchmark_name]
    .filter(Boolean)
    .join(" / ");
  return extras || "当前版本没有额外元数据。";
}

function describeExecutionMode(
  targetKind: TargetKind,
  spec: EvalSpecSummaryV2 | null,
  version: EvalSuiteVersionSummaryV2 | EvalSpecVersionSummaryV2 | null
) {
  if (!version) {
    return "待选择版本";
  }
  if (targetKind === "suite") {
    return "suite / temporal fan-out";
  }
  const typedVersion = version as EvalSpecVersionSummaryV2;
  return `${typedVersion.engine} / ${typedVersion.execution_mode}${
    spec?.capability_category ? ` · ${spec.capability_category}` : ""
  }`;
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
  title,
  description,
  disabled,
  onClick
}: {
  active: boolean;
  title: string;
  description: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={[
        "rounded-2xl border px-5 py-4 text-left transition",
        active
          ? "border-sky-400/70 bg-[rgba(24,39,61,0.85)] shadow-[0_0_0_1px_rgba(125,211,252,0.15)]"
          : "border-slate-800/80 bg-[rgba(12,18,26,0.72)] hover:border-slate-700/90",
        disabled ? "cursor-not-allowed opacity-45" : ""
      ].join(" ")}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <div className="text-base font-semibold text-slate-50">{title}</div>
      <div className="mt-2 text-sm leading-6 text-slate-400">{description}</div>
    </button>
  );
}

function FieldBlock({
  label,
  description,
  children
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2.5">
      <div className="space-y-1">
        <Label className="text-sm text-slate-200">{label}</Label>
        {description ? <div className="text-xs leading-5 text-slate-500">{description}</div> : null}
      </div>
      {children}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm leading-6 text-slate-200">{value}</div>
    </div>
  );
}
