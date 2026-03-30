"use client";

import Link from "next/link";
import * as React from "react";
import { ArrowLeft, Database, FolderTree, HardDrive, Loader2, Search, Trash2 } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ConsoleListFilterField,
  ConsoleListHeader,
  ConsoleListTableSurface,
  ConsoleListToolbar,
  ConsoleListToolbarCluster,
  consoleListFilterTriggerClassName,
  consoleListSearchInputClassName
} from "@/components/console/list-surface";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { deleteLakeAsset } from "@/features/lake/api";
import { cn } from "@/lib/utils";
import type { LakeAssetSummary, LakeBatchSummary } from "@/types/api";

type LakeAssetManagerProps = {
  assets: LakeAssetSummary[];
  batches: LakeBatchSummary[];
};

export function LakeAssetManager({ assets, batches }: LakeAssetManagerProps) {
  const router = useRouter();
  const [items, setItems] = React.useState(assets);
  const [query, setQuery] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [typeFilter, setTypeFilter] = React.useState("all");
  const [batchFilter, setBatchFilter] = React.useState("all");
  const [confirmTarget, setConfirmTarget] = React.useState<LakeAssetSummary | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);

  React.useEffect(() => {
    setItems(assets);
  }, [assets]);

  const resourceTypeOptions = React.useMemo(() => {
    return Array.from(
      new Set(items.map((asset) => asset.resource_type?.trim()).filter(Boolean) as string[])
    ).sort((left, right) => left.localeCompare(right, "zh-CN"));
  }, [items]);

  const batchOptions = React.useMemo(() => {
    const labelById = new Map(batches.map((batch) => [batch.id, batch.name]));
    return Array.from(
      new Set(items.map((asset) => asset.batch_id))
    ).map((batchId) => ({
      id: batchId,
      name: labelById.get(batchId) ?? batchId
    }));
  }, [batches, items]);

  const filteredItems = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((asset) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        asset.name.toLowerCase().includes(normalizedQuery) ||
        (asset.relative_path ?? "").toLowerCase().includes(normalizedQuery) ||
        asset.id.toLowerCase().includes(normalizedQuery) ||
        asset.batch_id.toLowerCase().includes(normalizedQuery) ||
        asset.batch_name.toLowerCase().includes(normalizedQuery);
      const matchesStatus = statusFilter === "all" || asset.status === statusFilter;
      const matchesType = typeFilter === "all" || asset.resource_type === typeFilter;
      const matchesBatch = batchFilter === "all" || asset.batch_id === batchFilter;
      return matchesQuery && matchesStatus && matchesType && matchesBatch;
    });
  }, [batchFilter, items, query, statusFilter, typeFilter]);

  const totalSizeBytes = React.useMemo(
    () =>
      items.reduce((sum, asset) => {
        return sum + (asset.size_bytes ?? 0);
      }, 0),
    [items]
  );
  const folderCount = items.filter((asset) => asset.resource_type === "folder").length;
  const fileCount = items.length - folderCount;
  const activeBatchCount = new Set(items.map((asset) => asset.batch_id)).size;

  async function handleConfirmDelete() {
    if (!confirmTarget) {
      return;
    }

    setPendingDeleteId(confirmTarget.id);
    try {
      await deleteLakeAsset(confirmTarget.id);
      setItems((current) => pruneDeletedAssets(current, confirmTarget));
      toast.success(
        confirmTarget.resource_type === "folder"
          ? `已删除文件夹 ${confirmTarget.name}`
          : `已删除资产 ${confirmTarget.name}`
      );
      setConfirmTarget(null);
      router.refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除资产失败";
      toast.error(message);
    } finally {
      setPendingDeleteId(null);
    }
  }

  return (
    <div className="space-y-4">
      <ConsoleListHeader
        actions={
          <>
            <Link href="/dataset?scope=my-data-lake">
              <Button size="sm" variant="outline">
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                返回我的数据湖
              </Button>
            </Link>
            <Link href="/data">
              <Button size="sm" variant="outline">
                浏览对象层
              </Button>
            </Link>
          </>
        }
        description="这里展示项目内全部 lake raw 资产。按资产维度做搜索、筛选和删除，不再受“最近资产”数量限制。"
        title="湖资产管理"
      />

      <div className="grid gap-3 md:grid-cols-4">
        <SummaryStatCard hint="包含文件和目录资产" icon={Database} label="资产总数" value={items.length} />
        <SummaryStatCard hint={`${folderCount} 个目录资产`} icon={FolderTree} label="文件资产" value={fileCount} />
        <SummaryStatCard hint="当前资产归属的导入批次" icon={Database} label="活跃批次" value={activeBatchCount} />
        <SummaryStatCard hint="raw 层登记的对象大小" icon={HardDrive} label="原始体量" value={formatFileSize(totalSizeBytes)} />
      </div>

      <ConsoleListToolbar className="gap-y-2">
        <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
          <div className="relative min-w-[300px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
            <Input
              className={cn(consoleListSearchInputClassName, "w-full")}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索文件名、相对路径、批次名称或资产 ID"
              type="search"
              value={query}
            />
          </div>

          <ConsoleListFilterField className="w-[148px] min-w-[148px]" label="状态">
            <Select onValueChange={setStatusFilter} value={statusFilter}>
              <SelectTrigger className={consoleListFilterTriggerClassName}>
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="ready">已就绪</SelectItem>
                <SelectItem value="uploading">上传中</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
              </SelectContent>
            </Select>
          </ConsoleListFilterField>

          <ConsoleListFilterField className="w-[168px] min-w-[168px]" label="类型">
            <Select onValueChange={setTypeFilter} value={typeFilter}>
              <SelectTrigger className={consoleListFilterTriggerClassName}>
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="all">全部类型</SelectItem>
                {resourceTypeOptions.map((value) => (
                  <SelectItem key={value} value={value}>
                    {formatResourceTypeLabel(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ConsoleListFilterField>

          <ConsoleListFilterField className="w-[220px] min-w-[220px]" label="批次">
            <Select onValueChange={setBatchFilter} value={batchFilter}>
              <SelectTrigger className={cn(consoleListFilterTriggerClassName, "min-w-[220px]")}>
                <SelectValue placeholder="全部批次" />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="all">全部批次</SelectItem>
                {batchOptions.map((batch) => (
                  <SelectItem key={batch.id} value={batch.id}>
                    {batch.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </ConsoleListFilterField>
        </ConsoleListToolbarCluster>
      </ConsoleListToolbar>

      <ConsoleListTableSurface>
        <Table className="min-w-[1320px] table-fixed">
          <TableHeader className="bg-transparent">
            <TableRow className="hover:bg-transparent">
              <TableHead className={stickyHeadClassName}>资产</TableHead>
              <TableHead className="w-[240px] min-w-[240px]">批次</TableHead>
              <TableHead className="w-[140px] min-w-[140px]">类型</TableHead>
              <TableHead className="w-[100px] min-w-[100px]">大小</TableHead>
              <TableHead className="w-[110px] min-w-[110px]">状态</TableHead>
              <TableHead className="w-[150px] min-w-[150px]">导入时间</TableHead>
              <TableHead className="w-[120px] min-w-[120px] text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredItems.length === 0 ? (
              <TableRow className="bg-transparent hover:bg-transparent">
                <TableCell className={stickyCellClassName} colSpan={7}>
                  <div className="flex min-h-[200px] flex-col items-center justify-center gap-3 py-10 text-center">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full border border-slate-800/70 bg-[rgba(10,15,22,0.44)] text-slate-500">
                      <Database className="h-5 w-5" />
                    </div>
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-slate-200">没有匹配的资产</div>
                      <div className="text-xs text-slate-500">调整搜索词或筛选条件后再试</div>
                    </div>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((asset) => {
                const isDeleting = pendingDeleteId === asset.id;
                const statusMeta = getLakeStatusMeta(asset.status);

                return (
                  <TableRow key={asset.id} className="bg-transparent">
                    <TableCell className={stickyCellClassName}>
                      <div className="min-w-0">
                        <div className="truncate font-medium text-slate-100">{asset.name}</div>
                        <div className="mt-1 truncate text-xs text-slate-500">
                          {asset.relative_path || asset.id}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-slate-200">{asset.batch_name}</div>
                        <div className="mt-1 truncate text-xs text-slate-500">{asset.batch_id}</div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-slate-300">
                      {asset.resource_type === "folder"
                        ? "目录"
                        : `${formatResourceTypeLabel(asset.resource_type)} · ${asset.format || "bin"}`}
                    </TableCell>
                    <TableCell className="text-sm text-slate-300">
                      {asset.resource_type === "folder" ? "目录" : formatFileSize(asset.size_bytes ?? 0)}
                    </TableCell>
                    <TableCell>
                      <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-slate-400">
                      {formatDateTime(asset.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        className="h-7 min-w-[72px] gap-1.5 whitespace-nowrap"
                        disabled={isDeleting}
                        onClick={() => setConfirmTarget(asset)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        {isDeleting ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                        删除
                      </Button>
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
            <AlertDialogCancel disabled={pendingDeleteId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="min-w-[96px] bg-rose-600 text-white hover:bg-rose-500"
              disabled={pendingDeleteId !== null}
              onClick={() => void handleConfirmDelete()}
            >
              {pendingDeleteId ? (
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

function SummaryStatCard({
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
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(12,18,27,0.78)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-[12px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
          <div className="text-2xl font-semibold text-slate-50">{value}</div>
          <div className="text-xs text-slate-500">{hint}</div>
        </div>
        <div className="rounded-full border border-slate-800 bg-slate-950/80 p-2 text-slate-300">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

function pruneDeletedAssets(items: LakeAssetSummary[], target: LakeAssetSummary) {
  if (target.resource_type !== "folder") {
    return items.filter((item) => item.id !== target.id);
  }

  const targetPath = target.relative_path?.replace(/\/+$/, "") ?? "";
  return items.filter((item) => {
    if (item.batch_id !== target.batch_id) {
      return true;
    }
    if (item.id === target.id) {
      return false;
    }
    const itemPath = item.relative_path?.replace(/\/+$/, "") ?? "";
    if (!targetPath || !itemPath) {
      return true;
    }
    return itemPath !== targetPath && !itemPath.startsWith(`${targetPath}/`);
  });
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

function formatFileSize(sizeBytes: number) {
  if (sizeBytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = sizeBytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function formatResourceTypeLabel(value?: string | null) {
  if (!value) {
    return "document";
  }
  const labelByType: Record<string, string> = {
    archive: "压缩包",
    binary: "二进制",
    document: "文档",
    folder: "目录",
    image: "图片",
    tabular: "表格"
  };
  return labelByType[value] ?? value;
}

function getLakeStatusMeta(status: string) {
  const metaByStatus: Record<string, { label: string; className: string }> = {
    failed: {
      label: "失败",
      className: "border-rose-500/25 bg-rose-500/10 text-rose-200"
    },
    ready: {
      label: "已就绪",
      className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
    },
    uploading: {
      label: "上传中",
      className: "border-amber-500/25 bg-amber-500/10 text-amber-200"
    }
  };
  return (
    metaByStatus[status] ?? {
      label: status,
      className: "border-slate-500/25 bg-slate-500/10 text-slate-200"
    }
  );
}

const stickyHeadClassName =
  "sticky left-0 z-20 w-[360px] min-w-[360px] bg-[rgba(13,18,25,0.92)] pr-5 backdrop-blur";

const stickyCellClassName = cn(
  "sticky left-0 z-10 w-[360px] min-w-[360px] bg-[rgba(13,18,25,0.84)] pr-5 align-top",
  "after:absolute after:right-0 after:top-0 after:h-full after:w-px after:bg-slate-800/70"
);
