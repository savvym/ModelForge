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

  const eligibleDimensions = React.useMemo(
    () =>
      evalTemplates.filter(
        (template) =>
          template.template_type === "llm_categorical" || template.template_type === "llm_numeric"
      ),
    [evalTemplates]
  );

  const [displayName, setDisplayName] = React.useState(initialBenchmark?.display_name ?? "");
  const [description, setDescription] = React.useState(initialBenchmark?.description ?? "");
  const [category, setCategory] = React.useState(initialBenchmark?.category ?? "llm");
  const [selectedTemplateId, setSelectedTemplateId] = React.useState<string>(
    initialBenchmark?.eval_template_id ?? eligibleDimensions[0]?.id ?? "none"
  );

  const selectedDimension =
    eligibleDimensions.find((template) => template.id === selectedTemplateId) ?? null;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!displayName.trim()) {
      setError("请输入 Benchmark 显示名称。");
      return;
    }

    if (!selectedDimension) {
      setError("请选择一个评测维度。");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        display_name: displayName.trim(),
        description: description.trim() || undefined,
        category: category || undefined,
        default_eval_method: "judge-template",
        requires_judge_model: true,
        eval_template_id: selectedDimension.id
      };

      if (mode === "edit" && initialBenchmark) {
        await updateBenchmarkDefinition(initialBenchmark.name, payload);
        router.push(`/model/eval-benchmarks/${initialBenchmark.name}`);
      } else {
        const created = await createBenchmarkDefinition(payload);
        router.push(`/model/eval-benchmarks/${created.name}`);
      }
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "保存 Benchmark 失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">基础信息</legend>

        {mode === "edit" && initialBenchmark ? (
          <div className="space-y-2">
            <Label htmlFor="name">Benchmark ID</Label>
            <Input id="name" value={initialBenchmark.name} readOnly disabled />
            <p className="text-xs text-muted-foreground">Benchmark ID 创建后不可修改。</p>
          </div>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="displayName">显示名称</Label>
          <Input
            id="displayName"
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="例如 NTA Bench Network"
            value={displayName}
          />
          {mode === "create" ? (
            <p className="text-xs text-muted-foreground">
              系统会自动生成 Benchmark ID，并将这个 Benchmark 作为后续数据集版本的容器。
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">描述</Label>
          <Input
            id="description"
            onChange={(event) => setDescription(event.target.value)}
            placeholder="介绍这个 Benchmark 评测什么能力，以及适用场景"
            value={description}
          />
        </div>

        <div className="space-y-2">
          <Label>分类</Label>
          <Select onValueChange={setCategory} value={category}>
            <SelectTrigger className="w-[220px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </fieldset>

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">评测维度</legend>

        <div className="space-y-2">
          <Label>选择评测维度</Label>
          <Select onValueChange={setSelectedTemplateId} value={selectedTemplateId}>
            <SelectTrigger>
              <SelectValue placeholder="选择评测维度" />
            </SelectTrigger>
            <SelectContent>
              {eligibleDimensions.length === 0 ? (
                <SelectItem value="none" disabled>
                  暂无可用评测维度
                </SelectItem>
              ) : null}
              {eligibleDimensions.map((dimension) => (
                <SelectItem key={dimension.id} value={dimension.id}>
                  {dimension.name} · v{dimension.version}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            自定义 Benchmark 创建时会绑定一个评测维度。后续上传的 Benchmark Version 默认需要遵循这个维度的数据格式，不再做额外字段映射。
          </p>
        </div>

        {selectedDimension ? (
          <div className="grid gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4 md:grid-cols-4">
            <TemplateSummaryItem label="维度名称" value={`${selectedDimension.name} · v${selectedDimension.version}`} />
            <TemplateSummaryItem
              label="评测类型"
              value={getTemplateTypeLabel(selectedDimension.template_type)}
            />
            <TemplateSummaryItem label="评分器" value={getPresetLabel(selectedDimension.preset_id)} />
            <TemplateSummaryItem
              label="裁判模型"
              value={selectedDimension.model || "跟随任务配置"}
            />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
            当前还没有可用于 Benchmark 的自动评测维度。请先创建评测维度，再回来创建 Benchmark。
          </div>
        )}
      </fieldset>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="flex gap-3">
        <Button disabled={submitting || eligibleDimensions.length === 0} type="submit">
          {submitting
            ? mode === "edit"
              ? "保存中..."
              : "创建中..."
            : mode === "edit"
              ? "保存 Benchmark"
              : "创建 Benchmark"}
        </Button>
        <Button onClick={() => router.back()} type="button" variant="outline">
          取消
        </Button>
      </div>
    </form>
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
