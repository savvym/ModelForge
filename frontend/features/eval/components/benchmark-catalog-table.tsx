import Link from "next/link";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { getPresetLabel, getTemplateTypeLabel } from "@/features/eval/eval-template-meta";
import { formatEvalMethod } from "@/features/eval/status";
import type { BenchmarkDefinitionSummary } from "@/types/api";

export function BenchmarkCatalogTable({
  benchmarks
}: {
  benchmarks: BenchmarkDefinitionSummary[];
}) {
  const empty = benchmarks.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Benchmark</TableHead>
            <TableHead>版本数</TableHead>
            <TableHead>默认评测方式</TableHead>
            <TableHead>评测模板</TableHead>
            <TableHead>Judge</TableHead>
            <TableHead>任务数</TableHead>
            <TableHead>最近运行</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={7}>
                当前还没有自定义 Benchmark。请先创建一个模板驱动的 Benchmark，并上传至少一个
                Version 数据集。
              </TableCell>
            </TableRow>
          ) : (
            benchmarks.map((benchmark) => (
              <TableRow key={benchmark.name}>
                <TableCell className="min-w-[260px] align-top">
                  <Link className="block" href={`/model/eval-benchmarks/${benchmark.name}`}>
                    <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                      {benchmark.display_name}
                    </div>
                    <div className="mt-1 font-mono text-xs text-slate-500">{benchmark.name}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {benchmark.category ? (
                        <Badge variant="outline">{benchmark.category}</Badge>
                      ) : null}
                      {benchmark.tags.slice(0, 2).map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </Link>
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {benchmark.enabled_version_count}/{benchmark.version_count}
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {formatEvalMethod(benchmark.default_eval_method)}
                </TableCell>
                <TableCell className="min-w-[220px] align-top">
                  {benchmark.eval_template_name ? (
                    <div className="space-y-1">
                      <div className="text-slate-200">
                        {benchmark.eval_template_name}
                        {benchmark.eval_template_version != null
                          ? ` · v${benchmark.eval_template_version}`
                          : ""}
                      </div>
                      <div className="text-xs text-slate-500">
                        {getTemplateTypeLabel(benchmark.eval_template_type)}
                        {benchmark.eval_template_preset_id
                          ? ` · ${getPresetLabel(benchmark.eval_template_preset_id)}`
                          : ""}
                      </div>
                    </div>
                  ) : (
                    <span className="text-slate-500">--</span>
                  )}
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant={benchmark.requires_judge_model ? "default" : "outline"}>
                    {benchmark.requires_judge_model ? "Required" : "Optional"}
                  </Badge>
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {benchmark.eval_job_count.toLocaleString()}
                </TableCell>
                <TableCell className="align-top text-slate-400">
                  {formatDateTime(benchmark.latest_eval_at)}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
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
