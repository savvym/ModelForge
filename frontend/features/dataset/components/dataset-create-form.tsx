"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FileUp, HardDriveUpload, Layers3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createDataset } from "@/features/dataset/api";
import { useDatasetUploadManager } from "@/features/dataset/components/dataset-upload-manager";
import { S3BrowserDialog } from "@/features/object-store/components/s3-browser-dialog";
import { cn } from "@/lib/utils";

const datasetTypeOptions = [
  {
    key: "sft",
    label: "SFT 精调",
    description: "适合监督微调数据，默认按文本生成任务组织版本。",
    badge: "精调"
  },
  {
    key: "dpo",
    label: "直接偏好学习",
    description: "适合偏好对比数据，便于后续偏好优化与回放。",
    badge: "偏好"
  },
  {
    key: "continued-pretrain",
    label: "继续预训练",
    description: "用于增量预训练语料，适合大批量语料整理。",
    badge: "预训练"
  },
  {
    key: "evaluation",
    label: "评测数据集",
    description: "用于模型评测任务，创建后可直接在评测链路中选用。",
    badge: "评测"
  }
] as const;

const datasetTypeConfig = {
  sft: {
    purpose: "finetune",
    use_case: "finetune",
    modality: "text-generation",
    recipe: "sft",
    tags: ["finetune", "text-generation", "sft"]
  },
  dpo: {
    purpose: "finetune",
    use_case: "finetune",
    modality: "text-generation",
    recipe: "dpo",
    tags: ["finetune", "text-generation", "dpo"]
  },
  "continued-pretrain": {
    purpose: "finetune",
    use_case: "finetune",
    modality: "text-generation",
    recipe: "continued-pretrain",
    tags: ["finetune", "text-generation", "continued-pretrain"]
  },
  evaluation: {
    purpose: "evaluation",
    use_case: "evaluation",
    modality: "text-generation",
    recipe: "generic-eval",
    tags: ["evaluation", "text-generation", "generic-eval"]
  }
} as const;

const uploadTabs = [
  { key: "local-upload", label: "上传数据集", icon: FileUp },
  { key: "s3-import", label: "从 S3 导入", icon: HardDriveUpload }
] as const;

const secondaryButtonClassName =
  "h-7 whitespace-nowrap rounded-full border border-[rgb(243,243,247)] bg-transparent px-3 text-[14px] font-medium leading-6 text-[#f3f3f7] shadow-[rgb(243,243,247)_0_0_0_1px_inset] transition-colors hover:bg-[rgba(255,255,255,0.05)]";

const activeSecondaryButtonClassName =
  "h-7 whitespace-nowrap rounded-full border border-[rgb(243,243,247)] bg-[rgba(255,255,255,0.08)] px-3 text-[14px] font-medium leading-6 text-[#f3f3f7] shadow-[rgb(243,243,247)_0_0_0_1px_inset]";

const datasetSchema = z
  .object({
    name: z.string().min(3, "数据集名称至少 3 个字符"),
    description: z.string().max(500, "描述不能超过 500 个字符").optional(),
    dataset_type: z.enum(["sft", "dpo", "continued-pretrain", "evaluation"]),
    source_type: z.enum(["local-upload", "s3-import"]),
    file_name: z.string().optional(),
    source_uri: z.string().optional()
  })
  .superRefine((value, ctx) => {
    if (value.source_type === "local-upload" && !value.file_name?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "请先选择待上传的数据集文件",
        path: ["file_name"]
      });
    }

    if (value.source_type === "s3-import" && !value.source_uri?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "请输入 S3 对象存储路径",
        path: ["source_uri"]
      });
    }
  });

type DatasetFormValues = z.infer<typeof datasetSchema>;

export function DatasetCreateForm() {
  const router = useRouter();
  const { startDatasetCreateUpload } = useDatasetUploadManager();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [s3BrowserOpen, setS3BrowserOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const form = useForm<DatasetFormValues>({
    resolver: zodResolver(datasetSchema),
    defaultValues: {
      name: "nta-bench",
      description: "用于模型精调和回归验证的数据集版本。",
      dataset_type: "sft",
      source_type: "local-upload",
      file_name: "",
      source_uri: ""
    }
  });

  const datasetType = form.watch("dataset_type");
  const sourceType = form.watch("source_type");
  const isEvaluationDataset = datasetType === "evaluation";
  const acceptedFileTypes = isEvaluationDataset ? ".jsonl,.xlsx,.xls" : ".jsonl";

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    form.setValue("file_name", file?.name ?? "", {
      shouldDirty: true,
      shouldValidate: true
    });
  };

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    const typeConfig = datasetTypeConfig[values.dataset_type];

    setIsSubmitting(true);
    try {
      if (values.source_type === "local-upload" && selectedFile) {
        void startDatasetCreateUpload({
          name: values.name,
          description: values.description?.trim() || null,
          purpose: typeConfig.purpose,
          format: typeConfig.modality,
          use_case: typeConfig.use_case,
          modality: typeConfig.modality,
          recipe: typeConfig.recipe,
          scope: "my-datasets",
          tags: [...typeConfig.tags],
          file: selectedFile
        }).catch((error: unknown) => {
          console.error("dataset direct upload init failed", error);
        });
        router.push("/dataset");
        return;
      }

      await createDataset({
        name: values.name,
        description: values.description?.trim() || null,
        purpose: typeConfig.purpose,
        format: typeConfig.modality,
        use_case: typeConfig.use_case,
        modality: typeConfig.modality,
        recipe: typeConfig.recipe,
        scope: "my-datasets",
        source_type: values.source_type,
        tags: [...typeConfig.tags],
        file_name: values.file_name?.trim() || null,
        source_uri: values.source_uri?.trim() || null
      });
      router.push("/dataset");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "创建数据集失败";
      form.setError("root", { message });
    } finally {
      setIsSubmitting(false);
    }
  });

  return (
    <form
      id="dataset-create-form"
      className="space-y-0"
      onSubmit={onSubmit}
    >
      <section className="px-0 pb-3 pt-3">
        <SectionHeading title="基本信息" />

        <div className="mt-2.5 grid gap-3">
          <div className="space-y-2.5">
            <Label className="text-[13px] text-slate-300" htmlFor="name">
              数据集名称
            </Label>
            <Input
              className="h-10 text-[14px]"
              disabled={isSubmitting}
              id="name"
              placeholder="请输入数据集名称"
              {...form.register("name")}
            />
            <FieldError message={form.formState.errors.name?.message} />
          </div>

          <div className="space-y-2.5">
            <Label className="text-[13px] text-slate-300" htmlFor="description">
              数据集描述
            </Label>
            <Textarea
              className="min-h-[84px] text-[14px]"
              disabled={isSubmitting}
              id="description"
              placeholder="描述数据来源、字段结构和适用场景。"
              {...form.register("description")}
            />
            <FieldError message={form.formState.errors.description?.message} />
          </div>
        </div>
      </section>

      <section className="border-t border-slate-800/55 px-0 py-3">
        <SectionHeading title="数据类型" />

        <div className="mt-2.5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {datasetTypeOptions.map((option) => {
            const isActive = option.key === datasetType;

            return (
              <button
                className={cn(
                  "rounded-lg border px-4 py-2.5 text-left transition-all",
                  isActive
                    ? "border-sky-500/45 bg-[rgba(18,29,40,0.48)] text-slate-50"
                    : "border-slate-800/90 bg-[rgba(10,15,22,0.2)] text-slate-300 hover:border-slate-700 hover:bg-[rgba(14,20,29,0.34)] hover:text-slate-50"
                )}
                disabled={isSubmitting}
                key={option.key}
                onClick={() =>
                  form.setValue("dataset_type", option.key, { shouldValidate: true })
                }
                type="button"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-[14px] font-medium">{option.label}</div>
                  <span
                    className={cn(
                      "rounded-full border px-2.5 py-0.5 text-[11px]",
                      isActive
                        ? "border-white/12 bg-white/8 text-white/85"
                        : "border-slate-800 bg-[rgba(10,15,22,0.34)] text-slate-400"
                    )}
                  >
                    {option.badge}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

      </section>

      <section className="border-t border-slate-800/55 px-0 py-3">
        <SectionHeading title="数据上传" />

        <div className="mt-2.5 space-y-3">
          <div className="flex flex-wrap items-center gap-2 pb-1">
            <div className="text-[14px] font-medium text-slate-100">版本</div>
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/12 px-3 py-1.5 text-[12px] font-medium text-sky-100">
              <Layers3 className="h-3.5 w-3.5" />
              V1
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="text-[14px] font-medium text-slate-100">文件上传</div>
            <div className="flex flex-wrap items-center gap-2">
              {uploadTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = tab.key === sourceType;

                return (
                  <button
                    className={cn(
                      "inline-flex items-center gap-2",
                      isActive
                        ? activeSecondaryButtonClassName
                        : secondaryButtonClassName
                    )}
                    disabled={isSubmitting}
                    key={tab.key}
                    onClick={() =>
                      form.setValue("source_type", tab.key, { shouldValidate: true })
                    }
                    type="button"
                  >
                    <Icon className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {sourceType === "local-upload" ? (
            <div className="space-y-2.5">
              <div
                className={cn(
                  "rounded-lg border border-dashed px-5 py-5 transition-colors",
                  isDragging
                    ? "border-sky-500/55 bg-[rgba(18,30,42,0.42)]"
                    : "border-slate-800/90 bg-[rgba(10,15,22,0.16)]"
                )}
                onClick={() => fileInputRef.current?.click()}
                onDragEnter={(event) => {
                  event.preventDefault();
                  if (!isSubmitting) {
                    setIsDragging(true);
                  }
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsDragging(false);
                  if (isSubmitting) {
                    return;
                  }

                  const file = event.dataTransfer.files?.[0] ?? null;
                  handleFileSelect(file);
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
              >
                <input
                  disabled={isSubmitting}
                  accept={acceptedFileTypes}
                  id="file"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    handleFileSelect(file);
                  }}
                  ref={fileInputRef}
                  type="file"
                />

                <div className="mx-auto flex max-w-xl flex-col items-center text-center">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-slate-800/90 bg-[rgba(10,15,22,0.32)] text-slate-300">
                    <FileUp className="h-5 w-5" />
                  </div>
                  <div className="mt-3 text-[14px] font-medium text-slate-100">
                    将文件拖拽到此处，或点击上传
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                    <Button
                      className={secondaryButtonClassName}
                      disabled={isSubmitting}
                      onClick={(event) => {
                        event.stopPropagation();
                        fileInputRef.current?.click();
                      }}
                      type="button"
                      variant="outline"
                    >
                      选择文件
                    </Button>
                    <span className="rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-2.5 py-1 text-[12px] text-slate-400">
                      {isEvaluationDataset ? "支持 JSONL / XLSX / XLS" : "推荐 JSONL"}
                    </span>
                    <span className="rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-2.5 py-1 text-[12px] text-slate-400">
                      当前环境接入 RustFS
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                {selectedFile ? (
                  <div className="inline-flex items-center gap-2 rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-3 py-2 text-slate-300">
                    <FileUp className="h-4 w-4 text-slate-500" />
                    <span className="font-medium text-slate-100">{selectedFile.name}</span>
                    <span className="text-slate-500">
                      {formatFileSize(selectedFile.size)}
                    </span>
                  </div>
                ) : (
                  <>
                    <span className="rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-2.5 py-1">
                      支持预览与下载
                    </span>
                    <span className="rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-2.5 py-1">
                      创建后自动生成 V1
                    </span>
                  </>
                )}
              </div>
              <FieldError message={form.formState.errors.file_name?.message} />
            </div>
          ) : (
            <div className="space-y-2.5">
              <div className="space-y-2.5">
                <Label className="text-[13px] text-slate-300" htmlFor="source_uri">
                  对象存储路径
                </Label>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <Input
                    className="h-10 text-[13px]"
                    disabled={isSubmitting}
                    id="source_uri"
                    placeholder="s3://nta-default/nta/dataset/ds-20260320172136-8cxb7/dsv-20260320172136-vwdpc/SFT_TextEmbedding_Sample.jsonl"
                    {...form.register("source_uri")}
                  />
                  <Button
                    className={cn(secondaryButtonClassName, "self-center")}
                    disabled={isSubmitting}
                    onClick={() => setS3BrowserOpen(true)}
                    type="button"
                    variant="outline"
                  >
                    从对象存储选择
                  </Button>
                </div>
                <div className="text-[12px] leading-5 text-slate-500">
                  支持直接粘贴对象路径，或从右侧资源浏览器选择文件。导入后会同步生成版本记录，并保留文件预览与下载能力。
                </div>
              </div>
              <FieldError message={form.formState.errors.source_uri?.message} />
            </div>
          )}
        </div>
      </section>

      <section className="border-t border-slate-800/55 px-0 py-4">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button
            className="bg-sky-500 px-5 text-slate-950 hover:bg-sky-400"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "提交中..." : "创建数据集"}
          </Button>
          <Button
            className={secondaryButtonClassName}
            disabled={isSubmitting}
            onClick={() => router.push("/dataset")}
            type="button"
            variant="outline"
          >
            取消
          </Button>
        </div>
        <FieldError message={form.formState.errors.root?.message} />
      </section>

      <S3BrowserDialog
        initialUri={form.watch("source_uri")}
        onClose={() => setS3BrowserOpen(false)}
        onSelect={(uri) => {
          form.setValue("source_uri", uri, {
            shouldDirty: true,
            shouldValidate: true
          });
        }}
        open={s3BrowserOpen}
      />
    </form>
  );
}

function SectionHeading({
  title,
  description
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="space-y-0.5">
      <h2 className="text-[14px] font-medium text-slate-100">{title}</h2>
      {description ? <p className="text-[12px] leading-5 text-slate-500">{description}</p> : null}
    </div>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }

  return <p className="mt-2 text-[12px] text-rose-400">{message}</p>;
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
