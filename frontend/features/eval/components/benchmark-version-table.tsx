import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { BenchmarkDefinitionSummary } from "@/types/api";

export function BenchmarkVersionTable({
  benchmark
}: {
  benchmark: BenchmarkDefinitionSummary;
}) {
  const empty = benchmark.versions.length === 0;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Version</TableHead>
          <TableHead>说明</TableHead>
          <TableHead>数据源</TableHead>
          <TableHead>样本数</TableHead>
          <TableHead>任务数</TableHead>
          <TableHead>最近运行</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {empty ? (
          <TableRow className="hover:bg-transparent">
            <TableCell className="py-12 text-center text-sm text-slate-500" colSpan={8}>
              当前 Benchmark 还没有注册 Version。
            </TableCell>
          </TableRow>
        ) : (
          benchmark.versions.map((version) => (
            <TableRow key={version.id}>
              <TableCell className="min-w-[240px] align-top">
                <div className="font-medium text-slate-100">{version.display_name}</div>
                <div className="mt-1 font-mono text-xs text-slate-500">{version.id}</div>
              </TableCell>
              <TableCell className="max-w-[360px] whitespace-pre-wrap text-sm leading-6 text-slate-400">
                {version.description}
              </TableCell>
              <TableCell className="max-w-[420px] break-all text-xs leading-6 text-slate-400">
                {version.dataset_source_uri ||
                  (version.dataset_path ? `legacy local: ${version.dataset_path}` : "--")}
              </TableCell>
              <TableCell className="align-top text-slate-300">
                {version.sample_count.toLocaleString()}
              </TableCell>
              <TableCell className="align-top text-slate-300">
                {version.eval_job_count.toLocaleString()}
              </TableCell>
              <TableCell className="align-top text-slate-400">
                {formatDateTime(version.latest_eval_at)}
              </TableCell>
              <TableCell className="align-top">
                <Badge variant={version.enabled ? "outline" : "secondary"}>
                  {version.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </TableCell>
              <TableCell className="text-right align-top">
                <Link
                  className="text-sm text-sky-300 transition-colors hover:text-sky-200"
                  href={`/model/eval-benchmarks/${benchmark.name}/versions/${version.id}/edit`}
                >
                  编辑
                </Link>
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
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
