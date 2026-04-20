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
import { buildObjectStoreRootPrefix } from "@/lib/object-store-layout";
import { cn } from "@/lib/utils";

const uploadTabs = [
  { key: "local-upload", label: "上传数据集", icon: FileUp },
  { key: "s3-import", label: "从 S3 导入", icon: HardDriveUpload }
] as const;

const secondaryButtonClassName =
  "h-7 whitespace-nowrap rounded-full border border-border bg-transparent px-3 text-[14px] font-medium leading-6 text-foreground transition-colors hover:bg-accent hover:text-accent-foreground";

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
        void startDatasetVersionUpload({
          datasetId,
          datasetName,
          versionLabel: `V${nextVersion}`,
          description: description.trim() || null,
          file: selectedFile
        }).catch((uploadError: unknown) => {
          console.error("dataset version direct upload init failed", uploadError);
        });
        router.push(`/dataset/${datasetId}`);
        return;
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
              <Label className="text-[13px] text-foreground">当前数据集</Label>
              <div className="flex h-10 items-center rounded-lg border border-border bg-card/80 px-3 text-[14px] text-foreground">
                {datasetName}
              </div>
            </div>

            <div className="space-y-2.5">
              <Label className="text-[13px] text-foreground">版本号</Label>
              <div className="flex h-10 w-fit items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 text-[13px] font-medium text-primary">
                <Layers3 className="h-4 w-4" />
                V{nextVersion}
              </div>
            </div>
          </div>

          <div className="space-y-2.5">
            <Label className="text-[13px] text-foreground">用途与格式</Label>
            <div className="flex min-h-[40px] items-center rounded-lg border border-border bg-card/80 px-3 py-2 text-[13px] text-foreground">
              {formatLabel}
            </div>
          </div>

          <div className="space-y-2.5">
            <Label className="text-[13px] text-foreground" htmlFor="version-description">
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
            <div className="flex flex-wrap items-start justify-between gap-3 text-[12px] leading-5 text-muted-foreground">
              <div>建议说明这次版本新增了什么、替换了什么，以及主要适用场景。</div>
              <div className="shrink-0">{description.length}/300</div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-border px-0 py-3">
        <SectionHeading title="数据上传" />

        <div className="mt-2.5 space-y-3">
          <div className="flex flex-wrap items-center gap-5 border-b border-border">
            {uploadTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = tab.key === sourceType;

              return (
                <button
                  className={cn(
                    "-mb-px inline-flex h-9 items-center gap-2 border-b-2 px-0.5 text-[13px] transition-colors",
                    isActive
                      ? "border-primary font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
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
                    ? "border-primary/50 bg-primary/10"
                    : "border-border bg-card/80"
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
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-card/80 text-foreground">
                    <FileUp className="h-5 w-5" />
                  </div>
                  <div className="mt-3 text-[14px] font-medium text-foreground">
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
                    <span className="rounded-full border border-border bg-card/80 px-2.5 py-1 text-[12px] text-muted-foreground">
                      {isEvaluationDataset ? "支持 JSONL / XLSX / XLS" : "推荐 JSONL"}
                    </span>
                    <span className="rounded-full border border-border bg-card/80 px-2.5 py-1 text-[12px] text-muted-foreground">
                      当前环境接入 COS
                    </span>
                  </div>
                </div>
              </div>

              {selectedFile ? (
                <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                  <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-2 text-foreground">
                    <FileUp className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium text-foreground">{selectedFile.name}</span>
                    <span className="text-muted-foreground">{formatFileSize(selectedFile.size)}</span>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="space-y-2.5">
              <Label className="text-[13px] text-foreground" htmlFor="source_uri">
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
                  placeholder={`s3://your-bucket/${buildObjectStoreRootPrefix()}projects/<project-id>/datasets/<dataset-code>/versions/<version-code>/source/new-version.jsonl`}
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
              <div className="text-[12px] leading-5 text-muted-foreground">
                支持直接粘贴对象路径，或从右侧资源浏览器选择文件。导入后会同步生成版本记录，并保留文件预览与下载能力。
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="px-0 py-4">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <Button className="px-5" disabled={isSubmitting} type="submit">
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
      <h2 className="text-[14px] font-medium text-foreground">{title}</h2>
      {description ? <p className="text-[12px] leading-5 text-muted-foreground">{description}</p> : null}
    </div>
  );
}

function FieldError({ message }: { message?: string | null }) {
  if (!message) {
    return null;
  }

  return <p className="mt-2 text-[12px] text-destructive">{message}</p>;
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
