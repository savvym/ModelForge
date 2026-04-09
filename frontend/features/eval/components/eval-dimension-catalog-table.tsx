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
import type { EvalTemplateSummary } from "@/types/api";

export function EvalDimensionCatalogTable({
  dimensions
}: {
  dimensions: EvalTemplateSummary[];
}) {
  const empty = dimensions.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>评测维度</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>评分器</TableHead>
            <TableHead>裁判模型</TableHead>
            <TableHead>创建时间</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={5}>
                当前还没有评测维度。请先创建一个可复用的评测维度，再用于自定义 Benchmark。
              </TableCell>
            </TableRow>
          ) : (
            dimensions.map((dimension) => (
              <TableRow key={dimension.id}>
                <TableCell className="min-w-[260px] align-top">
                  <div className="font-medium text-slate-100">{dimension.name}</div>
                  <div className="mt-1 text-xs text-slate-500">v{dimension.version}</div>
                  {dimension.description ? (
                    <div className="mt-2 max-w-[480px] text-sm leading-6 text-slate-400">
                      {dimension.description}
                    </div>
                  ) : null}
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {getTemplateTypeLabel(dimension.template_type)}
                </TableCell>
                <TableCell className="align-top">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{getPresetLabel(dimension.preset_id)}</Badge>
                    <Badge variant="secondary">{dimension.output_type}</Badge>
                  </div>
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {dimension.model || "跟随任务配置"}
                </TableCell>
                <TableCell className="align-top text-slate-400">
                  {formatDateTime(dimension.created_at)}
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
