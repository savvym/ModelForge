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
import type { BenchmarkDefinitionSummary } from "@/types/api";

export function BenchmarkCatalogTable({
  benchmarks,
  emptyMessage
}: {
  benchmarks: BenchmarkDefinitionSummary[];
  emptyMessage: string;
}) {
  const empty = benchmarks.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Benchmark</TableHead>
            <TableHead>来源</TableHead>
            <TableHead>版本数</TableHead>
            <TableHead>评测维度</TableHead>
            <TableHead>任务数</TableHead>
            <TableHead>最近运行</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={6}>
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            benchmarks.map((benchmark) => (
              <TableRow key={benchmark.name}>
                <TableCell className="min-w-[280px] align-top">
                  <Link className="block" href={`/model/eval-benchmarks/${benchmark.name}`}>
                    <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                      {benchmark.display_name}
                    </div>
                    <div className="mt-1 font-mono text-xs text-slate-500">{benchmark.name}</div>
                    {benchmark.description ? (
                      <div className="mt-2 max-w-[520px] text-sm leading-6 text-slate-400">
                        {benchmark.description}
                      </div>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {benchmark.category ? (
                        <Badge variant="outline">{benchmark.category}</Badge>
                      ) : null}
                      {benchmark.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </Link>
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant={benchmark.source_type === "builtin" ? "outline" : "secondary"}>
                    {benchmark.source_type === "builtin" ? "平台预置" : "自定义"}
                  </Badge>
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {benchmark.enabled_version_count}/{benchmark.version_count}
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
                      <div className="text-xs text-slate-500">绑定评测维度</div>
                    </div>
                  ) : benchmark.source_type === "builtin" ? (
                    <span className="text-slate-400">平台预置规则</span>
                  ) : (
                    <span className="text-slate-500">未绑定</span>
                  )}
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
