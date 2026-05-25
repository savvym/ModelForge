"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import {
  deleteBenchmarkVersion,
  getBenchmarkSampleFileUrl,
  getBenchmarkVersionDownloadUrl,
  getBenchmarkVersionPreview
} from "@/features/eval/api";
import { cn } from "@/lib/utils";
import type {
  BenchmarkDefinitionDetail,
  BenchmarkVersionSummary,
  ObjectStoreObjectPreviewResponse
} from "@/types/api";

type DetailTab = "details" | "preview";

type JsonlPreviewRow = {
  lineNumber: number;
  record: Record<string, unknown>;
};

type JsonlPreviewParseError = {
  lineNumber: number;
  message: string;
};

type JsonlPreviewResult = {
  rows: JsonlPreviewRow[];
  columns: string[];
  parseErrors: JsonlPreviewParseError[];
  totalLines: number;
};

const JSONL_PREVIEW_PAGE_SIZE = 20;
const ROOT_JSON_PATH = "$";

const PREFERRED_JSONL_COLUMNS = [
  "id",
  "instruction",
  "input",
  "output",
  "messages",
  "text",
  "question",
  "answer",
  "label",
  "response",
  "target",
  "metadata"
] as const;

export function BenchmarkDetailPanel({
  benchmark
}: {
  benchmark: BenchmarkDefinitionDetail;
}) {
  const router = useRouter();
  const isBuiltin = benchmark.source_type === "builtin";
  const versions = benchmark.versions;
  const [activeTab, setActiveTab] = React.useState<DetailTab>("details");
  const [selectedVersionId, setSelectedVersionId] = React.useState(versions[0]?.id ?? "");
  const [previewCache, setPreviewCache] = React.useState<
    Record<string, ObjectStoreObjectPreviewResponse>
  >({});
  const [loadingPreviewVersionId, setLoadingPreviewVersionId] = React.useState<string | null>(null);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [deletePending, setDeletePending] = React.useState(false);

  const selectedVersion =
    versions.find((version) => version.id === selectedVersionId) ?? versions[0] ?? null;
  const selectedPreview = selectedVersion ? previewCache[selectedVersion.id] : undefined;
  React.useEffect(() => {
    if (!selectedVersion && versions.length > 0) {
      setSelectedVersionId(versions[0].id);
    }
  }, [selectedVersion, versions]);

  React.useEffect(() => {
    if (isBuiltin || activeTab !== "preview" || !selectedVersion) {
      return;
    }

    if (!selectedVersion.dataset_source_uri) {
      setPreviewError("当前 Version 还没有可预览的数据文件。");
      return;
    }

    if (previewCache[selectedVersion.id]) {
      setPreviewError(null);
      return;
    }

    let cancelled = false;
    setLoadingPreviewVersionId(selectedVersion.id);
    setPreviewError(null);

    getBenchmarkVersionPreview(benchmark.name, selectedVersion.id)
      .then((preview) => {
        if (cancelled) {
          return;
        }

        setPreviewCache((current) => ({
          ...current,
          [selectedVersion.id]: preview
        }));
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }

        setPreviewError(error instanceof Error ? error.message : "文件预览读取失败");
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPreviewVersionId((current) =>
            current === selectedVersion.id ? null : current
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, isBuiltin, previewCache, selectedVersion]);

  function handleDownloadSelectedVersion() {
    if (!selectedVersion) {
      return;
    }

    window.location.href = getBenchmarkVersionDownloadUrl(benchmark.name, selectedVersion.id);
  }

  function handleDownloadSampleFile() {
    window.location.href = getBenchmarkSampleFileUrl(benchmark.name);
  }

  async function handleDeleteSelectedVersion() {
    if (!selectedVersion) {
      return;
    }

    setDeletePending(true);
    setActionError(null);

    try {
      await deleteBenchmarkVersion(benchmark.name, selectedVersion.id);
      setDeleteConfirmOpen(false);
      router.refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除 Benchmark Version 失败");
      setDeleteConfirmOpen(false);
    } finally {
      setDeletePending(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {actionError ? (
        <div className="mx-4 mb-3 rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {actionError}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <Card className="flex min-h-0 w-[320px] flex-col overflow-hidden rounded-none border-0 border-r border-border bg-transparent shadow-none">
        <CardHeader className="border-b border-border bg-transparent px-3 py-2.5">
          <div className="space-y-1">
            <div className="text-[13px] font-medium text-foreground">Benchmark Versions</div>
            <div className="text-xs text-muted-foreground">{versions.length} 个版本</div>
          </div>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 p-0">
          <div className="min-h-0 overflow-y-auto px-2 py-2">
            {versions.length > 0 ? (
              <div className="space-y-2">
                {versions.map((version) => {
                  const isActive = version.id === selectedVersion?.id;

                  return (
                    <button
                      className={cn(
                        "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                        isActive
                          ? "border-border bg-muted/60"
                          : "border-border bg-card/60 hover:border-border hover:bg-muted/60"
                      )}
                      key={version.id}
                      onClick={() => {
                        setSelectedVersionId(version.id);
                        setActiveTab("details");
                      }}
                      type="button"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-foreground">
                            {version.display_name}
                          </div>
                          <div className="mt-1 font-mono text-[11px] text-muted-foreground">{version.id}</div>
                        </div>
                        <Badge variant={version.enabled ? "outline" : "secondary"}>
                          {version.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                        <span>{formatNumber(version.sample_count)} samples</span>
                        <span>{formatNumber(version.evaluation_run_count)} runs</span>
                      </div>
                      {version.latest_eval_at ? (
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          最近运行 {formatDateTime(version.latest_eval_at)}
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="px-4 py-6 text-sm text-muted-foreground">当前 Benchmark 还没有可展示的版本。</div>
            )}
          </div>
        </CardContent>
        </Card>

        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-none border-0 bg-transparent shadow-none">
          <CardHeader className="border-b border-border bg-transparent px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <PrimaryTabButton
                  active={activeTab === "details"}
                  label="版本详情"
                  onClick={() => setActiveTab("details")}
                />
                {!isBuiltin ? (
                  <PrimaryTabButton
                    active={activeTab === "preview"}
                    label="数据预览"
                    onClick={() => setActiveTab("preview")}
                  />
                ) : null}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {selectedVersion ? (
                  <Link
                    href={`/model/eval-leaderboards/create?benchmark=${encodeURIComponent(benchmark.name)}&version=${encodeURIComponent(selectedVersion.id)}`}
                  >
                    <Button type="button" variant="outline">
                      创建排行榜
                    </Button>
                  </Link>
                ) : null}
                {isBuiltin ? (
                  <Button onClick={handleDownloadSampleFile} type="button" variant="outline">
                    下载示例格式
                  </Button>
                ) : (
                  <>
                    {selectedVersion ? (
                      <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/${selectedVersion.id}/edit`}>
                        <Button type="button" variant="outline">
                          编辑 Version
                        </Button>
                      </Link>
                    ) : null}
                    {selectedVersion ? (
                      <Button
                        className="border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
                        disabled={deletePending}
                        onClick={() => {
                          setActionError(null);
                          setDeleteConfirmOpen(true);
                        }}
                        type="button"
                        variant="outline"
                      >
                        删除 Version
                      </Button>
                    ) : null}
                    <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/create`}>
                      <Button type="button">新增 Version</Button>
                    </Link>
                  </>
                )}
              </div>
            </div>
          </CardHeader>

          <CardContent className="min-h-0 flex-1 p-0">
            {selectedVersion ? (
              activeTab === "details" ? (
                <BenchmarkVersionDetailTab
                  benchmarkDisplayName={benchmark.display_name}
                  benchmarkName={benchmark.name}
                  isBuiltin={isBuiltin}
                  version={selectedVersion}
                />
              ) : (
                <BenchmarkVersionPreviewTab
                  loading={loadingPreviewVersionId === selectedVersion.id}
                  onDownload={handleDownloadSelectedVersion}
                  preview={selectedPreview}
                  previewError={previewError}
                  version={selectedVersion}
                />
              )
            ) : (
              <div className="flex min-h-[480px] items-center justify-center p-10 text-sm text-muted-foreground">
                当前 Benchmark 还没有可展示的版本。
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <AlertDialog
        onOpenChange={(open) => {
          if (!deletePending) {
            setDeleteConfirmOpen(open);
          }
        }}
        open={deleteConfirmOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 Benchmark Version</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除当前 Version「{selectedVersion?.display_name ?? "--"}」及其管理入口。
              如果这个 Version 仍被评测任务引用，系统会先阻止删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletePending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deletePending}
              onClick={() => void handleDeleteSelectedVersion()}
            >
              {deletePending ? "处理中..." : "删除 Version"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function BenchmarkVersionDetailTab({
  benchmarkDisplayName,
  benchmarkName,
  isBuiltin,
  version
}: {
  benchmarkDisplayName: string;
  benchmarkName: string;
  isBuiltin: boolean;
  version: BenchmarkVersionSummary;
}) {
  return (
    <div className="min-h-0 overflow-y-auto p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Card className="border-border bg-card/80 shadow-none">
            <CardHeader className="pb-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-3">
                  <div className="inline-flex rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs font-medium text-foreground">
                    {version.id}
                  </div>
                  <CardTitle className="text-lg text-foreground">{version.display_name}</CardTitle>
                </div>
                <Badge variant={version.enabled ? "outline" : "secondary"}>
                  {version.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="样本数" value={formatNumber(version.sample_count)} />
              <MetricCard label="任务数" value={formatNumber(version.evaluation_run_count)} />
              <MetricCard label="状态" value={version.enabled ? "已启用" : "已停用"} />
              <MetricCard label="最近运行" value={formatDateTime(version.latest_eval_at)} />
            </CardContent>
          </Card>

          <Card className="border-border bg-card/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-foreground">Version 信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-foreground">
              <DetailRow label="Benchmark" value={`${benchmarkDisplayName} (${benchmarkName})`} />
              <DetailRow label="展示名称" value={version.display_name} />
              <DetailRow label="说明" value={version.description || "--"} />
              {isBuiltin ? (
                <DetailRow label="数据来源" value="平台预置数据集版本" />
              ) : (
                <DetailRow label="数据源 URI" value={version.dataset_source_uri || "--"} />
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="border-border bg-card/80 shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-foreground">
              {isBuiltin ? "使用提示" : "预览提示"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            {isBuiltin ? (
              <>
                <p>基线 Benchmark 由平台统一维护，当前页面只展示可用版本信息，不提供版本编辑或数据文件预览。</p>
                <p>如果你要准备自定义数据集，可以先下载示例格式，再按对应评测维度组织 JSONL 文件。</p>
              </>
            ) : (
              <>
                <p>数据预览会直接读取当前 Version 绑定的数据文件，便于快速检查样本结构和字段内容。</p>
                <p>点击任一行，可在右侧查看该条 JSONL 样本的完整结构。</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BenchmarkVersionPreviewTab({
  loading,
  onDownload,
  preview,
  previewError,
  version
}: {
  loading: boolean;
  onDownload: () => void;
  preview?: ObjectStoreObjectPreviewResponse;
  previewError: string | null;
  version: BenchmarkVersionSummary;
}) {
  const previewContent = preview?.content ?? "";
  const [previewPage, setPreviewPage] = React.useState(1);
  const jsonlPreview = React.useMemo(() => buildJsonlPreview(previewContent), [previewContent]);
  const totalPreviewRows = jsonlPreview.rows.length;
  const previewPageCount = Math.max(1, Math.ceil(totalPreviewRows / JSONL_PREVIEW_PAGE_SIZE));
  const boundedPreviewPage = Math.min(previewPage, previewPageCount);
  const previewPageStart = (boundedPreviewPage - 1) * JSONL_PREVIEW_PAGE_SIZE;
  const pagedPreviewRows = jsonlPreview.rows.slice(
    previewPageStart,
    previewPageStart + JSONL_PREVIEW_PAGE_SIZE
  );
  const previewLineLabel = React.useMemo(() => {
    if (preview?.truncated) {
      const totalCount =
        version.sample_count > jsonlPreview.totalLines
          ? ` / 共 ${formatNumber(version.sample_count)} 条`
          : "";

      return `预览前 ${jsonlPreview.totalLines} 行${totalCount}`;
    }

    return `${jsonlPreview.totalLines} 行预览`;
  }, [jsonlPreview.totalLines, preview?.truncated, version.sample_count]);

  React.useEffect(() => {
    setPreviewPage(1);
  }, [previewContent, version.id]);

  React.useEffect(() => {
    setPreviewPage((current) => Math.min(current, previewPageCount));
  }, [previewPageCount]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-foreground">
              {preview?.file_name ?? version.dataset_source_uri ?? version.display_name}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">{previewLineLabel}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              className="gap-2"
              disabled={!preview?.object_key}
              onClick={onDownload}
              type="button"
              variant="outline"
            >
              <Download className="h-4 w-4" />
              下载
            </Button>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {loading ? (
          <PreviewState message="文件预览加载中..." />
        ) : previewError ? (
          <PreviewState intent="error" message={previewError} />
        ) : !preview ? (
          <PreviewState message="当前 Version 还没有可预览的文件内容。" />
        ) : preview.preview_kind !== "text" ? (
          <PreviewState
            message={`当前对象是 ${preview.preview_kind} 类型，暂不支持结构化预览，请直接下载查看。`}
          />
        ) : (
          <JsonlTableView
            columns={jsonlPreview.columns}
            key={version.id}
            loading={loading}
            page={boundedPreviewPage}
            pageCount={previewPageCount}
            pageSize={JSONL_PREVIEW_PAGE_SIZE}
            rows={pagedPreviewRows}
            totalRows={totalPreviewRows}
            truncated={preview.truncated}
            versionSampleCount={version.sample_count}
            onPageChange={setPreviewPage}
          />
        )}
      </div>
    </div>
  );
}

function JsonlTableView({
  columns,
  loading,
  onPageChange,
  page,
  pageCount,
  pageSize,
  rows,
  totalRows,
  truncated,
  versionSampleCount
}: {
  columns: string[];
  loading: boolean;
  onPageChange: (page: number) => void;
  page: number;
  pageCount: number;
  pageSize: number;
  rows: JsonlPreviewRow[];
  totalRows: number;
  truncated: boolean;
  versionSampleCount: number;
}) {
  const [selectedRow, setSelectedRow] = React.useState<JsonlPreviewRow | null>(null);
  const start = totalRows ? (page - 1) * pageSize + 1 : 0;
  const end = Math.min(page * pageSize, totalRows);
  const totalLabel =
    truncated && versionSampleCount > totalRows
      ? `已预览 ${formatNumber(totalRows)} 条 · 共 ${formatNumber(versionSampleCount)} 条`
      : `共 ${formatNumber(totalRows)} 条`;

  function openRow(row: JsonlPreviewRow) {
    setSelectedRow(row);
  }

  function changePage(nextPage: number) {
    setSelectedRow(null);
    onPageChange(nextPage);
  }

  return totalRows > 0 ? (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <ConsoleListTableSurface className="min-h-0 flex-1 overflow-hidden">
        <div className="console-scrollbar-subtle max-h-[calc(100vh-340px)] min-h-[360px] overflow-auto">
          <table className="w-full min-w-[980px] table-fixed caption-bottom text-sm">
            <TableHeader className="bg-transparent">
              <TableRow className="hover:bg-transparent">
                <TableHead className="sticky left-0 top-0 z-20 w-[96px] min-w-[96px] bg-card/80">
                  行
                </TableHead>
                {columns.map((column) => (
                  <TableHead
                    className="sticky top-0 z-10 min-w-[180px] bg-card/80"
                    key={column}
                  >
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  aria-label={`查看第 ${row.lineNumber} 行详情`}
                  className={cn(
                    "cursor-pointer bg-transparent outline-none hover:bg-muted/40 focus-visible:bg-muted/50",
                    selectedRow?.lineNumber === row.lineNumber ? "bg-muted/50" : null
                  )}
                  key={row.lineNumber}
                  onClick={() => openRow(row)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openRow(row);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <TableCell
                    className={cn(
                      "sticky left-0 z-10 w-[96px] min-w-[96px] bg-card/90 align-top font-medium text-muted-foreground",
                      selectedRow?.lineNumber === row.lineNumber ? "bg-muted" : null
                    )}
                  >
                    {row.lineNumber}
                  </TableCell>
                  {columns.map((column) => (
                    <TableCell
                      className="max-w-[320px] align-top text-[13px] leading-6 text-foreground"
                      key={`${row.lineNumber}-${column}`}
                    >
                      <div className="line-clamp-3 break-words">
                        {formatJsonlValuePreview(row.record[column])}
                      </div>
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </table>
        </div>
      </ConsoleListTableSurface>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-card/80 px-4 py-3">
        <div className="text-xs text-muted-foreground">
          {start} - {end} / {totalLabel}
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            disabled={loading || page <= 1}
            onClick={() => changePage(Math.max(1, page - 1))}
            size="sm"
            type="button"
            variant="ghost"
          >
            上一页
          </Button>
          <div className="min-w-[64px] text-center text-xs text-muted-foreground">
            {page} / {pageCount}
          </div>
          <Button
            disabled={loading || page >= pageCount}
            onClick={() => changePage(Math.min(pageCount, page + 1))}
            size="sm"
            type="button"
            variant="ghost"
          >
            下一页
          </Button>
        </div>
      </div>

      <JsonlRowDetailSheet
        onOpenChange={(open) => {
          if (!open) {
            setSelectedRow(null);
          }
        }}
        open={selectedRow !== null}
        row={selectedRow}
      />
    </div>
  ) : (
    <EmptyPreviewPanel
      description="当前预览内容还不足以生成结构化表格。"
      title="暂无可展示的 JSONL 记录"
    />
  );
}

function JsonlRowDetailSheet({
  onOpenChange,
  open,
  row
}: {
  onOpenChange: (open: boolean) => void;
  open: boolean;
  row: JsonlPreviewRow | null;
}) {
  const fieldCount = row ? Object.keys(row.record).length : 0;
  const [selectedJsonPath, setSelectedJsonPath] = React.useState<string>(ROOT_JSON_PATH);
  const [expandedJsonPaths, setExpandedJsonPaths] = React.useState<string[]>([ROOT_JSON_PATH]);

  React.useEffect(() => {
    setSelectedJsonPath(ROOT_JSON_PATH);
    setExpandedJsonPaths(row ? getInitialExpandedJsonPaths(row.record) : [ROOT_JSON_PATH]);
  }, [row]);

  return (
    <Sheet onOpenChange={onOpenChange} open={open}>
      <SheetContent className="w-full gap-0 overflow-hidden border-l border-border bg-card p-0 text-foreground shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-[640px] [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-muted-foreground [&>button]:hover:bg-card/80 [&>button]:hover:text-foreground">
        <SheetHeader className="border-b border-border bg-card/80 px-5 py-4 pr-16 text-left">
          <SheetTitle className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            line:{row?.lineNumber ?? "--"}
          </SheetTitle>
          <SheetDescription className="text-[12px] leading-5 text-muted-foreground">
            格式化 JSON 结构 · {fieldCount} 个字段
          </SheetDescription>
        </SheetHeader>
        <div className="console-scrollbar-drawer min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {row ? (
            <JsonStructureTree
              expandedPaths={expandedJsonPaths}
              onSelectPath={setSelectedJsonPath}
              onTogglePath={(path) =>
                setExpandedJsonPaths((current) =>
                  current.includes(path)
                    ? current.filter((item) => item !== path)
                    : [...current, path]
                )
              }
              selectedPath={selectedJsonPath}
              value={row.record}
            />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function JsonStructureTree({
  expandedPaths,
  onSelectPath,
  onTogglePath,
  selectedPath,
  value
}: {
  expandedPaths: string[];
  onSelectPath: (path: string) => void;
  onTogglePath: (path: string) => void;
  selectedPath: string;
  value: unknown;
}) {
  if (!isJsonContainer(value)) {
    return (
      <div className="font-mono text-[12px] leading-7 text-foreground">
        {renderJsonNodeValue(value)}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {renderJsonTreeChildren({
        depth: 0,
        expandedPaths,
        onSelectPath,
        onTogglePath,
        parentPath: ROOT_JSON_PATH,
        selectedPath,
        value
      })}
    </div>
  );
}

function PrimaryTabButton({
  active,
  label,
  onClick
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "inline-flex h-8 items-center rounded-full border px-3 text-sm transition-colors",
        active
          ? "border-border bg-accent text-accent-foreground"
          : "border-border bg-muted/40 text-muted-foreground hover:bg-card/80 hover:text-foreground"
      )}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/40 px-4 py-4">
      <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="mt-3 text-lg font-medium text-foreground">{value}</div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="break-all text-sm text-foreground">{value}</div>
    </div>
  );
}

function PreviewState({
  intent = "default",
  message
}: {
  intent?: "default" | "error";
  message: string;
}) {
  return (
    <div className="flex min-h-full items-center justify-center p-10">
      <div
        className={cn(
          "rounded-lg border px-4 py-3 text-sm",
          intent === "error"
            ? "border-rose-900/40 bg-destructive/10 text-destructive"
            : "border-border bg-muted/40 text-muted-foreground"
        )}
      >
        {message}
      </div>
    </div>
  );
}

function EmptyPreviewPanel({
  description,
  title
}: {
  description: string;
  title: string;
}) {
  return (
    <div className="flex min-h-full items-center justify-center p-10">
      <div className="max-w-md space-y-2 text-center">
        <div className="text-base font-medium text-foreground">{title}</div>
        <div className="text-sm leading-6 text-muted-foreground">{description}</div>
      </div>
    </div>
  );
}

function buildJsonlPreview(content: string): JsonlPreviewResult {
  const lines = content.split(/\r?\n/);
  const rows: JsonlPreviewRow[] = [];
  const parseErrors: JsonlPreviewParseError[] = [];
  const fields = new Map<string, number>();
  let totalLines = 0;

  lines.forEach((line, index) => {
    if (!line.trim()) {
      return;
    }

    totalLines += 1;

    try {
      const parsed = JSON.parse(line) as unknown;
      const record = isPlainRecord(parsed) ? parsed : { value: parsed };
      rows.push({
        lineNumber: index + 1,
        record
      });

      Object.keys(record).forEach((key) => {
        fields.set(key, (fields.get(key) ?? 0) + 1);
      });
    } catch (error) {
      parseErrors.push({
        lineNumber: index + 1,
        message: error instanceof Error ? error.message : "JSON 解析失败"
      });
    }
  });

  const columns = Array.from(fields.entries())
    .sort((left, right) => {
      const preferredOrder =
        getPreferredColumnOrder(left[0]) - getPreferredColumnOrder(right[0]);
      if (preferredOrder !== 0) {
        return preferredOrder;
      }
      if (left[1] !== right[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .map(([key]) => key);

  return {
    rows,
    columns: columns.length > 0 ? columns : ["value"],
    parseErrors,
    totalLines
  };
}

function getPreferredColumnOrder(column: string) {
  const index = PREFERRED_JSONL_COLUMNS.indexOf(column as (typeof PREFERRED_JSONL_COLUMNS)[number]);
  return index === -1 ? PREFERRED_JSONL_COLUMNS.length + 1 : index;
}

function formatJsonlValuePreview(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatJsonlValuePreview(item)).join(", ");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "[object]";
    }
  }
  return String(value);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isJsonContainer(value: unknown): value is Record<string, unknown> | unknown[] {
  return isPlainRecord(value) || Array.isArray(value);
}

function getInitialExpandedJsonPaths(value: unknown) {
  return collectExpandedJsonPaths(value, ROOT_JSON_PATH, 1);
}

function collectExpandedJsonPaths(value: unknown, path: string, depth: number): string[] {
  if (!isJsonContainer(value)) {
    return [];
  }

  const next = [path];
  if (depth <= 0) {
    return next;
  }

  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      if (isJsonContainer(item)) {
        next.push(...collectExpandedJsonPaths(item, appendJsonPath(path, index), depth - 1));
      }
    });
    return next;
  }

  Object.entries(value).forEach(([key, item]) => {
    if (isJsonContainer(item)) {
      next.push(...collectExpandedJsonPaths(item, appendJsonPath(path, key), depth - 1));
    }
  });

  return next;
}

function renderJsonTreeChildren({
  depth,
  expandedPaths,
  onSelectPath,
  onTogglePath,
  parentPath,
  selectedPath,
  value
}: {
  depth: number;
  expandedPaths: string[];
  onSelectPath: (path: string) => void;
  onTogglePath: (path: string) => void;
  parentPath: string;
  selectedPath: string;
  value: Record<string, unknown> | unknown[];
}) {
  const entries = Array.isArray(value)
    ? value.map((item, index) => [index, item] as const)
    : Object.entries(value);

  return entries.map(([key, child]) => {
    const path = appendJsonPath(parentPath, key);
    const container = isJsonContainer(child);
    const expanded = container ? expandedPaths.includes(path) : false;
    const active = selectedPath === path;
    const label = Array.isArray(value) ? `[${key}]` : String(key);

    return (
      <div key={path}>
        <div
          className="flex items-start gap-2"
          style={{ paddingLeft: `${depth * 18}px` }}
        >
          {container ? (
            <button
              className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-card/80 hover:text-foreground"
              onClick={() => onTogglePath(path)}
              type="button"
            >
              {expanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </button>
          ) : (
            <span className="block h-5 w-5 shrink-0" />
          )}

          <button
            className={cn(
              "flex min-w-0 flex-1 items-start gap-2 rounded-lg px-2 py-1.5 text-left font-mono text-[12px] leading-6 transition-colors",
              active
                ? "bg-primary/10 text-foreground"
                : "text-foreground hover:bg-muted/40 hover:text-foreground"
            )}
            onClick={() => onSelectPath(path)}
            type="button"
          >
            <span className="shrink-0 text-primary">{label}</span>
            <span className="shrink-0 text-muted-foreground">:</span>
            {container ? (
              <span className="truncate text-muted-foreground">{summarizeJsonContainer(child)}</span>
            ) : (
              renderJsonNodeValue(child)
            )}
          </button>
        </div>

        {container && expanded ? (
          <div className="space-y-1">
            {renderJsonTreeChildren({
              depth: depth + 1,
              expandedPaths,
              onSelectPath,
              onTogglePath,
              parentPath: path,
              selectedPath,
              value: child
            })}
          </div>
        ) : null}
      </div>
    );
  });
}

function appendJsonPath(parentPath: string, segment: string | number) {
  if (typeof segment === "number") {
    return parentPath === ROOT_JSON_PATH ? `${ROOT_JSON_PATH}[${segment}]` : `${parentPath}[${segment}]`;
  }

  return parentPath === ROOT_JSON_PATH ? `${ROOT_JSON_PATH}.${segment}` : `${parentPath}.${segment}`;
}

function summarizeJsonContainer(value: Record<string, unknown> | unknown[]) {
  if (Array.isArray(value)) {
    return `[${value.length}]`;
  }

  return `{${Object.keys(value).length}}`;
}

function renderJsonNodeValue(value: unknown) {
  if (value === null) {
    return <span className="text-muted-foreground">null</span>;
  }

  if (typeof value === "string") {
    return <span className="break-words text-emerald-300">"{value}"</span>;
  }

  if (typeof value === "number") {
    return <span className="text-amber-300">{value}</span>;
  }

  if (typeof value === "boolean") {
    return <span className="text-primary">{String(value)}</span>;
  }

  if (value === undefined) {
    return <span className="text-muted-foreground">undefined</span>;
  }

  return <span className="break-words text-foreground">{String(value)}</span>;
}

function formatNumber(value?: number | null) {
  if (value == null) {
    return "--";
  }
  return value.toLocaleString("zh-CN");
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
