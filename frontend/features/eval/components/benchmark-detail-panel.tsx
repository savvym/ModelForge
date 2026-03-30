"use client";

import * as React from "react";
import Link from "next/link";
import { Download } from "lucide-react";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
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
type PreviewMode = "table" | "raw";

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
  const versions = benchmark.versions;
  const [activeTab, setActiveTab] = React.useState<DetailTab>("details");
  const [previewMode, setPreviewMode] = React.useState<PreviewMode>("table");
  const [selectedVersionId, setSelectedVersionId] = React.useState(versions[0]?.id ?? "");
  const [previewCache, setPreviewCache] = React.useState<
    Record<string, ObjectStoreObjectPreviewResponse>
  >({});
  const [loadingPreviewVersionId, setLoadingPreviewVersionId] = React.useState<string | null>(null);
  const [previewError, setPreviewError] = React.useState<string | null>(null);

  const selectedVersion =
    versions.find((version) => version.id === selectedVersionId) ?? versions[0] ?? null;
  const selectedPreview = selectedVersion ? previewCache[selectedVersion.id] : undefined;
  React.useEffect(() => {
    if (!selectedVersion && versions.length > 0) {
      setSelectedVersionId(versions[0].id);
    }
  }, [selectedVersion, versions]);

  React.useEffect(() => {
    if (activeTab !== "preview" || !selectedVersion) {
      return;
    }

    if (!selectedVersion.dataset_source_uri && !selectedVersion.dataset_path) {
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
  }, [activeTab, previewCache, selectedVersion]);

  function handleDownloadSelectedVersion() {
    if (!selectedVersion) {
      return;
    }

    window.location.href = getBenchmarkVersionDownloadUrl(benchmark.name, selectedVersion.id);
  }

  return (
    <div className="flex h-full min-h-0 flex-1">
      <Card className="flex min-h-0 w-[320px] flex-col overflow-hidden rounded-none border-0 border-r border-slate-800/70 bg-transparent shadow-none">
        <CardHeader className="border-b border-slate-800/70 bg-transparent px-3 py-2.5">
          <div className="space-y-1">
            <div className="text-[13px] font-medium text-zinc-100">Versions</div>
            <div className="text-xs text-zinc-500">{versions.length} 个版本</div>
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
                        "w-full rounded-2xl border px-3 py-3 text-left transition-colors",
                        isActive
                          ? "border-slate-600 bg-[rgba(29,41,58,0.72)]"
                          : "border-slate-800/70 bg-[rgba(12,18,28,0.42)] hover:border-slate-700 hover:bg-[rgba(14,20,29,0.62)]"
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
                          <div className="truncate text-sm font-medium text-zinc-100">
                            {version.display_name}
                          </div>
                          <div className="mt-1 font-mono text-[11px] text-zinc-500">{version.id}</div>
                        </div>
                        <Badge variant={version.enabled ? "outline" : "secondary"}>
                          {version.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-zinc-500">
                        <span>{formatNumber(version.sample_count)} samples</span>
                        <span>{formatNumber(version.eval_job_count)} jobs</span>
                      </div>
                      {version.latest_eval_at ? (
                        <div className="mt-1 text-[11px] text-zinc-500">
                          最近运行 {formatDateTime(version.latest_eval_at)}
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="px-4 py-6 text-sm text-zinc-500">当前 Benchmark 还没有可展示的版本。</div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-none border-0 bg-transparent shadow-none">
        <CardHeader className="border-b border-slate-800/70 bg-transparent px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <PrimaryTabButton
                active={activeTab === "details"}
                label="版本详情"
                onClick={() => setActiveTab("details")}
              />
              <PrimaryTabButton
                active={activeTab === "preview"}
                label="数据预览"
                onClick={() => setActiveTab("preview")}
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {selectedVersion ? (
                <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/${selectedVersion.id}/edit`}>
                  <Button type="button" variant="outline">
                    编辑 Version
                  </Button>
                </Link>
              ) : null}
              <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/create`}>
                <Button type="button">新增 Version</Button>
              </Link>
            </div>
          </div>
        </CardHeader>

        <CardContent className="min-h-0 flex-1 p-0">
          {selectedVersion ? (
            activeTab === "details" ? (
              <BenchmarkVersionDetailTab
                benchmarkName={benchmark.name}
                version={selectedVersion}
              />
            ) : (
              <BenchmarkVersionPreviewTab
                loading={loadingPreviewVersionId === selectedVersion.id}
                onDownload={handleDownloadSelectedVersion}
                onPreviewModeChange={setPreviewMode}
                preview={selectedPreview}
                previewError={previewError}
                previewMode={previewMode}
                version={selectedVersion}
              />
            )
          ) : (
            <div className="flex min-h-[480px] items-center justify-center p-10 text-sm text-zinc-500">
              当前 Benchmark 还没有可展示的版本。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BenchmarkVersionDetailTab({
  benchmarkName,
  version
}: {
  benchmarkName: string;
  version: BenchmarkVersionSummary;
}) {
  return (
    <div className="min-h-0 overflow-y-auto p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
            <CardHeader className="pb-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-3">
                  <div className="inline-flex rounded-full border border-slate-700 bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-xs font-medium text-zinc-200">
                    {version.id}
                  </div>
                  <CardTitle className="text-lg text-zinc-100">{version.display_name}</CardTitle>
                </div>
                <Badge variant={version.enabled ? "outline" : "secondary"}>
                  {version.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="样本数" value={formatNumber(version.sample_count)} />
              <MetricCard label="任务数" value={formatNumber(version.eval_job_count)} />
              <MetricCard label="状态" value={version.enabled ? "已启用" : "已停用"} />
              <MetricCard label="最近运行" value={formatDateTime(version.latest_eval_at)} />
            </CardContent>
          </Card>

          <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-100">Version 信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-zinc-300">
              <DetailRow label="Benchmark" value={benchmarkName} />
              <DetailRow label="展示名称" value={version.display_name} />
              <DetailRow label="说明" value={version.description || "--"} />
              <DetailRow label="数据源 URI" value={version.dataset_source_uri || "--"} />
              <DetailRow label="旧路径" value={version.dataset_path || "--"} />
            </CardContent>
          </Card>
        </div>

        <Card className="border-slate-800/70 bg-[rgba(10,15,22,0.74)] shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-100">预览提示</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-zinc-400">
            <p>数据预览会直接读取当前 Version 绑定的对象存储文件，不再展示 benchmark 级别的样例和格式参考。</p>
            <p>如果你上传的是 JSONL，右侧支持表格预览和 Raw 预览，便于快速检查样本结构。</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BenchmarkVersionPreviewTab({
  loading,
  onDownload,
  onPreviewModeChange,
  preview,
  previewError,
  previewMode,
  version
}: {
  loading: boolean;
  onDownload: () => void;
  onPreviewModeChange: (mode: PreviewMode) => void;
  preview?: ObjectStoreObjectPreviewResponse;
  previewError: string | null;
  previewMode: PreviewMode;
  version: BenchmarkVersionSummary;
}) {
  const previewContent = preview?.content ?? "";
  const jsonlPreview = React.useMemo(() => buildJsonlPreview(previewContent), [previewContent]);
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

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-slate-800/70 px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-zinc-100">
              {preview?.file_name ?? version.dataset_source_uri ?? version.display_name}
            </div>
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
              label="Raw"
              onClick={() => onPreviewModeChange("raw")}
            />
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
        ) : previewMode === "table" ? (
          <JsonlTableView columns={jsonlPreview.columns} rows={jsonlPreview.rows} />
        ) : (
          <JsonlRawView
            content={previewContent}
            parseErrors={jsonlPreview.parseErrors}
            rows={jsonlPreview.rows}
          />
        )}
      </div>
    </div>
  );
}

function JsonlTableView({
  columns,
  rows
}: {
  columns: string[];
  rows: JsonlPreviewRow[];
}) {
  return rows.length > 0 ? (
    <ConsoleListTableSurface className="min-h-0 flex-1">
      <div className="console-scrollbar-subtle h-full overflow-auto">
        <Table className="min-w-[980px] table-fixed">
          <TableHeader className="bg-transparent">
            <TableRow className="hover:bg-transparent">
              <TableHead className="sticky left-0 top-0 z-20 w-[96px] min-w-[96px] bg-[rgba(13,18,25,0.92)]">
                行
              </TableHead>
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
            {rows.map((row) => (
              <TableRow className="bg-transparent" key={row.lineNumber}>
                <TableCell className="sticky left-0 z-10 w-[96px] min-w-[96px] bg-[rgba(13,18,25,0.84)] align-top font-medium text-slate-400">
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
            ))}
          </TableBody>
        </Table>
      </div>
    </ConsoleListTableSurface>
  ) : (
    <EmptyPreviewPanel
      description="当前预览内容还不足以生成结构化表格。"
      title="暂无可展示的 JSONL 记录"
    />
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
              <p>Raw 视图更适合检查转义、空行和非法 JSON。</p>
              <p>如果结构稳定，优先使用“表格预览”做样本抽查。</p>
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

function InspectorCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[rgba(255,255,255,0.03)] px-3 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">{label}</div>
      <div className="mt-2 text-base font-medium text-zinc-100">{value}</div>
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
