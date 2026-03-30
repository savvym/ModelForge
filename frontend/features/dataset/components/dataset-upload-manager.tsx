"use client";

import * as React from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  UploadCloud,
  X
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  completeDatasetDirectUpload,
  failDatasetDirectUpload,
  getDataset,
  prepareDatasetDirectUpload,
  prepareDatasetVersionDirectUpload
} from "@/features/dataset/api";
import { uploadFileWithDirectUpload } from "@/features/dataset/direct-upload";
import { cn } from "@/lib/utils";

type QueueItemStatus = "preparing" | "uploading" | "processing" | "completed" | "failed";
type QueueItemOperation = "create-dataset" | "create-version";

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

type DatasetUploadManagerStoreState = {
  items: DatasetUploadQueueItem[];
  collapsed: boolean;
  ownerId: string | null;
};

const DatasetUploadManagerContext = React.createContext<DatasetUploadManagerContextValue | null>(
  null
);

const STATUS_LABELS: Record<QueueItemStatus, string> = {
  preparing: "准备上传",
  uploading: "上传中",
  processing: "后台处理中",
  completed: "上传完成",
  failed: "上传失败"
};

const storeListeners = new Set<() => void>();
const mountedProviderIds: string[] = [];
let storeState: DatasetUploadManagerStoreState = {
  items: [],
  collapsed: false,
  ownerId: null
};

function emitStoreChange() {
  storeListeners.forEach((listener) => listener());
}

function subscribeStore(listener: () => void) {
  storeListeners.add(listener);
  return () => {
    storeListeners.delete(listener);
  };
}

function getStoreSnapshot() {
  return storeState;
}

function normalizeItems(items: DatasetUploadQueueItem[]) {
  return [...items].sort((left, right) => right.updatedAt - left.updatedAt);
}

function buildPendingUploadTaskId(prefix: QueueItemOperation) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}:${crypto.randomUUID()}`;
  }

  return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`;
}

function setStoreState(
  updater:
    | DatasetUploadManagerStoreState
    | ((current: DatasetUploadManagerStoreState) => DatasetUploadManagerStoreState)
) {
  const nextState = typeof updater === "function" ? updater(storeState) : updater;
  storeState = {
    ...nextState,
    items: normalizeItems(nextState.items)
  };
  emitStoreChange();
}

function updateStoreItem(
  itemId: string,
  updater:
    | Partial<DatasetUploadQueueItem>
    | ((item: DatasetUploadQueueItem) => DatasetUploadQueueItem)
) {
  setStoreState((current) => ({
    ...current,
    items: current.items.map((item) => {
      if (item.id !== itemId) {
        return item;
      }

      return typeof updater === "function"
        ? updater(item)
        : {
            ...item,
            ...updater,
            updatedAt: Date.now()
          };
    })
  }));
}

function upsertStoreItem(item: DatasetUploadQueueItem) {
  setStoreState((current) => ({
    ...current,
    items: [item, ...current.items.filter((entry) => entry.id !== item.id)]
  }));
}

function dismissStoreItem(itemId: string) {
  setStoreState((current) => ({
    ...current,
    items: current.items.filter((item) => item.id !== itemId)
  }));
}

function clearFinishedStoreItems() {
  setStoreState((current) => ({
    ...current,
    items: current.items.filter((item) => item.status !== "completed" && item.status !== "failed")
  }));
}

function setStoreCollapsed(
  value: boolean | ((current: boolean) => boolean)
) {
  setStoreState((current) => ({
    ...current,
    collapsed: typeof value === "function" ? value(current.collapsed) : value
  }));
}

function registerProvider(providerId: string) {
  if (!mountedProviderIds.includes(providerId)) {
    mountedProviderIds.push(providerId);
  }

  if (!storeState.ownerId) {
    setStoreState((current) => ({
      ...current,
      ownerId: providerId
    }));
  }
}

function unregisterProvider(providerId: string) {
  const index = mountedProviderIds.indexOf(providerId);
  if (index >= 0) {
    mountedProviderIds.splice(index, 1);
  }

  if (storeState.ownerId === providerId) {
    setStoreState((current) => ({
      ...current,
      ownerId: mountedProviderIds[0] ?? null
    }));
  }
}

export function DatasetUploadManagerProvider({
  children
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const store = React.useSyncExternalStore(subscribeStore, getStoreSnapshot, getStoreSnapshot);
  const providerIdRef = React.useRef(
    `dataset-upload-provider-${Math.random().toString(36).slice(2, 10)}`
  );
  const pollTimersRef = React.useRef<Record<string, number>>({});

  React.useEffect(() => {
    const providerId = providerIdRef.current;
    registerProvider(providerId);

    return () => {
      Object.values(pollTimersRef.current).forEach((timeoutId) => window.clearTimeout(timeoutId));
      pollTimersRef.current = {};
      unregisterProvider(providerId);
    };
  }, []);

  const stopPolling = React.useCallback((itemId: string) => {
    const timeoutId = pollTimersRef.current[itemId];
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      delete pollTimersRef.current[itemId];
    }
  }, []);

  const schedulePoll = React.useCallback(
    (item: { id: string; datasetId: string; versionId: string }) => {
      const poll = async () => {
        try {
          const dataset = await getDataset(item.datasetId);
          const version = dataset.versions.find((entry) => entry.id === item.versionId);
          if (!version) {
            throw new Error("数据集版本不存在");
          }

          if (version.status === "ready") {
            stopPolling(item.id);
            updateStoreItem(item.id, (current) => ({
              ...current,
              status: "completed",
              uploadedBytes: current.sizeBytes,
              updatedAt: Date.now()
            }));
            router.refresh();
            return;
          }

          if (version.status === "failed") {
            stopPolling(item.id);
            updateStoreItem(item.id, {
              status: "failed",
              error: "后台导入失败"
            });
            router.refresh();
            return;
          }

          updateStoreItem(item.id, {
            status: "processing"
          });
        } catch {
          // Keep polling on transient refresh failures.
        }

        pollTimersRef.current[item.id] = window.setTimeout(poll, 2500);
      };

      stopPolling(item.id);
      pollTimersRef.current[item.id] = window.setTimeout(poll, 1800);
    },
    [router, stopPolling]
  );

  const runUploadLifecycle = React.useCallback(
    async (params: {
      itemId: string;
      datasetId: string;
      versionId: string;
      file: File;
      prepareResponse: Awaited<ReturnType<typeof prepareDatasetDirectUpload>>;
    }) => {
      try {
        const upload = await uploadFileWithDirectUpload({
          file: params.file,
          initResponse: params.prepareResponse.upload,
          onProgress: ({ status, uploadedBytes }) => {
            updateStoreItem(params.itemId, {
              status: status === "finalizing" ? "uploading" : status,
              uploadedBytes
            });
          }
        });

        updateStoreItem(params.itemId, {
          status: "processing",
          uploadedBytes: params.file.size
        });

        const finalized = await completeDatasetDirectUpload(params.datasetId, params.versionId, {
          upload
        });

        if (finalized.status === "ready") {
          stopPolling(params.itemId);
          updateStoreItem(params.itemId, {
            status: "completed",
            uploadedBytes: params.file.size
          });
          router.refresh();
          return;
        }

        router.refresh();
        schedulePoll({
          id: params.itemId,
          datasetId: params.datasetId,
          versionId: params.versionId
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "上传数据集失败";
        try {
          await failDatasetDirectUpload(params.datasetId, params.versionId, {
            reason: message
          });
        } catch {
          // Ignore fail-backfill errors; the queue item still needs to surface the failure.
        }
        stopPolling(params.itemId);
        updateStoreItem(params.itemId, {
          status: "failed",
          error: message
        });
        router.refresh();
      }
    },
    [router, schedulePoll, stopPolling]
  );

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
      const itemId = buildPendingUploadTaskId("create-dataset");
      const now = Date.now();
      upsertStoreItem({
        id: itemId,
        datasetId: null,
        versionId: null,
        persisted: false,
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
        fileName: input.file.name,
        sizeBytes: input.file.size,
        uploadedBytes: 0,
        status: "preparing",
        operation: "create-dataset",
        error: null,
        createdAt: new Date(now).toISOString(),
        updatedAt: now
      });
      setStoreCollapsed(false);
      try {
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
        });

        updateStoreItem(itemId, (current) => ({
          ...current,
          datasetId: prepared.dataset_id,
          versionId: prepared.version_id,
          persisted: true,
          updatedAt: Date.now()
        }));
        void runUploadLifecycle({
          itemId,
          datasetId: prepared.dataset_id,
          versionId: prepared.version_id,
          file: input.file,
          prepareResponse: prepared
        });

        return {
          datasetId: prepared.dataset_id,
          versionId: prepared.version_id
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : "创建数据集失败";
        updateStoreItem(itemId, {
          status: "failed",
          error: message
        });
        throw error;
      }
    },
    [router, runUploadLifecycle]
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
      });

      const now = Date.now();
      const versionNumber = Number.parseInt(input.versionLabel.replace(/^V/i, ""), 10) || 1;
      upsertStoreItem({
        id: prepared.version_id,
        datasetId: prepared.dataset_id,
        versionId: prepared.version_id,
        persisted: true,
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
        fileName: input.file.name,
        sizeBytes: input.file.size,
        uploadedBytes: 0,
        status: "preparing",
        operation: "create-version",
        error: null,
        createdAt: new Date(now).toISOString(),
        updatedAt: now
      });
      setStoreCollapsed(false);
      router.refresh();
      void runUploadLifecycle({
        itemId: prepared.version_id,
        datasetId: prepared.dataset_id,
        versionId: prepared.version_id,
        file: input.file,
        prepareResponse: prepared
      });

    },
    [router, runUploadLifecycle]
  );

  const contextValue = React.useMemo<DatasetUploadManagerContextValue>(
    () => ({
      startDatasetCreateUpload,
      startDatasetVersionUpload
    }),
    [startDatasetCreateUpload, startDatasetVersionUpload]
  );

  const activeCount = store.items.filter(
    (item) =>
      item.status === "preparing" || item.status === "uploading" || item.status === "processing"
  ).length;
  const isPanelOwner = store.ownerId === providerIdRef.current;

  return (
    <DatasetUploadManagerContext.Provider value={contextValue}>
      {children}
      {isPanelOwner && store.items.length > 0 ? (
        <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex max-w-[360px] flex-col items-end gap-2">
          <div className="pointer-events-auto w-full overflow-hidden rounded-2xl border border-slate-800/90 bg-[rgba(8,12,19,0.96)] shadow-[0_24px_60px_rgba(2,6,23,0.55)] backdrop-blur-xl">
            <div className="flex items-center gap-3 border-b border-slate-800/80 px-4 py-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-sky-500/30 bg-sky-500/10 text-sky-200">
                <UploadCloud className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-100">上传中心</div>
                <div className="text-xs text-slate-500">
                  {activeCount > 0 ? `进行中 ${activeCount} 项` : "全部任务已结束"}
                </div>
              </div>
              <button
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-800/70 hover:text-slate-100"
                onClick={() => setStoreCollapsed((current) => !current)}
                type="button"
              >
                {store.collapsed ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>
            </div>

            {!store.collapsed ? (
              <div className="space-y-3 px-3 py-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>{store.items.length} 个上传任务</span>
                  <button
                    className="transition-colors hover:text-slate-200"
                    onClick={clearFinishedStoreItems}
                    type="button"
                  >
                    清理已完成
                  </button>
                </div>

                <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
                  {store.items.map((item) => {
                    const progress = resolveProgress(item);
                    const canDismiss = item.status === "completed" || item.status === "failed";

                    return (
                      <div
                        className="rounded-2xl border border-slate-800/85 bg-[rgba(15,23,34,0.72)] p-3"
                        key={item.id}
                      >
                        <div className="flex items-start gap-3">
                          <div className={cn("mt-0.5", getStatusIconClassName(item.status))}>
                            {renderStatusIcon(item.status)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-3">
                              <div className="truncate text-sm font-medium text-slate-100">
                                {item.datasetName}
                              </div>
                              {canDismiss ? (
                                <button
                                  className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-800/70 hover:text-slate-100"
                                  onClick={() => {
                                    stopPolling(item.id);
                                    dismissStoreItem(item.id);
                                  }}
                                  type="button"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              ) : null}
                            </div>
                            <div className="mt-1 truncate text-xs text-slate-500">
                              {item.versionLabel} · {item.fileName}
                            </div>
                            <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                              <span className={getStatusTextClassName(item.status)}>
                                {STATUS_LABELS[item.status]}
                              </span>
                              <span className="text-slate-500">
                                {item.status === "processing"
                                  ? "等待后台导入完成"
                                  : `${progress}% · ${formatFileSize(item.sizeBytes)}`}
                              </span>
                            </div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800/90">
                              <div
                                className={cn(
                                  "h-full rounded-full transition-[width] duration-300",
                                  item.status === "failed"
                                    ? "bg-rose-500/80"
                                    : item.status === "completed"
                                      ? "bg-emerald-500/80"
                                      : "bg-sky-500"
                                )}
                                style={{ width: `${progress}%` }}
                              />
                            </div>
                            {item.error ? (
                              <div className="mt-2 text-xs leading-5 text-rose-300">
                                {item.error}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="px-4 py-3 text-xs text-slate-500">
                上传在后台继续，展开可查看每个数据集的进度。
              </div>
            )}
          </div>
        </div>
      ) : null}
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
  return React.useSyncExternalStore(subscribeStore, getStoreSnapshot, getStoreSnapshot).items;
}

function resolveProgress(item: DatasetUploadQueueItem) {
  if (item.status === "processing" || item.status === "completed") {
    return 100;
  }

  if (item.sizeBytes <= 0) {
    return 0;
  }

  return Math.max(2, Math.min(100, Math.round((item.uploadedBytes / item.sizeBytes) * 100)));
}

function renderStatusIcon(status: QueueItemStatus) {
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4" />;
  }

  if (status === "failed") {
    return <AlertCircle className="h-4 w-4" />;
  }

  return <Loader2 className="h-4 w-4 animate-spin" />;
}

function getStatusIconClassName(status: QueueItemStatus) {
  if (status === "completed") {
    return "text-emerald-300";
  }

  if (status === "failed") {
    return "text-rose-300";
  }

  return "text-sky-300";
}

function getStatusTextClassName(status: QueueItemStatus) {
  if (status === "completed") {
    return "text-emerald-300";
  }

  if (status === "failed") {
    return "text-rose-300";
  }

  return "text-sky-300";
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
