"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronRight,
  Download,
  Ellipsis,
  FileJson2
} from "lucide-react";
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
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  deleteDataset,
  deleteDatasetVersion,
  getDatasetVersionDownloadUrl,
  getDatasetVersionPreview
} from "@/features/dataset/api";
import { getDatasetStatusMeta } from "@/features/dataset/status";
import { cn } from "@/lib/utils";
import type {
  DatasetDetail,
  DatasetFileSummary,
  DatasetVersionPreview,
  DatasetVersionSummary
} from "@/types/api";

type DatasetTab = "preview" | "details";
type PreviewMode = "table" | "raw";
type OpenMenuState =
  | { type: "dataset" }
  | { type: "version"; versionId: string; scope: "tree" }
  | null;
type ConfirmTarget =
  | { type: "dataset" }
  | { type: "version"; version: DatasetVersionSummary }
  | null;

type JsonlPreviewRow = {
  lineNumber: number;
  raw: string;
  record: Record<string, unknown>;
};

type JsonlPreviewParseError = {
  lineNumber: number;
  message: string;
  raw: string;
};

type JsonlPreviewResult = {
  rows: JsonlPreviewRow[];
  columns: string[];
  parseErrors: JsonlPreviewParseError[];
  totalLines: number;
};

const DEFAULT_PREVIEW_FILE_KEY = "__default__";
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
  "target"
];
const ROOT_JSON_PATH = "$";
const previewStickyHeadClassName =
  "sticky left-0 top-0 z-20 w-[96px] min-w-[96px] bg-[rgba(13,18,25,0.92)]";
const previewStickyCellClassName = cn(
  "sticky left-0 z-10 w-[96px] min-w-[96px] align-top font-medium",
  "after:absolute after:right-0 after:top-0 after:h-full after:w-px after:bg-slate-800/70"
);

export function DatasetDetailPanel({ dataset }: { dataset: DatasetDetail }) {
  const router = useRouter();
  const versions = dataset.versions;
  const initialVersionId = versions[0]?.id ?? "";
  const initialFileId = versions[0]?.files[0]?.id ?? "";
  const initialPreviewTarget = getResolvedPreviewTarget(versions, initialVersionId, initialFileId);
  const [activeTab, setActiveTab] = React.useState<DatasetTab>("details");
  const [previewMode, setPreviewMode] = React.useState<PreviewMode>("table");
  const [selectedVersionId, setSelectedVersionId] = React.useState(initialVersionId);
  const [selectedFileId, setSelectedFileId] = React.useState(initialFileId);
  const [lastPreviewTarget, setLastPreviewTarget] = React.useState(initialPreviewTarget);
  const [expandedVersionIds, setExpandedVersionIds] = React.useState<string[]>(() =>
    initialVersionId ? [initialVersionId] : []
  );
  const [previewCache, setPreviewCache] = React.useState<Record<string, Awaited<ReturnType<typeof getDatasetVersionPreview>>>>(
    {}
  );
  const [loadingPreviewKey, setLoadingPreviewKey] = React.useState<string | null>(null);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [pendingAction, setPendingAction] = React.useState<
    "delete-dataset" | "delete-version" | null
  >(null);
  const [openMenu, setOpenMenu] = React.useState<OpenMenuState>(null);
  const [confirmTarget, setConfirmTarget] = React.useState<ConfirmTarget>(null);

  const selectedVersion =
    versions.find((version) => version.id === selectedVersionId) ?? versions[0] ?? null;
  const selectedFile =
    selectedVersion?.files.find((file) => file.id === selectedFileId) ??
    selectedVersion?.files[0] ??
    null;
  const selectedPreviewKey = selectedVersion
    ? getPreviewCacheKey(selectedVersion.id, selectedFile?.id ?? DEFAULT_PREVIEW_FILE_KEY)
    : null;
  const selectedPreview =
    selectedPreviewKey ? previewCache[selectedPreviewKey] : undefined;

  React.useEffect(() => {
    const resolvedPreviewTarget = getResolvedPreviewTarget(
      versions,
      lastPreviewTarget.versionId,
      lastPreviewTarget.fileId
    );

    if (
      resolvedPreviewTarget.versionId !== lastPreviewTarget.versionId ||
      resolvedPreviewTarget.fileId !== lastPreviewTarget.fileId
    ) {
      setLastPreviewTarget(resolvedPreviewTarget);
    }

    if (versions.length > 0 && !versions.some((version) => version.id === selectedVersionId)) {
      setSelectedVersionId(versions[0].id);
    }
  }, [lastPreviewTarget.fileId, lastPreviewTarget.versionId, selectedVersionId, versions]);

  React.useEffect(() => {
    if (activeTab !== "preview") {
      return;
    }

    if (!selectedVersion) {
      setSelectedFileId("");
      return;
    }

    if (
      selectedVersion.files.length > 0 &&
      selectedVersion.files.some((file) => file.id === selectedFileId)
    ) {
      return;
    }

    setSelectedFileId(selectedVersion.files[0]?.id ?? "");
  }, [activeTab, selectedFileId, selectedVersion]);

  React.useEffect(() => {
    if (!selectedVersionId) {
      return;
    }

    setExpandedVersionIds((current) =>
      current.includes(selectedVersionId) ? current : [...current, selectedVersionId]
    );
  }, [selectedVersionId]);

  React.useEffect(() => {
    if (activeTab !== "preview" || !selectedVersion) {
      return;
    }

    const nextPreviewTarget = {
      versionId: selectedVersion.id,
      fileId: selectedFile?.id ?? ""
    };

    setLastPreviewTarget((current) =>
      current.versionId === nextPreviewTarget.versionId &&
      current.fileId === nextPreviewTarget.fileId
        ? current
        : nextPreviewTarget
    );
  }, [activeTab, selectedFile?.id, selectedVersion]);

  React.useEffect(() => {
    if (activeTab !== "preview" || !selectedVersion) {
      return;
    }

    if (selectedVersion.status !== "ready") {
      setPreviewError(null);
      return;
    }

    const previewKey = getPreviewCacheKey(
      selectedVersion.id,
      selectedFile?.id ?? DEFAULT_PREVIEW_FILE_KEY
    );
    if (previewCache[previewKey]) {
      return;
    }

    let cancelled = false;
    setLoadingPreviewKey(previewKey);
    setPreviewError(null);

    getDatasetVersionPreview(dataset.id, selectedVersion.id, selectedFile?.id)
      .then((preview) => {
        if (cancelled) {
          return;
        }

        setPreviewCache((current) => ({
          ...current,
          [previewKey]: preview
        }));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }

        setPreviewError("文件预览读取失败");
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPreviewKey((current) => (current === previewKey ? null : current));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, dataset.id, previewCache, selectedFile, selectedVersion]);

  async function handleDeleteDataset() {
    try {
      setActionError(null);
      setPendingAction("delete-dataset");
      await deleteDataset(dataset.id);
      router.push("/dataset");
      router.refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除数据集失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleDeleteVersion(version: DatasetVersionSummary) {
    try {
      setActionError(null);
      setPendingAction("delete-version");
      await deleteDatasetVersion(dataset.id, version.id);
      router.refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除版本失败");
    } finally {
      setPendingAction(null);
    }
  }

  function handleDownloadVersion() {
    if (!selectedVersion) {
      return;
    }

    window.location.href = getDatasetVersionDownloadUrl(
      dataset.id,
      selectedVersion.id,
      selectedFile?.id
    );
  }

  async function handleConfirmDelete() {
    if (!confirmTarget) {
      return;
    }

    try {
      if (confirmTarget.type === "dataset") {
        await handleDeleteDataset();
        return;
      }

      await handleDeleteVersion(confirmTarget.version);
    } finally {
      setConfirmTarget(null);
    }
  }

  function toggleVersionExpanded(versionId: string) {
    setExpandedVersionIds((current) =>
      current.includes(versionId)
        ? current.filter((item) => item !== versionId)
        : [...current, versionId]
    );
  }

  function openPreview(target?: { versionId: string; fileId: string }) {
    const resolvedTarget = getResolvedPreviewTarget(
      versions,
      target?.versionId ?? lastPreviewTarget.versionId,
      target?.fileId ?? lastPreviewTarget.fileId
    );

    setSelectedVersionId(resolvedTarget.versionId);
    setSelectedFileId(resolvedTarget.fileId);
    setLastPreviewTarget(resolvedTarget);
    setActiveTab("preview");
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2">
      {actionError ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-4 py-3 text-sm text-rose-300">
          {actionError}
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <Card className="flex min-h-0 w-[300px] flex-col overflow-hidden rounded-none border-0 border-r border-slate-800/70 bg-transparent shadow-none">
          <CardHeader className="border-b border-slate-800/70 bg-transparent px-3 py-2.5">
            <div className="space-y-1">
              <div className="text-[13px] font-medium text-zinc-100">版本与文件</div>
              <div className="text-xs text-zinc-500">{versions.length} 个版本</div>
            </div>
          </CardHeader>

          <CardContent className="min-h-0 flex-1 p-0">
            <div className="min-h-0 overflow-y-auto px-2 py-2">
              {versions.length > 0 ? (
                <div>
                  {versions.map((version, index) => {
                    const isLast = index === versions.length - 1;
                    const isExpanded = expandedVersionIds.includes(version.id);
                    const fileEntries = getVersionFileEntries(version);

                    return (
                      <div
                        className={cn(
                          "px-2 py-1.5 transition-colors",
                          !isLast ? "border-b border-slate-800/70" : null,
                          "bg-transparent hover:bg-[rgba(14,20,29,0.56)]"
                        )}
                        key={version.id}
                      >
                        <div className="flex items-center gap-2">
                          <button
                            aria-label={isExpanded ? `收起 V${version.version}` : `展开 V${version.version}`}
                            className="min-w-0 flex flex-1 items-center gap-2 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                            onClick={() => {
                              toggleVersionExpanded(version.id);
                              setSelectedVersionId(version.id);
                              setActiveTab("details");
                            }}
                            type="button"
                          >
                            <span className="flex h-6 w-6 items-center justify-center text-zinc-500">
                              {isExpanded ? (
                                <ChevronDown className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5" />
                              )}
                            </span>
                            <span className="text-sm font-medium text-zinc-100">
                              V{version.version}
                            </span>
                            <span className="text-xs text-zinc-500">
                              {formatNumber(version.record_count)} 条
                            </span>
                            <span className="text-xs text-zinc-500">
                              {version.file_count || fileEntries.length} 文件
                            </span>
                            <span className="rounded-full border border-slate-800/90 bg-[rgba(12,18,28,0.82)] px-2 py-0.5 text-[11px] text-slate-300">
                              {getDatasetStatusMeta(version.status).label}
                            </span>
                          </button>

                          <ActionMenu
                            disabled={pendingAction !== null}
                            onDelete={() => {
                              setOpenMenu(null);
                              setConfirmTarget({ type: "version", version });
                            }}
                            onOpenChange={(open) =>
                              setOpenMenu(
                                open
                                  ? { type: "version", versionId: version.id, scope: "tree" }
                                  : null
                              )
                            }
                            open={
                              openMenu?.type === "version" &&
                              openMenu.versionId === version.id &&
                              openMenu.scope === "tree"
                            }
                            size="icon-sm"
                          />
                        </div>

                        {isExpanded ? (
                          <div className="ml-7 mt-1 space-y-0.5 border-l border-slate-800/70 pl-3">
                            {fileEntries.map((file) => {
                              const isActiveFile =
                                activeTab === "preview" &&
                                version.id === selectedVersionId &&
                                file.id === (selectedFile?.id ?? DEFAULT_PREVIEW_FILE_KEY);

                              return (
                                <button
                                  className={cn(
                                    "flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors",
                                    isActiveFile
                                      ? "bg-[rgba(29,41,58,0.82)] text-zinc-100"
                                      : "text-zinc-400 hover:bg-[rgba(255,255,255,0.04)] hover:text-zinc-200"
                                  )}
                                  key={file.id}
                                  onClick={() => {
                                    openPreview({
                                      versionId: version.id,
                                      fileId: file.id === DEFAULT_PREVIEW_FILE_KEY ? "" : file.id
                                    });
                                  }}
                                  type="button"
                                >
                                  <FileJson2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate text-xs font-medium">{file.file_name}</div>
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="px-4 py-6 text-sm text-zinc-500">当前数据集还没有可展示的版本。</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-none border-0 bg-transparent shadow-none">
          <CardHeader className="border-b border-slate-800/70 bg-transparent px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <PrimaryTabButton
                  active={activeTab === "preview"}
                  label="数据集预览"
                  onClick={() => openPreview()}
                />
                <PrimaryTabButton
                  active={activeTab === "details"}
                  label="版本详情"
                  onClick={() => setActiveTab("details")}
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={pendingAction !== null}
                  onClick={() => router.push(`/dataset/${dataset.id}/new-version`)}
                  type="button"
                >
                  新建版本
                </Button>

                <ActionMenu
                  chrome="plain"
                  disabled={pendingAction !== null}
                  onDelete={() => {
                    setOpenMenu(null);
                    setConfirmTarget({ type: "dataset" });
                  }}
                  onOpenChange={(open) => setOpenMenu(open ? { type: "dataset" } : null)}
                  open={openMenu?.type === "dataset"}
                />
              </div>
            </div>
          </CardHeader>

          <CardContent className="min-h-0 flex-1 p-0">
            {selectedVersion ? (
              activeTab === "preview" ? (
                <DatasetPreviewTab
                  activeFile={selectedFile}
                  loading={loadingPreviewKey === selectedPreviewKey}
                  onDownload={handleDownloadVersion}
                  onPreviewModeChange={setPreviewMode}
                  preview={selectedPreview}
                  previewError={previewError}
                  previewMode={previewMode}
                  version={selectedVersion}
                />
              ) : (
                <DatasetVersionDetailTab
                  dataset={dataset}
                  version={selectedVersion}
                />
              )
            ) : (
              <div className="flex min-h-[480px] items-center justify-center p-10 text-sm text-zinc-500">
                当前数据集还没有可展示的版本。
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <DeleteConfirmDialog
        confirmLabel={confirmTarget?.type === "dataset" ? "删除数据集" : "删除版本"}
        description={
          confirmTarget?.type === "dataset"
            ? `删除后将移除数据集「${dataset.name}」及其所有版本，当前操作不可恢复。`
            : confirmTarget
              ? `删除 V${confirmTarget.version.version} 后将无法恢复，请确认后继续。`
              : ""
        }
        onClose={() => {
          if (pendingAction === null) {
            setConfirmTarget(null);
          }
        }}
        onConfirm={() => void handleConfirmDelete()}
        open={confirmTarget !== null}
        pending={pendingAction !== null}
        title={confirmTarget?.type === "dataset" ? "删除数据集" : "删除版本"}
      />
    </div>
  );
}

function DatasetPreviewTab({
  activeFile,
  loading,
  onDownload,
  onPreviewModeChange,
  preview,
  previewError,
  previewMode,
  version
}: {
  activeFile: DatasetFileSummary | null;
  loading: boolean;
  onDownload: () => void;
  onPreviewModeChange: (mode: PreviewMode) => void;
  preview?: DatasetVersionPreview;
  previewError: string | null;
  previewMode: PreviewMode;
  version: DatasetVersionSummary;
}) {
  const statusMeta = getDatasetStatusMeta(version.status);
  const fileName = preview?.file_name ?? activeFile?.file_name ?? getVersionFileLabel(version);
  const previewContent = preview?.content ?? "";
  const jsonlPreview = React.useMemo(() => buildJsonlPreview(previewContent), [previewContent]);
  const previewLineLabel = React.useMemo(() => {
    if (preview?.truncated) {
      const totalCount =
        typeof version.record_count === "number" && version.record_count > jsonlPreview.totalLines
          ? ` / 共 ${formatNumber(version.record_count)} 条`
          : "";

      return `预览前 ${jsonlPreview.totalLines} 行${totalCount}`;
    }

    return `${jsonlPreview.totalLines} 行预览`;
  }, [jsonlPreview.totalLines, preview?.truncated, version.record_count]);
  const [selectedRowLineNumber, setSelectedRowLineNumber] = React.useState<number | null>(null);
  const [inspectorOpen, setInspectorOpen] = React.useState(false);
  const [selectedJsonPath, setSelectedJsonPath] = React.useState<string>(ROOT_JSON_PATH);
  const [expandedJsonPaths, setExpandedJsonPaths] = React.useState<string[]>([ROOT_JSON_PATH]);
  const selectedRow = React.useMemo(
    () => jsonlPreview.rows.find((row) => row.lineNumber === selectedRowLineNumber) ?? null,
    [jsonlPreview.rows, selectedRowLineNumber]
  );

  React.useEffect(() => {
    if (selectedRowLineNumber === null) {
      return;
    }

    if (!jsonlPreview.rows.some((row) => row.lineNumber === selectedRowLineNumber)) {
      setSelectedRowLineNumber(null);
      setInspectorOpen(false);
    }
  }, [jsonlPreview.rows, selectedRowLineNumber]);

  React.useEffect(() => {
    setSelectedRowLineNumber(null);
    setInspectorOpen(false);
    setSelectedJsonPath(ROOT_JSON_PATH);
    setExpandedJsonPaths([ROOT_JSON_PATH]);
  }, [previewContent]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-slate-800/70 px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-zinc-100">{fileName}</div>
            <div className="mt-1 text-xs text-zinc-500">{previewLineLabel}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <PreviewModeButton
              active={previewMode === "table"}
              label="表格预览"
              onClick={() => onPreviewModeChange("table")}
            />
            <PreviewModeButton
              active={previewMode === "raw"}
              label="Raw JSONL"
              onClick={() => onPreviewModeChange("raw")}
            />
            <Button
              className="gap-2"
              disabled={version.status !== "ready" || (!activeFile && !version.object_key)}
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
        {version.status === "uploading" ? (
          <PreviewState message="文件正在直传到对象存储，上传完成后会自动开始导入。" />
        ) : version.status === "processing" ? (
          <PreviewState message="后台正在解析并导入数据集，完成后可预览和下载。" />
        ) : version.status === "failed" ? (
          <PreviewState intent="error" message={`${statusMeta.label}，请重新上传该版本。`} />
        ) : loading ? (
          <PreviewState message="文件预览加载中..." />
        ) : previewError ? (
          <PreviewState intent="error" message={previewError} />
        ) : previewMode === "table" ? (
          <JsonlTableView
            activeRowLineNumber={selectedRowLineNumber}
            columns={jsonlPreview.columns}
            onSelectRow={(row) => {
              setSelectedRowLineNumber(row.lineNumber);
              setSelectedJsonPath(ROOT_JSON_PATH);
              setExpandedJsonPaths(getInitialExpandedJsonPaths(row.record));
              setInspectorOpen(true);
            }}
            rows={jsonlPreview.rows}
          />
        ) : (
          <JsonlRawView
            content={previewContent}
            parseErrors={jsonlPreview.parseErrors}
            rows={jsonlPreview.rows}
          />
        )}
      </div>

      <Sheet
        onOpenChange={(open) => {
          setInspectorOpen(open);
          if (!open) {
            setSelectedJsonPath(ROOT_JSON_PATH);
          }
        }}
        open={inspectorOpen && selectedRow !== null}
      >
        <SheetContent className="min-h-0 w-full overflow-hidden gap-0 border-l border-slate-800/85 bg-[linear-gradient(180deg,rgba(10,15,22,0.98),rgba(8,12,19,0.95))] p-0 text-slate-100 shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-[620px] [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-slate-500 [&>button]:hover:bg-slate-800/80 [&>button]:hover:text-slate-100">
          <SheetHeader className="px-5 pb-1 pt-4 pr-16 text-left">
            <SheetTitle className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">
              line:{selectedRow?.lineNumber ?? "--"}
            </SheetTitle>
          </SheetHeader>

          <div className="min-h-0 flex-1 px-4 pb-4 pt-1">
            <div className="console-scrollbar-drawer h-full overflow-y-auto pl-1 pr-2">
              {selectedRow ? (
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
                  value={selectedRow.record}
                />
              ) : null}
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function JsonlTableView({
  activeRowLineNumber,
  columns,
  onSelectRow,
  rows
}: {
  activeRowLineNumber: number | null;
  columns: string[];
  onSelectRow: (row: JsonlPreviewRow) => void;
  rows: JsonlPreviewRow[];
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {rows.length > 0 ? (
        <ConsoleListTableSurface className="min-h-0 flex-1">
          <div className="console-scrollbar-subtle h-full overflow-auto">
            <Table className="min-w-[980px] table-fixed">
              <TableHeader className="bg-transparent">
                <TableRow className="hover:bg-transparent">
                  <TableHead className={previewStickyHeadClassName}>行</TableHead>
                  {columns.map((column) => (
                    <TableHead
                      className="sticky top-0 z-10 min-w-[180px] bg-[rgba(13,18,25,0.92)]"
                      key={column}
                    >
                      {column}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const isActive = row.lineNumber === activeRowLineNumber;

                  return (
                    <TableRow
                      className={cn(
                        "cursor-pointer bg-transparent",
                        isActive ? "bg-[rgba(29,41,58,0.48)] hover:bg-[rgba(29,41,58,0.58)]" : null
                      )}
                      key={row.lineNumber}
                      onClick={() => onSelectRow(row)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectRow(row);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <TableCell
                        className={cn(
                          previewStickyCellClassName,
                          isActive
                            ? "bg-[rgba(29,41,58,0.82)] text-slate-100"
                            : "bg-[rgba(13,18,25,0.84)] text-slate-400"
                        )}
                      >
                        {row.lineNumber}
                      </TableCell>
                      {columns.map((column) => (
                        <TableCell
                          className="max-w-[320px] align-top text-[13px] leading-6 text-zinc-300"
                          key={`${row.lineNumber}-${column}`}
                        >
                          <div className="line-clamp-3 break-words">
                            {formatJsonlValuePreview(row.record[column])}
                          </div>
                        </TableCell>
                      ))}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </ConsoleListTableSurface>
      ) : (
        <EmptyPreviewPanel
          description="当前预览内容还不足以生成结构化表格。"
          title="暂无可展示的 JSONL 记录"
        />
      )}
    </div>
  );
}

function JsonlRawView({
  content,
  parseErrors,
  rows
}: {
  content: string;
  parseErrors: JsonlPreviewParseError[];
  rows: JsonlPreviewRow[];
}) {
  return (
    <div className="grid min-h-0 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-h-0 overflow-y-auto p-4">
        <pre className="min-h-full overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-slate-800 bg-[rgba(5,8,13,0.58)] p-4 font-mono text-[12px] leading-7 text-zinc-300">
          {content || "当前版本暂无可预览的文件内容。"}
        </pre>
      </div>

      <aside className="min-h-0 overflow-y-auto border-l border-slate-800/70 bg-[rgba(8,12,19,0.34)] px-4 py-4">
        <div className="space-y-4">
          <InspectorCard label="样本条数" value={String(rows.length)} />
          <InspectorCard label="解析异常" value={`${parseErrors.length} 行`} />

          <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-100">使用建议</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm leading-6 text-zinc-400">
              <p>Raw 视图适合精确检查转义、空行、非法 JSON 以及多行内容。</p>
              <p>如果结构稳定，优先使用“表格预览”来做质量检查。</p>
            </CardContent>
          </Card>

          {parseErrors.length > 0 ? (
            <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-zinc-100">异常行</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-xs text-zinc-400">
                {parseErrors.slice(0, 5).map((error) => (
                  <div
                    className="rounded-xl border border-slate-800 bg-[rgba(255,255,255,0.03)] px-3 py-2"
                    key={`${error.lineNumber}-${error.message}`}
                  >
                    第 {error.lineNumber} 行: {error.message}
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </aside>
    </div>
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
      <div className="font-mono text-[12px] leading-7 text-slate-200">
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

function DatasetVersionDetailTab({
  dataset,
  version
}: {
  dataset: DatasetDetail;
  version: DatasetVersionSummary;
}) {
  return (
    <div className="min-h-0 overflow-y-auto p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-3">
                  <div className="inline-flex rounded-full border border-slate-700 bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-xs font-medium text-zinc-200">
                    V{version.version}
                  </div>
                  <CardTitle className="text-lg text-zinc-100">
                    {getVersionDescription(dataset, version)}
                  </CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="数据量" value={formatNumber(version.record_count)} />
              <MetricCard label="预估 Tokens" value={formatNumber(getEstimatedTokens(version))} />
              <MetricCard label="创建时间" value={formatDateTime(version.created_at)} />
              <MetricCard
                label="更新时间"
                value={formatDateTime(version.updated_at ?? version.created_at)}
              />
            </CardContent>
          </Card>

          <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-100">版本说明</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-zinc-300">
              <DetailRow label="描述" value={version.description || dataset.description || "--"} />
              <DetailRow label="来源类型" value={version.source_type || "--"} />
              <DetailRow label="来源路径" value={version.source_uri || "--"} />
              <DetailRow label="创建人" value={version.created_by || dataset.owner_name || "--"} />
            </CardContent>
          </Card>
        </div>

        <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-100">文件清单</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {getVersionFileEntries(version).map((file) => (
                <div
                  className="rounded-2xl border border-slate-800 bg-[rgba(255,255,255,0.03)] px-3 py-3"
                  key={file.id}
                >
                  <div className="flex items-start gap-3">
                    <FileJson2 className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-zinc-100">{file.file_name}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
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
          ? "border-slate-200 bg-slate-100 text-slate-950"
          : "border-slate-800 bg-[rgba(255,255,255,0.03)] text-zinc-400 hover:bg-slate-800/70 hover:text-zinc-100"
      )}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function PreviewModeButton({
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
        "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition-colors",
        active
          ? "border-sky-200 bg-sky-100 text-sky-950"
          : "border-slate-800 bg-[rgba(255,255,255,0.03)] text-zinc-400 hover:bg-slate-800/70 hover:text-zinc-100"
      )}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function InspectorCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[rgba(255,255,255,0.03)] px-3 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div className="mt-2 text-base font-medium text-zinc-100">{value}</div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[rgba(255,255,255,0.03)] px-4 py-4">
      <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div className="mt-3 text-lg font-medium text-zinc-100">{value}</div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div className="break-all text-sm text-zinc-200">{value}</div>
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
          "rounded-2xl border px-4 py-3 text-sm",
          intent === "error"
            ? "border-rose-900/40 bg-rose-950/20 text-rose-300"
            : "border-slate-800 bg-[rgba(255,255,255,0.03)] text-zinc-400"
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
        <div className="text-base font-medium text-zinc-100">{title}</div>
        <div className="text-sm leading-6 text-zinc-500">{description}</div>
      </div>
    </div>
  );
}

function ActionMenu({
  chrome = "default",
  disabled,
  onDelete,
  onOpenChange,
  open,
  size = "default"
}: {
  chrome?: "default" | "plain";
  disabled: boolean;
  onDelete: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  size?: "default" | "icon-sm";
}) {
  return (
    <DropdownMenu onOpenChange={onOpenChange} open={open}>
      <DropdownMenuTrigger asChild>
        <Button
          aria-label="更多操作"
          className={cn(
            "px-0",
            size === "icon-sm"
              ? "h-8 w-8 rounded-md border-transparent bg-transparent text-zinc-500 shadow-none hover:bg-[rgba(255,255,255,0.04)] hover:text-zinc-100"
              : chrome === "plain"
                ? "h-9 w-9 rounded-md border-transparent bg-transparent text-zinc-400 shadow-none hover:bg-[rgba(255,255,255,0.04)] hover:text-zinc-100"
                : "h-9 w-9 border-slate-800 bg-[rgba(255,255,255,0.03)] text-zinc-400 hover:bg-slate-800/70 hover:text-zinc-100"
          )}
          disabled={disabled}
          size="sm"
          type="button"
          variant={size === "icon-sm" || chrome === "plain" ? "ghost" : "outline"}
        >
          <Ellipsis className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-32">
        <DropdownMenuItem onSelect={onDelete}>删除</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function DeleteConfirmDialog({
  confirmLabel,
  description,
  onClose,
  onConfirm,
  open,
  pending,
  title
}: {
  confirmLabel: string;
  description: string;
  onClose: () => void;
  onConfirm: () => void;
  open: boolean;
  pending: boolean;
  title: string;
}) {
  return (
    <AlertDialog
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !pending) {
          onClose();
        }
      }}
      open={open}
    >
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>取消</AlertDialogCancel>
          <AlertDialogAction
            className="bg-red-500/90 text-white hover:bg-red-500"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? "处理中..." : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function buildJsonlPreview(content: string): JsonlPreviewResult {
  const lines = content.split(/\r?\n/);
  const rows: JsonlPreviewRow[] = [];
  const parseErrors: JsonlPreviewParseError[] = [];
  const stats = new Map<
    string,
    {
      presenceCount: number;
      nonNullCount: number;
      types: Set<string>;
      sample: string;
    }
  >();
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
        raw: line,
        record
      });

      Object.entries(record).forEach(([key, value]) => {
        const existing = stats.get(key) ?? {
          presenceCount: 0,
          nonNullCount: 0,
          types: new Set<string>(),
          sample: "—"
        };

        existing.presenceCount += 1;
        if (value !== null && value !== undefined) {
          existing.nonNullCount += 1;
          existing.sample = existing.sample === "—" ? summarizeJsonlValue(value) : existing.sample;
        }
        existing.types.add(getJsonValueType(value));
        stats.set(key, existing);
      });
    } catch (error) {
      parseErrors.push({
        lineNumber: index + 1,
        message: error instanceof Error ? error.message : "JSON 解析失败",
        raw: line
      });
    }
  });

  const columns = Array.from(stats.entries())
    .map(([key, value]) => ({
      key,
      presenceCount: value.presenceCount
    }));

  return {
    rows,
    columns: selectJsonlColumns(columns),
    parseErrors,
    totalLines
  };
}

function selectJsonlColumns(
  fields: Array<{
    key: string;
    presenceCount: number;
  }>
) {
  if (fields.length === 0) {
    return ["value"];
  }

  const ordered = [...fields].sort((left, right) => {
    const preferredOrder = getPreferredColumnOrder(left.key) - getPreferredColumnOrder(right.key);
    if (preferredOrder !== 0) {
      return preferredOrder;
    }
    return right.presenceCount - left.presenceCount;
  });

  return ordered.slice(0, 6).map((field) => field.key);
}

function getPreferredColumnOrder(key: string) {
  const index = PREFERRED_JSONL_COLUMNS.indexOf(key);
  return index === -1 ? PREFERRED_JSONL_COLUMNS.length + 1 : index;
}

function formatJsonlValuePreview(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "string") {
    return value.replace(/\s+/g, " ").trim() || "空字符串";
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return summarizeJsonlValue(value);
}

function summarizeJsonlValue(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "string") {
    return compactText(value);
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  try {
    return compactText(JSON.stringify(value) ?? "—");
  } catch {
    return "不可序列化值";
  }
}

function compactText(value: string, maxLength = 96) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "空字符串";
  }

  if (normalized.length <= maxLength) {
    return normalized;
  }

  return `${normalized.slice(0, maxLength - 1)}…`;
}

function getJsonValueType(value: unknown) {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return "array";
  }
  return typeof value === "object" ? "object" : typeof value;
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
              className="mt-[3px] flex h-5 w-5 shrink-0 items-center justify-center rounded text-slate-500 transition-colors hover:bg-slate-800/70 hover:text-slate-100"
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
                ? "bg-[rgba(36,54,78,0.72)] text-slate-100"
                : "text-slate-300 hover:bg-[rgba(255,255,255,0.03)] hover:text-slate-100"
            )}
            onClick={() => onSelectPath(path)}
            type="button"
          >
            <span className="shrink-0 text-sky-300">{label}</span>
            <span className="shrink-0 text-slate-500">:</span>
            {container ? (
              <span className="truncate text-slate-500">{summarizeJsonContainer(child)}</span>
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
    return <span className="text-slate-500">null</span>;
  }

  if (typeof value === "string") {
    return <span className="break-words text-emerald-300">"{value}"</span>;
  }

  if (typeof value === "number") {
    return <span className="text-amber-300">{value}</span>;
  }

  if (typeof value === "boolean") {
    return <span className="text-sky-300">{String(value)}</span>;
  }

  if (value === undefined) {
    return <span className="text-slate-500">undefined</span>;
  }

  return <span className="break-words text-slate-300">{String(value)}</span>;
}

function getVersionDescription(dataset: DatasetDetail, version: DatasetVersionSummary) {
  return version.description || dataset.description || version.file_name || dataset.name;
}

function getResolvedPreviewTarget(
  versions: DatasetVersionSummary[],
  preferredVersionId: string,
  preferredFileId: string
) {
  const fallbackVersion = versions[0] ?? null;
  const fallbackFileId = fallbackVersion?.files[0]?.id ?? "";
  const preferredVersion =
    versions.find((version) => version.id === preferredVersionId) ?? fallbackVersion;

  if (!preferredVersion) {
    return { versionId: "", fileId: "" };
  }

  if (preferredVersion.files.length === 0) {
    return { versionId: preferredVersion.id, fileId: "" };
  }

  const resolvedFileId = preferredVersion.files.some((file) => file.id === preferredFileId)
    ? preferredFileId
    : preferredVersion.files[0]?.id ?? fallbackFileId;

  return {
    versionId: preferredVersion.id,
    fileId: resolvedFileId
  };
}

function getVersionFileEntries(version: DatasetVersionSummary): DatasetFileSummary[] {
  if (version.files.length > 0) {
    return version.files;
  }

  return [
    {
      id: DEFAULT_PREVIEW_FILE_KEY,
      version_id: version.id,
      file_name: getVersionFileLabel(version),
      object_key: version.object_key ?? "",
      created_at: version.created_at,
      updated_at: version.updated_at ?? version.created_at
    }
  ];
}

function getVersionFileLabel(version: DatasetVersionSummary) {
  if (version.files[0]?.file_name) {
    return version.files[0].file_name;
  }

  if (version.file_name) {
    return version.file_name;
  }

  if (version.object_key) {
    const parts = version.object_key.split("/");
    return parts[parts.length - 1] || version.object_key;
  }

  if (version.source_uri) {
    return version.source_uri;
  }

  return "dataset.jsonl";
}

function getPreviewCacheKey(versionId: string, fileId: string) {
  return `${versionId}:${fileId}`;
}

function getEstimatedTokens(version: DatasetVersionSummary) {
  if (version.record_count === 1) {
    return 83;
  }

  if (typeof version.record_count === "number" && version.record_count > 0) {
    return Math.max(83, Math.round(version.record_count * 218.75));
  }

  return null;
}

function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }

  return value.toLocaleString("zh-CN");
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false
  });
}
