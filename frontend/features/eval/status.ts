import type { BadgeProps } from "@/components/ui/badge";

type EvalStatusMeta = {
  label: string;
  variant: BadgeProps["variant"];
  className?: string;
};

const STATUS_META: Record<string, EvalStatusMeta> = {
  queued: { label: "排队中", variant: "secondary" },
  running: { label: "执行中", variant: "default" },
  preparing: { label: "准备中", variant: "secondary" },
  inferencing: { label: "推理中", variant: "default" },
  cancelling: { label: "停止中", variant: "secondary" },
  scoring: {
    label: "评分中",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  },
  completed: {
    label: "已完成",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  },
  cancelled: {
    label: "已停止",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  },
  failed: {
    label: "失败",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  }
};

const DELETE_BLOCKED_STATUSES = new Set(["preparing", "inferencing", "scoring", "cancelling"]);
const STOPPABLE_STATUSES = new Set(["queued", "preparing", "inferencing", "scoring"]);
const RUN_DELETE_BLOCKED_STATUSES = new Set(["queued", "running", "cancelling"]);
const RUN_CANCELLABLE_STATUSES = new Set(["queued", "running"]);

export function getEvalStatusMeta(status: string): EvalStatusMeta {
  return STATUS_META[status] ?? { label: status, variant: "outline" };
}

export function canDeleteEvalJob(status: string): boolean {
  return !DELETE_BLOCKED_STATUSES.has(status);
}

export function canStopEvalJob(status: string): boolean {
  return STOPPABLE_STATUSES.has(status);
}

export function getEvalDeleteBlockedReason(status: string): string | null {
  if (!canDeleteEvalJob(status)) {
    return "运行中的评测任务暂不支持删除，请等待任务完成后再删除。";
  }
  return null;
}

export function getEvalStopBlockedReason(status: string): string | null {
  if (!canStopEvalJob(status)) {
    return "当前任务状态不支持停止。";
  }
  return null;
}

export function canDeleteEvaluationRun(status: string): boolean {
  return !RUN_DELETE_BLOCKED_STATUSES.has(status);
}

export function canCancelEvaluationRun(status: string): boolean {
  return RUN_CANCELLABLE_STATUSES.has(status);
}

export function getEvaluationRunDeleteBlockedReason(status: string): string | null {
  if (!canDeleteEvaluationRun(status)) {
    return "运行中的评测任务暂不支持删除，请等待任务结束后再删除。";
  }
  return null;
}

export function getEvaluationRunCancelBlockedReason(status: string): string | null {
  if (!canCancelEvaluationRun(status)) {
    return "当前任务状态不支持取消。";
  }
  return null;
}

export function formatInferenceMode(mode: string): string {
  if (mode === "batch") {
    return "批量推理";
  }

  if (mode === "endpoint") {
    return "在线推理";
  }

  return mode;
}

export function formatEvalMethod(method: string): string {
  if (method === "judge-template") {
    return "评测模板";
  }

  if (method === "judge-rubric" || method === "judge-model") {
    return "Rubric 标准打分";
  }

  if (method === "judge-quality") {
    return "质量评分";
  }

  if (method === "accuracy") {
    return "标准答案比对";
  }

  if (method === "exact-match") {
    return "精确匹配";
  }

  if (method === "rule-based") {
    return "规则校验";
  }

  return method;
}

export function formatModelSource(source: string): string {
  if (source === "model-square") {
    return "模型广场";
  }

  if (source === "model-warehouse") {
    return "接入模型";
  }

  return source;
}

export function formatAccessSource(source: string): string {
  if (source === "nta") {
    return "NTA";
  }

  if (source === "ark") {
    return "火山方舟";
  }

  if (source === "ml-platform") {
    return "机器学习平台";
  }

  return source;
}

export function formatTaskType(taskType: string): string {
  if (taskType === "single-turn") {
    return "单轮任务测评";
  }

  if (taskType === "multi-turn") {
    return "多轮任务测评";
  }

  return taskType;
}

export function formatEvalMode(mode: string): string {
  if (mode === "infer-auto") {
    return "推理+自动评测";
  }

  if (mode === "inference-only") {
    return "仅推理";
  }

  return mode;
}

export function formatEvalDatasetSource(sourceType: string): string {
  if (sourceType === "benchmark-version") {
    return "Benchmark Version";
  }

  if (sourceType === "benchmark-preset") {
    return "Benchmark Version";
  }

  if (sourceType === "managed-dataset") {
    return "上传数据集";
  }

  if (sourceType === "s3-import" || sourceType === "tos-import") {
    return "从 S3 对象存储导入";
  }

  if (sourceType === "preset-suite") {
    return "预置评测集";
  }

  return sourceType;
}

export function formatEvaluationRunKind(kind: string): string {
  if (kind === "suite") {
    return "基线评测";
  }
  if (kind === "spec") {
    return "自定义评测";
  }
  if (kind === "benchmark") {
    return "Benchmark 评测";
  }
  return kind;
}

export function formatLeaderboardMetricName(metricName?: string | null): string {
  if (!metricName) {
    return "--";
  }

  if (metricName === "judge_template") {
    return "模板得分";
  }

  if (metricName === "judge_rubric") {
    return "Rubric 得分";
  }

  if (metricName === "judge_quality") {
    return "质量得分";
  }

  if (metricName === "acc" || metricName === "accuracy") {
    return "准确率";
  }

  return metricName;
}
