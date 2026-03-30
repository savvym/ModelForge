import type { BadgeProps } from "@/components/ui/badge";

type DatasetStatusMeta = {
  label: string;
  variant: BadgeProps["variant"];
  className?: string;
};

const DATASET_STATUS_META: Record<string, DatasetStatusMeta> = {
  uploading: {
    label: "上传中",
    variant: "secondary",
    className: "border-sky-500/35 bg-sky-500/10 text-sky-200"
  },
  ready: {
    label: "导入完成",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  },
  processing: {
    label: "导入中",
    variant: "secondary",
    className: "border-amber-500/35 bg-amber-500/10 text-amber-200"
  },
  failed: {
    label: "上传失败",
    variant: "outline",
    className: "border-rose-500/35 bg-rose-500/10 text-rose-200"
  },
  awaiting_upload: {
    label: "待上传",
    variant: "outline",
    className: "border-zinc-300 bg-zinc-50 text-zinc-700"
  }
};

export function getDatasetStatusMeta(status: string): DatasetStatusMeta {
  return DATASET_STATUS_META[status] ?? { label: status, variant: "outline" };
}

export function formatDatasetScope(scope: string): string {
  if (scope === "my-datasets") {
    return "我的数据集";
  }

  if (scope === "my-data-lake") {
    return "我的数据湖";
  }

  if (scope === "shared") {
    return "共享数据集";
  }

  return scope;
}

export function formatDatasetSourceType(sourceType: string): string {
  if (sourceType === "local-upload") {
    return "本地上传";
  }

  if (sourceType === "s3-import" || sourceType === "tos-import") {
    return "S3 对象存储导入";
  }

  if (sourceType === "data-lake-sampling") {
    return "数据湖采样";
  }

  if (sourceType === "shared-catalog") {
    return "共享目录";
  }

  return sourceType;
}

export function formatDatasetPurpose(purpose: string | null | undefined): string {
  if (purpose === "evaluation") {
    return "模型评测";
  }

  if (purpose === "sft" || purpose === "finetune") {
    return "模型精调";
  }

  if (purpose === "batch-inference") {
    return "批量推理";
  }

  if (purpose === "rag") {
    return "知识库";
  }

  return purpose || "--";
}

export function formatDatasetModality(modality: string | null | undefined): string {
  if (modality === "text-generation" || modality === "jsonl") {
    return "文本生成";
  }

  if (modality === "vision-understanding") {
    return "视觉理解";
  }

  if (modality === "vectorization" || modality === "sft") {
    return "向量化";
  }

  return modality || "--";
}

export function formatDatasetRecipe(recipe: string | null | undefined): string {
  if (recipe === "sft") {
    return "SFT 精调";
  }

  if (recipe === "dpo") {
    return "直接偏好学习";
  }

  if (recipe === "continued-pretrain") {
    return "继续预训练";
  }

  if (recipe === "generic-eval") {
    return "标准评测集";
  }

  return recipe || "--";
}

export function formatDatasetFormatLabel(dataset: {
  purpose?: string | null;
  format?: string | null;
  use_case?: string | null;
  modality?: string | null;
  recipe?: string | null;
}): string {
  const useCase = formatDatasetPurpose(dataset.use_case ?? dataset.purpose);
  const modality = formatDatasetModality(dataset.modality ?? dataset.format);
  const recipe = formatDatasetRecipe(dataset.recipe);

  if (recipe !== "--") {
    return `${useCase} · ${modality} > ${recipe}`;
  }

  return `${useCase} · ${modality}`;
}
