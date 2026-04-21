import Link from "next/link";
import { Pencil } from "lucide-react";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
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
            <TableHead className="w-[96px] text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-muted-foreground" colSpan={6}>
                当前还没有评测维度。请先创建一个可复用的评测维度，再用于自定义 Benchmark。
              </TableCell>
            </TableRow>
          ) : (
            dimensions.map((dimension) => (
              <TableRow key={dimension.id}>
                <TableCell className="min-w-[260px] align-top">
                  <div className="font-medium text-foreground">{dimension.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">v{dimension.version}</div>
                  {dimension.description ? (
                    <div className="mt-2 max-w-[480px] text-sm leading-6 text-muted-foreground">
                      {dimension.description}
                    </div>
                  ) : null}
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {getTemplateTypeLabel(dimension.template_type)}
                </TableCell>
                <TableCell className="align-top">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{getPresetLabel(dimension.preset_id)}</Badge>
                    <Badge variant="secondary">{dimension.output_type}</Badge>
                  </div>
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {formatJudgeModel(dimension)}
                </TableCell>
                <TableCell className="align-top text-muted-foreground">
                  {formatDateTime(dimension.created_at)}
                </TableCell>
                <TableCell className="align-top text-right">
                  <Link
                    className={buttonVariants({ size: "sm", variant: "outline" })}
                    href={`/model/eval-templates/${encodeURIComponent(dimension.name)}/edit`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    编辑
                  </Link>
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

function formatJudgeModel(dimension: EvalTemplateSummary) {
  if (dimension.model && dimension.provider) {
    return `${dimension.model} @ ${dimension.provider}`;
  }
  return dimension.model || dimension.provider || "跟随任务配置";
}
