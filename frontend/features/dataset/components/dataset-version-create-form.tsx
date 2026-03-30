"use client";

import { FileUp, HardDriveUpload, Layers3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createDatasetVersion } from "@/features/dataset/api";
import { useDatasetUploadManager } from "@/features/dataset/components/dataset-upload-manager";
import { S3BrowserDialog } from "@/features/object-store/components/s3-browser-dialog";
import { cn } from "@/lib/utils";

const uploadTabs = [
  { key: "local-upload", label: "上传数据集", icon: FileUp },
  { key: "s3-import", label: "从 S3 导入", icon: HardDriveUpload }
] as const;

const secondaryButtonClassName =
  "h-7 whitespace-nowrap rounded-full border border-[rgb(243,243,247)] bg-transparent px-3 text-[14px] font-medium leading-6 text-[#f3f3f7] shadow-[rgb(243,243,247)_0_0_0_1px_inset] transition-colors hover:bg-[rgba(255,255,255,0.05)]";

export function DatasetVersionCreateForm({
  datasetId,
  datasetName,
  nextVersion,
  formatLabel,
  defaultDescription,
  isEvaluationDataset = false
}: {
  datasetId: string;
  datasetName: string;
  nextVersion: number;
  formatLabel: string;
  defaultDescription?: string | null;
  isEvaluationDataset?: boolean;
}) {
  const router = useRouter();
  const { startDatasetVersionUpload } = useDatasetUploadManager();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sourceType, setSourceType] = useState<"local-upload" | "s3-import">("local-upload");
  const [description, setDescription] = useState(defaultDescription ?? "");
  const [sourceUri, setSourceUri] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [s3BrowserOpen, setS3BrowserOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const acceptedFileTypes = isEvaluationDataset ? ".jsonl,.xlsx,.xls" : ".jsonl";

  function handleFileSelect(file: File | null) {
    setSelectedFile(file);
    setError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (sourceType === "local-upload" && !selectedFile) {
      setError("请先选择待上传的数据集文件");
      return;
    }

    if (sourceType === "s3-import" && !sourceUri.trim()) {
      setError("请输入 S3 对象存储路径");
      return;
    }

    setIsSubmitting(true);
    try {
      if (sourceType === "local-upload" && selectedFile) {
        await startDatasetVersionUpload({
          datasetId,
          datasetName,
          versionLabel: `V${nextVersion}`,
          description: description.trim() || null,
          file: selectedFile
        });
      } else {
        await createDatasetVersion(datasetId, {
          description: description.trim() || null,
          source_type: sourceType,
          file_name: null,
          source_uri: sourceUri.trim() || null
        });
      }

      router.push(`/dataset/${datasetId}`);
      router.refresh();
    } catch (requestError: unknown) {
      const message =
        requestError instanceof Error ? requestError.message : "创建数据集版本失败";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-0" onSubmit={handleSubmit}>
      <section className="px-0 pb-3 pt-3">
        <SectionHeading
          description={`为 ${datasetName} 创建 V${nextVersion}，完成后详情页会自动切换到最新版本。`}
          title="基本信息"
        />

        <div className="mt-2.5 grid gap-3">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <div className="space-y-2.5">
              <Label className="text-[13px] text-slate-300">当前数据集</Label>
              <div className="flex h-10 items-center rounded-lg border border-slate-800/90 bg-[rgba(10,15,22,0.18)] px-3 text-[14px] text-slate-100">
                {datasetName}
              </div>
            </div>

            <div className="space-y-2.5">
              <Label className="text-[13px] text-slate-300">版本号</Label>
              <div className="flex h-10 w-fit items-center gap-2 rounded-lg border border-sky-500/30 bg-sky-500/12 px-3 text-[13px] font-medium text-sky-100">
                <Layers3 className="h-4 w-4" />
                V{nextVersion}
              </div>
            </div>
          </div>

          <div className="space-y-2.5">
            <Label className="text-[13px] text-slate-300">用途与格式</Label>
            <div className="flex min-h-[40px] items-center rounded-lg border border-slate-800/90 bg-[rgba(10,15,22,0.18)] px-3 py-2 text-[13px] text-slate-300">
              {formatLabel}
            </div>
          </div>

          <div className="space-y-2.5">
            <Label className="text-[13px] text-slate-300" htmlFor="version-description">
              版本描述
            </Label>
            <Textarea
              className="min-h-[84px] text-[14px]"
              disabled={isSubmitting}
              id="version-description"
              maxLength={300}
              onChange={(event) => {
                setDescription(event.target.value);
                if (error) {
                  setError(null);
                }
              }}
              placeholder="描述本次版本与上一版本的差异、来源或适用场景。"
              value={description}
            />
            <div className="flex flex-wrap items-start justify-between gap-3 text-[12px] leading-5 text-slate-500">
              <div>建议说明这次版本新增了什么、替换了什么，以及主要适用场景。</div>
              <div className="shrink-0">{description.length}/300</div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-slate-800/55 px-0 py-3">
        <SectionHeading title="数据上传" />

        <div className="mt-2.5 space-y-3">
          <div className="flex flex-wrap items-center gap-5 border-b border-slate-800/70">
            {uploadTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = tab.key === sourceType;

              return (
                <button
                  className={cn(
                    "-mb-px inline-flex h-9 items-center gap-2 border-b-2 px-0.5 text-[13px] transition-colors",
                    isActive
                      ? "border-slate-100 font-medium text-slate-50"
                      : "border-transparent text-slate-500 hover:text-slate-200"
                  )}
                  disabled={isSubmitting}
                  key={tab.key}
                  onClick={() => {
                    setSourceType(tab.key);
                    setError(null);
                  }}
                  type="button"
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
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
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <input
                  accept={acceptedFileTypes}
                  className="hidden"
                  disabled={isSubmitting}
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

              {selectedFile ? (
                <div className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                  <div className="inline-flex items-center gap-2 rounded-full border border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-3 py-2 text-slate-300">
                    <FileUp className="h-4 w-4 text-slate-500" />
                    <span className="font-medium text-slate-100">{selectedFile.name}</span>
                    <span className="text-slate-500">{formatFileSize(selectedFile.size)}</span>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="space-y-2.5">
              <Label className="text-[13px] text-slate-300" htmlFor="source_uri">
                对象存储路径
              </Label>
              <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input
                  className="h-10 text-[13px]"
                  disabled={isSubmitting}
                  id="source_uri"
                  onChange={(event) => {
                    setSourceUri(event.target.value);
                    if (error) {
                      setError(null);
                    }
                  }}
                  placeholder="s3://nta-default/nta/dataset/ds-20260320172136-8cxb7/dsv-20260320172136-vwdpc/new-version.jsonl"
                  value={sourceUri}
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
          )}
        </div>
      </section>

      <section className="px-0 py-4">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button className="bg-sky-500 px-5 text-slate-950 hover:bg-sky-400" disabled={isSubmitting} type="submit">
            {isSubmitting ? "提交中..." : "创建版本"}
          </Button>
          <Button
            className={secondaryButtonClassName}
            disabled={isSubmitting}
            onClick={() => router.push(`/dataset/${datasetId}`)}
            type="button"
            variant="outline"
          >
            取消
          </Button>
        </div>
        <FieldError message={error} />
      </section>

      <S3BrowserDialog
        initialUri={sourceUri}
        onClose={() => setS3BrowserOpen(false)}
        onSelect={(uri) => {
          setSourceUri(uri);
          setError(null);
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

function FieldError({ message }: { message?: string | null }) {
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
