"use client";

import { ChevronDown, ChevronUp, Database, FolderUp, HardDrive, Loader2, Trash2, UploadCloud } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  abortLakeUploadsKeepalive,
  completeLakeAssetDirectUpload,
  createLakeBatch,
  deleteLakeAsset,
  failLakeAssetDirectUpload,
  prepareLakeAssetDirectUpload
} from "@/features/lake/api";
import { cn } from "@/lib/utils";
import type {
  LakeAssetSummary,
  LakeBatchSummary,
  ObjectStoreUploadResponse
} from "@/types/api";

type UploadLifecycleStatus = "preparing" | "uploading" | "finalizing";
type UploadQueueItemStatus = "queued" | UploadLifecycleStatus | "completed" | "failed";

type UploadQueueItem = {
  id: string;
  assetId?: string | null;
  label: string;
  sizeBytes: number;
  uploadedBytes: number;
  status: UploadQueueItemStatus;
  error?: string | null;
};

export function DataLakePanel({
  initialAssets,
  initialBatches
}: {
  initialAssets: LakeAssetSummary[];
  initialBatches: LakeBatchSummary[];
}) {
  const router = useRouter();
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const folderInputRef = React.useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [uploadQueue, setUploadQueue] = React.useState<UploadQueueItem[]>([]);
  const [uploadQueueExpanded, setUploadQueueExpanded] = React.useState(false);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [deletingAssetId, setDeletingAssetId] = React.useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = React.useState<LakeAssetSummary | null>(null);
  const activeBatchIdRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!folderInputRef.current) {
      return;
    }
    folderInputRef.current.setAttribute("webkitdirectory", "");
    folderInputRef.current.setAttribute("directory", "");
  }, []);

  const totalSizeBytes = initialAssets.reduce((sum, asset) => sum + (asset.size_bytes ?? 0), 0);
  const readyAssets = initialAssets.filter((asset) => asset.status === "ready").length;
  const uploadingAssets = initialAssets.filter((asset) => asset.status === "uploading").length;
  const uploadQueueSummary = React.useMemo(() => {
    if (uploadQueue.length === 0) {
      return null;
    }

    let uploadedBytes = 0;
    let totalBytes = 0;
    let completedFiles = 0;
    let failedFiles = 0;

    for (const item of uploadQueue) {
      uploadedBytes += item.uploadedBytes;
      totalBytes += item.sizeBytes;
      if (item.status === "completed") {
        completedFiles += 1;
      } else if (item.status === "failed") {
        failedFiles += 1;
      }
    }

    const activeItem =
      uploadQueue.find((item) => ["preparing", "uploading", "finalizing"].includes(item.status)) ??
      uploadQueue.find((item) => item.status === "failed") ??
      uploadQueue.at(-1) ??
      null;

    return {
      activeItem,
      completedFiles,
      failedFiles,
      totalFiles: uploadQueue.length,
      totalBytes,
      uploadedBytes
    };
  }, [uploadQueue]);

  const handleDeleteAsset = React.useCallback(
    async (asset: LakeAssetSummary) => {
      setDeletingAssetId(asset.id);
      try {
        await deleteLakeAsset(asset.id);
        toast.success(
          asset.resource_type === "folder"
            ? `已删除文件夹 ${asset.name}`
            : `已删除资产 ${asset.name}`
        );
        router.refresh();
      } catch (error) {
        const message = error instanceof Error ? error.message : "删除资产失败";
        toast.error(message);
      } finally {
        setDeletingAssetId(null);
        setConfirmTarget(null);
      }
    },
    [router]
  );

  const updateUploadQueueItem = React.useCallback(
    (id: string, updater: UploadQueueItem | ((item: UploadQueueItem) => UploadQueueItem)) => {
      setUploadQueue((current) =>
        current.map((item) => {
          if (item.id !== id) {
            return item;
          }
          return typeof updater === "function" ? updater(item) : updater;
        })
      );
    },
    []
  );

  React.useEffect(() => {
    const handlePageHide = () => {
      const pendingAssetIds = uploadQueue
        .filter(
          (item) =>
            !!item.assetId &&
            item.status !== "completed" &&
            item.status !== "failed"
        )
        .map((item) => item.assetId as string);

      if (!activeBatchIdRef.current && pendingAssetIds.length === 0) {
        return;
      }

      abortLakeUploadsKeepalive({
        batchId: activeBatchIdRef.current,
        assetIds: pendingAssetIds,
        reason: "页面刷新或离开导致上传中断"
      });
    };

    window.addEventListener("pagehide", handlePageHide);
    return () => {
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, [uploadQueue]);

  const handleSelectedFiles = React.useCallback(
    async (selectedFiles: FileList | File[]) => {
      const files = Array.from(selectedFiles);
      if (files.length === 0) {
        return;
      }

      setUploading(true);
      setNotice(null);
      const queue = files.map((file, index) => ({
        id: buildUploadQueueItemId(file, index),
        label: getRelativeUploadPath(file) ?? file.name,
        sizeBytes: file.size,
        uploadedBytes: 0,
        status: "queued" as const,
        error: null
      }));
      setUploadQueue(queue);
      setUploadQueueExpanded(files.length <= 8);

      try {
        const batch = await createLakeBatch({
          name: buildLakeBatchName(files),
          description: buildLakeBatchDescription(files),
          planned_file_count: files.length,
          source_type: "upload",
          resource_type: inferBatchResourceType(files),
          root_paths: deriveRootFolderPaths(files)
        });
        activeBatchIdRef.current = batch.id;

        for (const [index, file] of files.entries()) {
          const queueItem = queue[index];
          const relativePath = getRelativeUploadPath(file);
          let assetId: string | null = null;

          try {
            updateUploadQueueItem(queueItem.id, {
              ...queueItem,
              status: "preparing",
              uploadedBytes: 0,
              error: null
            });

            const init = await prepareLakeAssetDirectUpload({
              batch_id: batch.id,
              source_type: "upload",
              resource_type: inferResourceType(file),
              file_name: file.name,
              file_size: file.size,
              content_type: file.type || null,
              relative_path: relativePath ?? null
            });
            assetId = init.asset_id;
            updateUploadQueueItem(queueItem.id, (item) => ({
              ...item,
              assetId: init.asset_id
            }));

            await uploadBlobWithProgress({
              file,
              headers: init.upload.headers,
              onProgress: (uploadedBytes, totalBytes) => {
                updateUploadQueueItem(queueItem.id, (item) => ({
                  ...item,
                  status: "uploading",
                  uploadedBytes: Math.min(totalBytes, uploadedBytes),
                  error: null
                }));
              },
              url: init.upload.url
            });

            updateUploadQueueItem(queueItem.id, (item) => ({
              ...item,
              status: "finalizing",
              uploadedBytes: item.sizeBytes,
              error: null
            }));

            const uploadPayload: ObjectStoreUploadResponse = {
              bucket: init.upload.bucket,
              object_key: init.upload.object_key,
              uri: init.upload.uri,
              file_name: init.upload.file_name,
              size_bytes: file.size,
              content_type: init.upload.content_type ?? file.type ?? null,
              last_modified: new Date().toISOString()
            };
            await completeLakeAssetDirectUpload(assetId, { upload: uploadPayload });

            updateUploadQueueItem(queueItem.id, (item) => ({
              ...item,
              status: "completed",
              uploadedBytes: item.sizeBytes,
              error: null
            }));
          } catch (error) {
            const message = error instanceof Error ? error.message : "数据湖上传失败";
            if (assetId) {
              void failLakeAssetDirectUpload(assetId, { reason: message });
            }
            updateUploadQueueItem(queueItem.id, (item) => ({
              ...item,
              status: "failed",
              error: message
            }));
          }
        }

        setNotice(buildUploadNotice(files));
        router.refresh();
      } catch (error) {
        const message = error instanceof Error ? error.message : "初始化数据湖上传失败";
        toast.error(message);
      } finally {
        activeBatchIdRef.current = null;
        setUploading(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        if (folderInputRef.current) {
          folderInputRef.current.value = "";
        }
      }
    },
    [router, updateUploadQueueItem]
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <SummaryCard
          label="导入批次"
          value={initialBatches.length}
          hint="按一次投递组织文件或文件夹"
          icon={Database}
        />
        <SummaryCard
          label="资产文件"
          value={initialAssets.length}
          hint={`${readyAssets} 个已就绪${uploadingAssets ? `，${uploadingAssets} 个上传中` : ""}`}
          icon={UploadCloud}
        />
        <SummaryCard
          label="原始体量"
          value={formatFileSize(totalSizeBytes)}
          hint="当前 raw 层登记的对象大小"
          icon={HardDrive}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button disabled={uploading} onClick={() => fileInputRef.current?.click()} size="sm">
          {uploading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
          导入文件
        </Button>
        <Button
          disabled={uploading}
          onClick={() => folderInputRef.current?.click()}
          size="sm"
          variant="secondary"
        >
          <FolderUp className="mr-1.5 h-3.5 w-3.5" />
          导入文件夹
        </Button>
        <Link href="/data">
          <Button size="sm" type="button" variant="outline">
            浏览对象层
          </Button>
        </Link>
        <Link href="/lake-assets">
          <Button size="sm" type="button" variant="outline">
            资产管理
          </Button>
        </Link>
      </div>

      <input
        ref={fileInputRef}
        className="hidden"
        multiple
        onChange={(event) => {
          if (event.target.files) {
            void handleSelectedFiles(event.target.files);
          }
        }}
        type="file"
      />
      <input
        ref={folderInputRef}
        className="hidden"
        multiple
        onChange={(event) => {
          if (event.target.files) {
            void handleSelectedFiles(event.target.files);
          }
        }}
        type="file"
      />

      {uploadQueueSummary ? (
        <Card className="border-slate-800/80 bg-[rgba(12,18,27,0.78)]">
          <CardHeader className="space-y-0 border-b border-slate-800/80 pb-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle className="text-sm text-slate-100">当前投递</CardTitle>
                <div className="mt-1 text-xs text-slate-500">
                  {buildUploadQueueSummaryLabel(uploadQueueSummary)}
                </div>
              </div>
              <Button
                className="h-7 w-7 rounded-md p-0 text-slate-400"
                onClick={() => setUploadQueueExpanded((value) => !value)}
                size="sm"
                type="button"
                variant="ghost"
              >
                {uploadQueueExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {notice ? <div className="text-xs text-emerald-300">{notice}</div> : null}
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3 text-xs text-slate-400">
                <span className="truncate">
                  {uploadQueueSummary.activeItem
                    ? `${renderUploadQueueStatusLabel(uploadQueueSummary.activeItem.status)} · ${uploadQueueSummary.activeItem.label}`
                    : "等待上传"}
                </span>
                <span className="shrink-0">
                  {formatUploadPercent(
                    uploadQueueSummary.uploadedBytes,
                    uploadQueueSummary.totalBytes
                  )}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-900">
                <div
                  className="h-full rounded-full bg-emerald-300 transition-[width] duration-200"
                  style={{
                    width: `${calculateUploadPercent(
                      uploadQueueSummary.uploadedBytes,
                      uploadQueueSummary.totalBytes
                    )}%`
                  }}
                />
              </div>
              <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                <span>
                  {uploadQueueSummary.completedFiles}/{uploadQueueSummary.totalFiles} 个文件
                  {uploadQueueSummary.failedFiles
                    ? `，失败 ${uploadQueueSummary.failedFiles} 个`
                    : ""}
                </span>
                <span>
                  {formatFileSize(uploadQueueSummary.uploadedBytes)} /{" "}
                  {formatFileSize(uploadQueueSummary.totalBytes)}
                </span>
              </div>
            </div>
            {uploadQueueExpanded ? (
              <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
                {uploadQueue.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-slate-800/80 bg-slate-950/60 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-slate-100">{item.label}</div>
                        <div className="text-xs text-slate-500">
                          {renderUploadQueueStatusLabel(item.status)}
                          {item.error ? ` · ${item.error}` : ""}
                        </div>
                      </div>
                      <div className="text-xs text-slate-400">
                        {formatUploadPercent(item.uploadedBytes, item.sizeBytes)}
                      </div>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-slate-900">
                      <div
                        className={cn(
                          "h-full rounded-full transition-[width] duration-200",
                          item.status === "failed" ? "bg-rose-400" : "bg-emerald-300"
                        )}
                        style={{ width: `${calculateUploadPercent(item.uploadedBytes, item.sizeBytes)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-500">
                大批量文件默认折叠显示，展开可查看每个文件的上传进度。
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-slate-800/80 bg-[rgba(12,18,27,0.78)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-slate-100">最近批次</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Table>
            <TableHeader className="bg-transparent">
              <TableRow className="border-slate-800/80 hover:bg-transparent">
                <TableHead>批次</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>文件数</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {initialBatches.length === 0 ? (
                <EmptyRow colSpan={5} message="还没有数据湖投递记录" />
              ) : (
                initialBatches.slice(0, 8).map((batch) => (
                  <TableRow key={batch.id} className="border-slate-800/70">
                    <TableCell className="align-top">
                      <div className="space-y-0.5">
                        <div className="font-medium text-slate-100">{batch.name}</div>
                        <div className="text-xs text-slate-500">{batch.id}</div>
                      </div>
                    </TableCell>
                    <TableCell className="text-slate-300">{renderStatusLabel(batch.status)}</TableCell>
                    <TableCell className="text-slate-300">
                      {batch.completed_file_count}/{batch.planned_file_count}
                      {batch.failed_file_count ? `，失败 ${batch.failed_file_count}` : ""}
                    </TableCell>
                    <TableCell className="text-slate-300">
                      {batch.resource_type || "document"} · {batch.source_type}
                    </TableCell>
                    <TableCell className="text-slate-400">
                      {formatDateTime(batch.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="border-slate-800/80 bg-[rgba(12,18,27,0.78)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-slate-100">最近资产</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Table>
            <TableHeader className="bg-transparent">
              <TableRow className="border-slate-800/80 hover:bg-transparent">
                <TableHead>文件</TableHead>
                <TableHead>批次</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>大小</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>导入时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {initialAssets.length === 0 ? (
                <EmptyRow colSpan={7} message="导入文件或文件夹后，这里会显示 raw 层资产。" />
              ) : (
                initialAssets.slice(0, 12).map((asset) => (
                  <TableRow key={asset.id} className="border-slate-800/70">
                    <TableCell className="align-top">
                      <div className="space-y-0.5">
                        <div className="font-medium text-slate-100">{asset.name}</div>
                        {asset.relative_path ? (
                          <div className="truncate text-xs text-slate-500">
                            {asset.relative_path}
                          </div>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="text-slate-300">{asset.batch_name}</TableCell>
                    <TableCell className="text-slate-300">
                      {asset.resource_type === "folder"
                        ? "目录"
                        : `${asset.resource_type || "document"} · ${asset.format || "bin"}`}
                    </TableCell>
                    <TableCell className="text-slate-300">
                      {asset.resource_type === "folder"
                        ? "目录"
                        : formatFileSize(asset.size_bytes ?? 0)}
                    </TableCell>
                    <TableCell className="text-slate-300">{renderStatusLabel(asset.status)}</TableCell>
                    <TableCell className="text-slate-400">{formatDateTime(asset.created_at)}</TableCell>
                    <TableCell className="whitespace-nowrap text-right">
                      <Button
                        className="h-7 min-w-[72px] gap-1.5 whitespace-nowrap"
                        disabled={deletingAssetId === asset.id}
                        onClick={() => setConfirmTarget(asset)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        {deletingAssetId === asset.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open && deletingAssetId === null) {
            setConfirmTarget(null);
          }
        }}
        open={confirmTarget !== null}
      >
        <AlertDialogContent className="max-w-md border-slate-800 bg-[rgba(10,15,23,0.96)] text-slate-100">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmTarget?.resource_type === "folder" ? "删除文件夹资产" : "删除资产"}
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-3 text-sm text-slate-400">
              <span className="block">
                {confirmTarget?.resource_type === "folder"
                  ? `删除后将移除文件夹「${confirmTarget?.name ?? ""}」及其全部内容，该操作不可恢复。`
                  : `删除后将移除资产「${confirmTarget?.name ?? ""}」，该操作不可恢复。`}
              </span>
              <span className="block rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-xs text-slate-300">
                <span className="block font-medium text-slate-100">
                  {confirmTarget?.resource_type === "folder" ? "删除范围" : "目标资产"}
                </span>
                <span className="mt-1 block truncate">
                  {confirmTarget?.relative_path || confirmTarget?.name || ""}
                </span>
                <span className="mt-1 block text-slate-500">
                  批次：{confirmTarget?.batch_name ?? ""}
                </span>
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingAssetId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="min-w-[96px] bg-rose-600 text-white hover:bg-rose-500"
              disabled={deletingAssetId !== null}
              onClick={() => {
                if (confirmTarget) {
                  void handleDeleteAsset(confirmTarget);
                }
              }}
            >
              {deletingAssetId !== null ? (
                <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  删除中...
                </span>
              ) : confirmTarget?.resource_type === "folder" ? (
                "删除文件夹"
              ) : (
                "确认删除"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  hint,
  label,
  value
}: {
  icon: typeof Database;
  hint: string;
  label: string;
  value: number | string;
}) {
  return (
    <Card className="border-slate-800/80 bg-[rgba(12,18,27,0.78)]">
      <CardContent className="flex items-start justify-between gap-3 p-4">
        <div className="space-y-1">
          <div className="text-[12px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
          <div className="text-2xl font-semibold text-slate-50">{value}</div>
          <div className="text-xs text-slate-500">{hint}</div>
        </div>
        <div className="rounded-full border border-slate-800 bg-slate-950/80 p-2 text-slate-300">
          <Icon className="h-4 w-4" />
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <TableRow className="border-slate-800/70">
      <TableCell className="py-10 text-center text-sm text-slate-500" colSpan={colSpan}>
        {message}
      </TableCell>
    </TableRow>
  );
}

function getRelativeUploadPath(file: File) {
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath?.trim();
  return relativePath ? relativePath.replace(/^\/+/, "") : null;
}

function buildLakeBatchName(files: File[]) {
  const rootFolder = files
    .map((file) => getRelativeUploadPath(file)?.split("/").filter(Boolean)[0] ?? null)
    .find(Boolean);
  if (rootFolder) {
    return `资料导入 · ${rootFolder}`;
  }
  if (files.length === 1) {
    return `资料导入 · ${files[0].name}`;
  }
  return `资料批量导入 · ${new Date().toLocaleString("zh-CN", { hour12: false })}`;
}

function buildLakeBatchDescription(files: File[]) {
  if (files.length === 1) {
    return `从本地导入 1 个文件：${files[0].name}`;
  }
  return `从本地导入 ${files.length} 个文件`;
}

function inferResourceType(file: File) {
  const fileName = file.name.toLowerCase();
  if (
    file.type.startsWith("image/") ||
    [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"].some((suffix) => fileName.endsWith(suffix))
  ) {
    return "image";
  }
  if ([".csv", ".tsv", ".xls", ".xlsx", ".parquet"].some((suffix) => fileName.endsWith(suffix))) {
    return "tabular";
  }
  if ([".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"].some((suffix) => fileName.endsWith(suffix))) {
    return "archive";
  }
  return "document";
}

function inferBatchResourceType(files: File[]) {
  const resourceTypes = new Set(files.map(inferResourceType));
  if (resourceTypes.size === 1) {
    return Array.from(resourceTypes)[0];
  }
  return "mixed";
}

function buildUploadQueueItemId(file: File, index: number) {
  return [getRelativeUploadPath(file) ?? file.name, file.size, file.lastModified, index].join(":");
}

function renderUploadQueueStatusLabel(status: UploadQueueItemStatus) {
  if (status === "queued") {
    return "等待上传";
  }
  if (status === "preparing") {
    return "准备上传";
  }
  if (status === "uploading") {
    return "上传中";
  }
  if (status === "finalizing") {
    return "登记资产";
  }
  if (status === "completed") {
    return "已完成";
  }
  return "上传失败";
}

function buildUploadNotice(files: File[]) {
  const rootFolders = new Set(
    files
      .map((file) => getRelativeUploadPath(file)?.split("/").filter(Boolean)[0] ?? null)
      .filter((value): value is string => Boolean(value))
  );

  if (rootFolders.size === 1) {
    return `已导入文件夹 ${Array.from(rootFolders)[0]}（${files.length} 个文件）`;
  }
  if (files.length === 1) {
    return `已导入 ${files[0].name}`;
  }
  return `已导入 ${files.length} 个文件`;
}

function deriveRootFolderPaths(files: File[]) {
  const rootPaths = new Set<string>();
  for (const file of files) {
    const relativePath = getRelativeUploadPath(file);
    if (!relativePath) {
      continue;
    }
    const rootPath = relativePath.split("/").filter(Boolean)[0];
    if (rootPath) {
      rootPaths.add(rootPath);
    }
  }
  return Array.from(rootPaths);
}

function buildUploadQueueSummaryLabel(summary: {
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
}) {
  if (summary.failedFiles > 0) {
    return `已完成 ${summary.completedFiles}/${summary.totalFiles}，失败 ${summary.failedFiles} 个`;
  }
  if (summary.completedFiles >= summary.totalFiles) {
    return `已完成 ${summary.completedFiles}/${summary.totalFiles}`;
  }
  return `正在上传 ${summary.completedFiles}/${summary.totalFiles}`;
}

function calculateUploadPercent(uploadedBytes: number, totalBytes: number) {
  if (totalBytes <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)));
}

function formatUploadPercent(uploadedBytes: number, totalBytes: number) {
  return `${calculateUploadPercent(uploadedBytes, totalBytes)}%`;
}

function formatFileSize(bytes: number) {
  if (bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(new Date(value));
}

function renderStatusLabel(status: string) {
  if (status === "ready") {
    return "已就绪";
  }
  if (status === "uploading") {
    return "上传中";
  }
  if (status === "partial") {
    return "部分完成";
  }
  if (status === "failed") {
    return "失败";
  }
  return status;
}

function uploadBlobWithProgress(params: {
  url: string;
  file: Blob;
  headers?: Record<string, string>;
  onProgress?: (uploadedBytes: number, totalBytes: number) => void;
}) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", params.url);

    for (const [key, value] of Object.entries(params.headers ?? {})) {
      request.setRequestHeader(key, value);
    }

    request.upload.onprogress = (event) => {
      if (!params.onProgress) {
        return;
      }
      const totalBytes = event.lengthComputable ? event.total : params.file.size;
      params.onProgress(event.loaded, totalBytes);
    };

    request.onerror = () => {
      reject(new Error("对象存储上传失败，请检查直传地址和 RustFS 配置"));
    };
    request.onabort = () => {
      reject(new Error("对象存储上传已中止"));
    };
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`对象存储上传失败: ${request.status} ${request.statusText}`));
        return;
      }
      params.onProgress?.(params.file.size, params.file.size);
      resolve();
    };

    request.send(params.file);
  });
}
