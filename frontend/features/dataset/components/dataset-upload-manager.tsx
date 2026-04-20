"use client";

import * as React from "react";
import Uppy, { type UppyFile } from "@uppy/core";
import { FilesList, UppyContextProvider, useUppyState } from "@uppy/react";
import StatusBar from "@uppy/react/status-bar";
import { ChevronDown, ChevronUp, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  completeDatasetDirectUpload,
  failDatasetDirectUpload,
  getDataset,
  prepareDatasetDirectUpload,
  prepareDatasetVersionDirectUpload
} from "@/features/dataset/api";
import { uploadFileWithDirectUpload } from "@/features/dataset/direct-upload";
import type { ObjectStoreUploadResponse } from "@/types/api";

type QueueItemStatus = "preparing" | "uploading" | "processing" | "completed" | "failed";
type QueueItemOperation = "create-dataset" | "create-version";
type DatasetUploadBody = ObjectStoreUploadResponse & Record<string, unknown>;
type DatasetUploadUppy = Uppy<DatasetUploadFileMeta, DatasetUploadBody>;
type DatasetUploadUppyFile = UppyFile<DatasetUploadFileMeta, DatasetUploadBody>;

type DatasetUploadPreparedTask = {
  datasetId: string;
  versionId: string;
  upload: Awaited<ReturnType<typeof prepareDatasetDirectUpload>>["upload"];
};

type DatasetUploadFileMeta = {
  taskId: string;
  operation: QueueItemOperation;
  datasetName: string;
  description?: string | null;
  purpose?: string | null;
  format?: string | null;
  useCase?: string | null;
  modality?: string | null;
  recipe?: string | null;
  scope: string;
  versionLabel: string;
  versionNumber: number;
  createdAt: string;
  updatedAt: number;
  prepared?: DatasetUploadPreparedTask;
};

export type DatasetUploadQueueItem = {
  id: string;
  datasetId: string | null;
  versionId: string | null;
  persisted: boolean;
  datasetName: string;
  description?: string | null;
  purpose?: string | null;
  format?: string | null;
  useCase?: string | null;
  modality?: string | null;
  recipe?: string | null;
  scope: string;
  versionLabel: string;
  versionNumber: number;
  fileName: string;
  sizeBytes: number;
  uploadedBytes: number;
  status: QueueItemStatus;
  operation: QueueItemOperation;
  error?: string | null;
  createdAt: string;
  updatedAt: number;
};

type DatasetUploadManagerContextValue = {
  startDatasetCreateUpload: (input: {
    name: string;
    description?: string | null;
    purpose: string;
    format: string;
    use_case?: string | null;
    modality?: string | null;
    recipe?: string | null;
    scope: string;
    tags: string[];
    file: File;
  }) => Promise<{ datasetId: string; versionId: string }>;
  startDatasetVersionUpload: (input: {
    datasetId: string;
    datasetName: string;
    versionLabel: string;
    description?: string | null;
    format?: string | null;
    file: File;
  }) => Promise<void>;
};

const DatasetUploadManagerContext = React.createContext<DatasetUploadManagerContextValue | null>(
  null
);
const DatasetUploadQueueItemsContext = React.createContext<DatasetUploadQueueItem[]>([]);

const statusBarLocale = {
  pluralize: (count: number) => (count === 1 ? 0 : 1),
  strings: {
    uploading: "上传中",
    complete: "上传完成",
    uploadFailed: "上传失败",
    paused: "已暂停",
    retry: "重试",
    cancel: "取消",
    pause: "暂停",
    resume: "继续",
    done: "完成",
    filesUploadedOfTotal: {
      0: "已上传 %{complete} / %{smart_count} 个文件",
      1: "已上传 %{complete} / %{smart_count} 个文件"
    },
    dataUploadedOfTotal: "%{complete} / %{total}",
    dataUploadedOfUnknown: "已上传 %{complete}",
    xTimeLeft: "剩余 %{time}",
    uploadXFiles: {
      0: "上传 %{smart_count} 个文件",
      1: "上传 %{smart_count} 个文件"
    },
    uploadXNewFiles: {
      0: "上传 +%{smart_count} 个文件",
      1: "上传 +%{smart_count} 个文件"
    },
    upload: "上传",
    retryUpload: "重试上传",
    xMoreFilesAdded: {
      0: "新增 %{smart_count} 个文件",
      1: "新增 %{smart_count} 个文件"
    },
    showErrorDetails: "查看错误详情",
    failedToAddFiles: "添加文件失败"
  }
} as const;

function buildPendingUploadTaskId(prefix: QueueItemOperation) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}:${crypto.randomUUID()}`;
  }

  return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
}

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function createDatasetUploadUppy() {
  return new Uppy<DatasetUploadFileMeta, DatasetUploadBody>({
    id: "dataset-upload-manager",
    allowMultipleUploadBatches: true,
    autoProceed: false,
    locale: statusBarLocale
  });
}

function touchFileMeta(uppy: DatasetUploadUppy, fileId: string) {
  const file = uppy.getFile(fileId);

  if (!file) {
    return;
  }

  uppy.setFileMeta(fileId, {
    ...file.meta,
    updatedAt: Date.now()
  });
}

function resolveQueueItemStatus(file: DatasetUploadUppyFile): QueueItemStatus {
  if (file.error) {
    return "failed";
  }

  if (file.progress.postprocess) {
    return "processing";
  }

  if (file.progress.uploadComplete || file.progress.complete) {
    return "completed";
  }

  if (typeof file.progress.uploadStarted === "number") {
    return "uploading";
  }

  return "preparing";
}

function mapUppyFileToQueueItem(file: DatasetUploadUppyFile): DatasetUploadQueueItem {
  const prepared = file.meta.prepared;

  return {
    id: file.id,
    datasetId: prepared?.datasetId ?? null,
    versionId: prepared?.versionId ?? null,
    persisted: Boolean(prepared),
    datasetName: file.meta.datasetName,
    description: file.meta.description ?? null,
    purpose: file.meta.purpose ?? null,
    format: file.meta.format ?? null,
    useCase: file.meta.useCase ?? null,
    modality: file.meta.modality ?? null,
    recipe: file.meta.recipe ?? null,
    scope: file.meta.scope,
    versionLabel: file.meta.versionLabel,
    versionNumber: file.meta.versionNumber,
    fileName: file.name,
    sizeBytes: file.size ?? 0,
    uploadedBytes: typeof file.progress.bytesUploaded === "number" ? file.progress.bytesUploaded : 0,
    status: resolveQueueItemStatus(file),
    operation: file.meta.operation,
    error: file.error ?? null,
    createdAt: file.meta.createdAt,
    updatedAt: file.meta.updatedAt
  };
}

function normalizeQueueItems(files: DatasetUploadUppyFile[]) {
  return [...files]
    .map(mapUppyFileToQueueItem)
    .sort((left, right) => right.updatedAt - left.updatedAt);
}

function removeFinishedUploads(uppy: DatasetUploadUppy) {
  for (const file of uppy.getFiles()) {
    const status = resolveQueueItemStatus(file);
    if (status === "completed" || status === "failed") {
      uppy.removeFile(file.id);
    }
  }
}

async function waitForDatasetVersionReady(params: {
  uppy: DatasetUploadUppy;
  fileId: string;
  datasetId: string;
  versionId: string;
}) {
  while (true) {
    const currentFile = params.uppy.getFile(params.fileId);
    if (!currentFile) {
      return;
    }

    params.uppy.emit("postprocess-progress", currentFile, {
      mode: "indeterminate",
      message: "后台处理中"
    });

    const dataset = await getDataset(params.datasetId);
    const version = dataset.versions.find((entry) => entry.id === params.versionId);
    if (!version) {
      throw new Error("数据集版本不存在");
    }

    if (version.status === "ready") {
      return;
    }

    if (version.status === "failed") {
      throw new Error("后台导入失败");
    }

    await delay(2500);
  }
}

function DatasetUploadCenter({
  collapsed,
  onCollapsedChange,
  queueItems,
  uppy
}: {
  collapsed: boolean;
  onCollapsedChange: React.Dispatch<React.SetStateAction<boolean>>;
  queueItems: DatasetUploadQueueItem[];
  uppy: DatasetUploadUppy;
}) {
  const activeCount = queueItems.filter(
    (item) =>
      item.status === "preparing" || item.status === "uploading" || item.status === "processing"
  ).length;
  const finishedCount = queueItems.filter(
    (item) => item.status === "completed" || item.status === "failed"
  ).length;
  const hasQueueItems = queueItems.length > 0;
  const uppyContext = uppy as unknown as Uppy;

  return (
    <div
      aria-hidden={!hasQueueItems}
      className={cn(
        "pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-[380px] flex-col items-end gap-2 transition-all duration-200",
        hasQueueItems ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
      )}
    >
      <div
        className={cn(
          "dataset-upload-uppy w-full overflow-hidden rounded-lg border border-border bg-card/90 shadow-lg backdrop-blur-xl",
          hasQueueItems ? "pointer-events-auto" : "pointer-events-none"
        )}
      >
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <div className="flex size-9 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
            <UploadCloud className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-foreground">上传中心</div>
            <div className="text-xs text-muted-foreground">
              {activeCount > 0 ? `进行中 ${activeCount} 项` : "全部任务已结束"}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {finishedCount > 0 ? (
              <Button
                className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => removeFinishedUploads(uppy)}
                type="button"
                variant="ghost"
              >
                清理已完成
              </Button>
            ) : null}
            <Button
              aria-label={collapsed ? "展开上传中心" : "收起上传中心"}
              className="size-8 text-muted-foreground hover:text-foreground"
              onClick={() => onCollapsedChange((current) => !current)}
              size="icon"
              type="button"
              variant="ghost"
            >
              {collapsed ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        <UppyContextProvider uppy={uppyContext}>
          <div className="px-3 py-3">
            <div
              aria-hidden={collapsed}
              className={cn("max-h-[240px] overflow-y-auto pr-1", collapsed && "hidden")}
            >
              <FilesList />
            </div>
            <StatusBar
              hideAfterFinish={false}
              hideCancelButton
              hidePauseResumeButton
              hideUploadButton
              locale={statusBarLocale}
              showProgressDetails
              uppy={uppy}
            />
          </div>
        </UppyContextProvider>
      </div>
    </div>
  );
}

export function DatasetUploadManagerProvider({
  children
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [uppy] = React.useState(() => createDatasetUploadUppy());
  const [collapsed, setCollapsed] = React.useState(false);
  const uppyFiles = useUppyState(uppy, (state) => Object.values(state.files));
  const queueItems = React.useMemo(() => normalizeQueueItems(uppyFiles), [uppyFiles]);

  const uploadFiles = React.useCallback(
    async (fileIDs: string[]) => {
      const files = fileIDs
        .map((fileId) => uppy.getFile(fileId))
        .filter(Boolean) as DatasetUploadUppyFile[];

      if (files.length === 0) {
        return;
      }

      uppy.emit("upload-start", files);

      await Promise.all(
        files.map(async (file) => {
          const prepared = file.meta.prepared;
          const uploadFile = file.data instanceof File ? file.data : null;

          if (!prepared || !uploadFile) {
            const error = new Error("上传任务缺少直传初始化信息");
            touchFileMeta(uppy, file.id);
            const latest = uppy.getFile(file.id);
            if (latest) {
              uppy.emit("upload-error", latest, error);
            }
            toast.error(error.message);
            return;
          }

          try {
            const upload = await uploadFileWithDirectUpload({
              file: uploadFile,
              initResponse: prepared.upload,
              onProgress: ({ uploadedBytes, totalBytes }) => {
                const latest = uppy.getFile(file.id);
                if (!latest) {
                  return;
                }

                touchFileMeta(uppy, file.id);
                uppy.emit("upload-progress", latest, {
                  bytesUploaded: uploadedBytes,
                  bytesTotal: totalBytes,
                  uploadStarted:
                    typeof latest.progress.uploadStarted === "number"
                      ? latest.progress.uploadStarted
                      : Date.now()
                });
              }
            });

            const latest = uppy.getFile(file.id);
            if (!latest) {
              return;
            }

            touchFileMeta(uppy, file.id);
            uppy.emit("upload-success", latest, {
              status: 200,
              body: upload as DatasetUploadBody,
              uploadURL: upload.uri
            });
          } catch (error) {
            const message = error instanceof Error ? error.message : "上传数据集失败";

            try {
              await failDatasetDirectUpload(prepared.datasetId, prepared.versionId, {
                reason: message
              });
            } catch {
              // Ignore fail-backfill errors; the user still needs the upload error surfaced.
            }

            const latest = uppy.getFile(file.id);
            if (latest) {
              touchFileMeta(uppy, file.id);
              uppy.emit("upload-error", latest, new Error(message));
            }

            toast.error(message);
            router.refresh();
          }
        })
      );
    },
    [router, uppy]
  );

  const finalizeUploads = React.useCallback(
    async (fileIDs: string[]) => {
      await Promise.all(
        fileIDs.map(async (fileId) => {
          const file = uppy.getFile(fileId);
          if (!file || file.error) {
            return;
          }

          const prepared = file.meta.prepared;
          const upload = file.response?.body;

          if (!prepared || !upload) {
            return;
          }

          try {
            touchFileMeta(uppy, fileId);
            uppy.emit("postprocess-progress", file, {
              mode: "indeterminate",
              message: "后台处理中"
            });

            const finalized = await completeDatasetDirectUpload(prepared.datasetId, prepared.versionId, {
              upload
            });

            if (finalized.status !== "ready") {
              await waitForDatasetVersionReady({
                uppy,
                fileId,
                datasetId: prepared.datasetId,
                versionId: prepared.versionId
              });
            }

            const latest = uppy.getFile(fileId);
            if (latest) {
              touchFileMeta(uppy, fileId);
              uppy.emit("postprocess-complete", latest);
            }

            router.refresh();
          } catch (error) {
            const message = error instanceof Error ? error.message : "后台导入失败";

            try {
              await failDatasetDirectUpload(prepared.datasetId, prepared.versionId, {
                reason: message
              });
            } catch {
              // Ignore fail-backfill errors; the status row should still surface the failure.
            }

            const latest = uppy.getFile(fileId);
            if (latest) {
              touchFileMeta(uppy, fileId);
              uppy.emit("upload-error", latest, new Error(message));
              uppy.emit("postprocess-complete", latest);
            }

            toast.error(message);
            router.refresh();
          }
        })
      );
    },
    [router, uppy]
  );

  React.useEffect(() => {
    uppy.addUploader(uploadFiles);
    uppy.addPostProcessor(finalizeUploads);

    return () => {
      uppy.removeUploader(uploadFiles);
      uppy.removePostProcessor(finalizeUploads);
    };
  }, [finalizeUploads, uploadFiles, uppy]);

  const startDatasetCreateUpload = React.useCallback(
    async (input: {
      name: string;
      description?: string | null;
      purpose: string;
      format: string;
      use_case?: string | null;
      modality?: string | null;
      recipe?: string | null;
      scope: string;
      tags: string[];
      file: File;
    }) => {
      const prepared = await prepareDatasetDirectUpload({
        name: input.name,
        description: input.description ?? null,
        purpose: input.purpose,
        format: input.format,
        use_case: input.use_case ?? null,
        modality: input.modality ?? null,
        recipe: input.recipe ?? null,
        scope: input.scope,
        tags: input.tags,
        file_name: input.file.name,
        file_size: input.file.size,
        content_type: input.file.type || null
      }).catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "创建数据集失败";
        toast.error(message);
        throw error;
      });

      const taskId = buildPendingUploadTaskId("create-dataset");
      const now = Date.now();

      uppy.addFile({
        id: taskId,
        source: "Dataset",
        name: input.file.name,
        type: input.file.type || "application/octet-stream",
        data: input.file,
        meta: {
          taskId,
          operation: "create-dataset",
          datasetName: input.name,
          description: input.description ?? null,
          purpose: input.purpose,
          format: input.format,
          useCase: input.use_case ?? null,
          modality: input.modality ?? null,
          recipe: input.recipe ?? null,
          scope: input.scope,
          versionLabel: "V1",
          versionNumber: 1,
          createdAt: new Date(now).toISOString(),
          updatedAt: now,
          prepared: {
            datasetId: prepared.dataset_id,
            versionId: prepared.version_id,
            upload: prepared.upload
          }
        }
      });

      setCollapsed(false);
      void uppy.upload().catch(() => undefined);

      return {
        datasetId: prepared.dataset_id,
        versionId: prepared.version_id
      };
    },
    [uppy]
  );

  const startDatasetVersionUpload = React.useCallback(
    async (input: {
      datasetId: string;
      datasetName: string;
      versionLabel: string;
      description?: string | null;
      format?: string | null;
      file: File;
    }) => {
      const prepared = await prepareDatasetVersionDirectUpload(input.datasetId, {
        description: input.description ?? null,
        format: input.format ?? null,
        file_name: input.file.name,
        file_size: input.file.size,
        content_type: input.file.type || null
      }).catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "创建数据集版本失败";
        toast.error(message);
        throw error;
      });

      const taskId = buildPendingUploadTaskId("create-version");
      const now = Date.now();
      const versionNumber = Number.parseInt(input.versionLabel.replace(/^V/i, ""), 10) || 1;

      uppy.addFile({
        id: taskId,
        source: "Dataset",
        name: input.file.name,
        type: input.file.type || "application/octet-stream",
        data: input.file,
        meta: {
          taskId,
          operation: "create-version",
          datasetName: input.datasetName,
          description: input.description ?? null,
          purpose: null,
          format: input.format ?? null,
          useCase: null,
          modality: input.format ?? null,
          recipe: null,
          scope: "my-datasets",
          versionLabel: input.versionLabel,
          versionNumber,
          createdAt: new Date(now).toISOString(),
          updatedAt: now,
          prepared: {
            datasetId: prepared.dataset_id,
            versionId: prepared.version_id,
            upload: prepared.upload
          }
        }
      });

      setCollapsed(false);
      void uppy.upload().catch(() => undefined);
    },
    [uppy]
  );

  const contextValue = React.useMemo<DatasetUploadManagerContextValue>(
    () => ({
      startDatasetCreateUpload,
      startDatasetVersionUpload
    }),
    [startDatasetCreateUpload, startDatasetVersionUpload]
  );

  return (
    <DatasetUploadManagerContext.Provider value={contextValue}>
      <DatasetUploadQueueItemsContext.Provider value={queueItems}>
        {children}
        <DatasetUploadCenter
          collapsed={collapsed}
          onCollapsedChange={setCollapsed}
          queueItems={queueItems}
          uppy={uppy}
        />
      </DatasetUploadQueueItemsContext.Provider>
    </DatasetUploadManagerContext.Provider>
  );
}

export function useDatasetUploadManager() {
  const context = React.useContext(DatasetUploadManagerContext);
  if (!context) {
    throw new Error("useDatasetUploadManager must be used within DatasetUploadManagerProvider");
  }
  return context;
}

export function useDatasetUploadQueueItems() {
  return React.useContext(DatasetUploadQueueItemsContext);
}
