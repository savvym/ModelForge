import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { EvalSpecDatasetFileSummaryV2, EvalSpecSummaryV2 } from "@/types/api";

function formatBytes(value?: number | null) {
  if (value == null || Number.isNaN(value)) {
    return "--";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  if (value < 1024 * 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
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

function humanizeDatasetStatus(status: string) {
  switch (status) {
    case "available":
      return "已就绪";
    case "external":
      return "外部提供";
    case "syncing":
      return "拉取中";
    case "failed":
      return "拉取失败";
    case "missing":
      return "缺失";
    default:
      return status;
  }
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.68)] px-4 py-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-sm text-slate-100">{value}</div>
    </div>
  );
}

function DatasetFileTable({ files }: { files: EvalSpecDatasetFileSummaryV2[] }) {
  if (files.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
        当前版本未配置显式数据集文件。
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800/80">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>文件</TableHead>
            <TableHead>角色</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>来源</TableHead>
            <TableHead>对象存储</TableHead>
            <TableHead>大小</TableHead>
            <TableHead>最近同步</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((file) => (
            <TableRow key={file.id}>
              <TableCell className="min-w-[220px] align-top">
                <div className="font-medium text-slate-100">{file.display_name}</div>
                <div className="mt-1 text-xs text-slate-500">{file.file_key}</div>
                {file.file_name ? <div className="mt-2 text-xs text-slate-400">{file.file_name}</div> : null}
              </TableCell>
              <TableCell>
                <div className="space-y-1 text-sm text-slate-300">
                  <div>{file.role}</div>
                  <div className="text-xs text-slate-500">
                    {file.format || "--"}
                    {file.is_required ? " · 必需" : " · 可选"}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{humanizeDatasetStatus(file.status)}</Badge>
                {file.error_message ? (
                  <div className="mt-2 max-w-[220px] text-xs text-rose-300">{file.error_message}</div>
                ) : null}
              </TableCell>
              <TableCell className="max-w-[280px] break-all text-xs text-slate-400">
                {file.source_uri || "--"}
              </TableCell>
              <TableCell className="max-w-[280px] break-all text-xs text-slate-400">
                {file.object_key || "--"}
              </TableCell>
              <TableCell className="text-sm text-slate-300">{formatBytes(file.size_bytes)}</TableCell>
              <TableCell className="text-sm text-slate-300">{formatDateTime(file.last_synced_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function JsonBlock({ value }: { value: Record<string, unknown> }) {
  if (Object.keys(value).length === 0) {
    return <div className="text-sm text-slate-500">当前为空。</div>;
  }

  return (
    <pre className="overflow-x-auto rounded-2xl border border-slate-800/80 bg-[rgba(8,13,20,0.92)] p-4 text-xs leading-6 text-slate-300">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function EvalSpecDetailPanel({ spec }: { spec: EvalSpecSummaryV2 }) {
  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-50">{spec.display_name}</h1>
            <Badge variant="outline">{spec.name}</Badge>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate-400">
            {spec.description || "当前评测类型没有额外描述。"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval?tab=catalog">
            返回管理
          </Link>
          <Link
            className={buttonVariants({ size: "sm", variant: "outline" })}
            href={`/model/eval-specs/${encodeURIComponent(spec.name)}/edit`}
          >
            编辑评测类型
          </Link>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="能力分组" value={spec.capability_group || "--"} />
        <SummaryCard label="能力分类" value={spec.capability_category || "--"} />
        <SummaryCard label="版本数量" value={String(spec.versions.length)} />
        <SummaryCard
          label="标签"
          value={spec.tags_json.length ? spec.tags_json.map((item) => String(item)).join(" / ") : "--"}
        />
      </section>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader>
          <CardTitle className="text-base text-slate-50">输入 / 输出契约</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-3">
            <div className="text-sm font-medium text-slate-200">输入 Schema</div>
            <JsonBlock value={spec.input_schema_json} />
          </div>
          <div className="space-y-3">
            <div className="text-sm font-medium text-slate-200">输出 Schema</div>
            <JsonBlock value={spec.output_schema_json} />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {spec.versions.map((version) => (
          <Card
            className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none"
            key={version.id}
          >
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base text-slate-50">{version.display_name}</CardTitle>
                    <Badge variant="outline">{version.version}</Badge>
                    {version.is_recommended ? <Badge>推荐</Badge> : null}
                    {version.enabled ? <Badge variant="outline">启用中</Badge> : <Badge variant="outline">已停用</Badge>}
                  </div>
                  <p className="max-w-3xl text-sm leading-6 text-slate-400">
                    {version.description || "当前版本没有额外描述。"}
                  </p>
                </div>
                <div className="grid gap-2 text-right text-sm text-slate-300">
                  <div>{version.engine} / {version.execution_mode}</div>
                  <div className="text-xs text-slate-500">
                    benchmark: {version.engine_benchmark_name || "--"}
                  </div>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <SummaryCard label="样本量" value={version.sample_count != null ? String(version.sample_count) : "--"} />
                <SummaryCard label="数据入口" value={version.dataset_source_uri || "--"} />
                <SummaryCard label="数据文件数" value={String(version.dataset_files.length)} />
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-200">数据集文件</div>
                <DatasetFileTable files={version.dataset_files} />
              </div>
              <div className="grid gap-4 xl:grid-cols-2">
                <div className="space-y-3">
                  <div className="text-sm font-medium text-slate-200">执行配置</div>
                  <JsonBlock value={version.engine_config_json} />
                </div>
                <div className="space-y-3">
                  <div className="text-sm font-medium text-slate-200">评分配置</div>
                  <JsonBlock value={version.scoring_config_json} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
