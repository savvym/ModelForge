"use client";

import * as React from "react";
import Link from "next/link";
import { FileSearch, MoreHorizontal, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  ConsoleListTableSurface
} from "@/components/console/list-surface";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { deleteDataset } from "@/features/dataset/api";
import {
  formatDatasetFormatLabel,
  getDatasetStatusMeta
} from "@/features/dataset/status";
import {
  useDatasetUploadQueueItems,
  type DatasetUploadQueueItem
} from "@/features/dataset/components/dataset-upload-manager";
import { cn } from "@/lib/utils";
import type { DatasetSummary } from "@/types/api";

export function DatasetListTable({
  datasets
}: {
  datasets: DatasetSummary[];
}) {
  const router = useRouter();
  const uploadItems = useDatasetUploadQueueItems();
  const mergedDatasets = React.useMemo(
    () => mergeDatasetsWithUploads(datasets, uploadItems),
    [datasets, uploadItems]
  );
  const [items, setItems] = React.useState(mergedDatasets);
  const [confirmTarget, setConfirmTarget] = React.useState<DatasetSummary | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setItems(mergedDatasets);
  }, [mergedDatasets]);

  async function handleConfirmDelete() {
    if (!confirmTarget) {
      return;
    }

    setPendingDeleteId(confirmTarget.id);
    setActionError(null);

    try {
      await deleteDataset(confirmTarget.id);
      setItems((current) => current.filter((dataset) => dataset.id !== confirmTarget.id));
      setConfirmTarget(null);
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除数据集失败");
    } finally {
      setPendingDeleteId(null);
    }
  }

  return (
    <div className="space-y-3">
      {actionError ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {actionError}
        </div>
      ) : null}

      <ConsoleListTableSurface>
        <Table className="min-w-[1240px] table-fixed">
          <TableHeader className="bg-transparent">
            <TableRow className="hover:bg-transparent">
              <TableHead className={stickyHeadClassName}>数据集名称</TableHead>
              <TableHead className="w-[220px] min-w-[220px]">数据格式</TableHead>
              <TableHead className="w-[110px] min-w-[110px]">最新版本</TableHead>
              <TableHead className="w-[120px] min-w-[120px]">状态</TableHead>
              <TableHead className="w-[110px] min-w-[110px]">数据量</TableHead>
              <TableHead className="w-[150px] min-w-[150px]">更新时间</TableHead>
              <TableHead className="w-[150px] min-w-[150px]">创建时间</TableHead>
              <TableHead className="w-[120px] min-w-[120px]">创建者</TableHead>
              <TableHead className="w-[170px] min-w-[170px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow className="bg-transparent hover:bg-transparent">
                <TableCell className={stickyCellClassName} colSpan={9}>
                  <div className="flex min-h-[180px] flex-col items-center justify-center gap-3 py-10 text-center">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full border border-slate-800/70 bg-[rgba(10,15,22,0.44)] text-slate-500">
                      <FileSearch className="h-5 w-5" />
                    </div>
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-slate-200">暂无数据</div>
                      <div className="text-xs text-slate-500">请调整搜索词或筛选条件后重试</div>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              items.map((dataset) => {
                const statusMeta = getDatasetStatusMeta(dataset.status);
                const isDeleting = pendingDeleteId === dataset.id;

                return (
                  <TableRow key={dataset.id} className="bg-transparent">
                    <TableCell className={stickyCellClassName}>
                      <div className="min-w-0">
                        <Link
                          className="block truncate font-medium text-slate-100 hover:text-white"
                          href={`/dataset/${dataset.id}`}
                        >
                          {dataset.name}
                        </Link>
                        <div className="mt-1 truncate text-xs text-muted-foreground">{dataset.id}</div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{formatDatasetFormatLabel(dataset)}</TableCell>
                    <TableCell>V{dataset.latest_version ?? "--"}</TableCell>
                    <TableCell>
                      <Badge className={statusMeta.className} variant={statusMeta.variant}>
                        {statusMeta.label}
                      </Badge>
                    </TableCell>
                    <TableCell>{dataset.record_count?.toLocaleString() ?? "--"}</TableCell>
                    <TableCell>{formatDateTime(dataset.updated_at ?? dataset.created_at)}</TableCell>
                    <TableCell>{formatDateTime(dataset.created_at)}</TableCell>
                    <TableCell>{dataset.owner_name ?? "--"}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Link href={`/dataset/${dataset.id}/new-version`}>
                          <Button size="sm" variant="outline">
                            新建版本
                          </Button>
                        </Link>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              aria-label="更多操作"
                              className="h-7 w-7 px-0"
                              disabled={isDeleting}
                              size="sm"
                              variant="ghost"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-32">
                            <DropdownMenuItem
                              onSelect={() => {
                                setActionError(null);
                                setConfirmTarget(dataset);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                              删除
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </ConsoleListTableSurface>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open && !pendingDeleteId) {
            setConfirmTarget(null);
          }
        }}
        open={confirmTarget !== null}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除数据集</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除数据集「{confirmTarget?.name ?? ""}」及其所有版本，当前操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingDeleteId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500/90 text-white hover:bg-red-500"
              disabled={pendingDeleteId !== null}
              onClick={() => void handleConfirmDelete()}
            >
              {pendingDeleteId ? "处理中..." : "删除数据集"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

const stickyHeadClassName =
  "sticky left-0 z-20 w-[280px] min-w-[280px] bg-[rgba(13,18,25,0.92)] pr-5 backdrop-blur";

const stickyCellClassName = cn(
  "sticky left-0 z-10 w-[280px] min-w-[280px] bg-[rgba(13,18,25,0.84)] pr-5 align-top",
  "after:absolute after:right-0 after:top-0 after:h-full after:w-px after:bg-slate-800/70"
);

function mergeDatasetsWithUploads(
  datasets: DatasetSummary[],
  uploadItems: DatasetUploadQueueItem[]
) {
  const latestUploadByDatasetId = new Map<string, DatasetUploadQueueItem>();

  for (const item of uploadItems) {
    if (!item.persisted || !item.datasetId) {
      continue;
    }

    const current = latestUploadByDatasetId.get(item.datasetId);
    if (!current || item.updatedAt > current.updatedAt) {
      latestUploadByDatasetId.set(item.datasetId, item);
    }
  }

  const merged = datasets.map((dataset) => {
    const queueItem = latestUploadByDatasetId.get(dataset.id);
    if (!queueItem) {
      return dataset;
    }

    latestUploadByDatasetId.delete(dataset.id);

    return {
      ...dataset,
      description: dataset.description ?? queueItem.description ?? null,
      purpose: queueItem.purpose ?? dataset.purpose ?? null,
      format: queueItem.format ?? dataset.format ?? null,
      use_case: queueItem.useCase ?? dataset.use_case ?? null,
      modality: queueItem.modality ?? dataset.modality ?? null,
      recipe: queueItem.recipe ?? dataset.recipe ?? null,
      status: resolveDatasetStatus(queueItem.status),
      latest_version: queueItem.versionNumber || dataset.latest_version || null,
      latest_version_id: queueItem.versionId || dataset.latest_version_id || null,
      updated_at: new Date(queueItem.updatedAt).toISOString()
    } satisfies DatasetSummary;
  });

  const synthetic = Array.from(latestUploadByDatasetId.values())
    .filter(
      (item) =>
        item.operation === "create-dataset" &&
        item.status !== "completed" &&
        item.datasetId
    )
    .map(
      (item) =>
        ({
          id: item.datasetId!,
          name: item.datasetName,
          description: item.description ?? null,
          purpose: item.purpose ?? null,
          format: item.format ?? null,
          use_case: item.useCase ?? null,
          modality: item.modality ?? null,
          recipe: item.recipe ?? null,
          scope: item.scope,
          source_type: "local-upload",
          status: resolveDatasetStatus(item.status),
          latest_version: item.versionNumber,
          latest_version_id: item.versionId,
          owner_name: null,
          tags: [],
          record_count: null,
          created_at: item.createdAt,
          updated_at: new Date(item.updatedAt).toISOString()
        }) satisfies DatasetSummary
    );

  return [...synthetic, ...merged].sort(
    (left, right) => resolveDatasetTimestamp(right) - resolveDatasetTimestamp(left)
  );
}

function resolveDatasetStatus(status: DatasetUploadQueueItem["status"]) {
  if (status === "completed") {
    return "ready";
  }

  if (status === "processing") {
    return "processing";
  }

  if (status === "failed") {
    return "failed";
  }

  return "uploading";
}

function resolveDatasetTimestamp(dataset: DatasetSummary) {
  return Date.parse(dataset.updated_at ?? dataset.created_at);
}
