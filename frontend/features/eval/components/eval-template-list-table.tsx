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
import {
  getPresetLabel,
  getTemplateTypeLabel,
  OUTPUT_TYPE_LABELS,
} from "@/features/eval/eval-template-meta";
import type { EvalTemplateSummary } from "@/types/api";

export function EvalTemplateListTable({
  templates
}: {
  templates: EvalTemplateSummary[];
}) {
  const empty = templates.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>模板名称</TableHead>
            <TableHead>版本</TableHead>
            <TableHead>评测类型</TableHead>
            <TableHead>预设</TableHead>
            <TableHead>输出类型</TableHead>
            <TableHead>变量</TableHead>
            <TableHead>Judge 模型</TableHead>
            <TableHead>创建时间</TableHead>
            <TableHead className="w-[96px] text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-muted-foreground" colSpan={9}>
                暂无评测模板。点击右上角「创建模板」开始。
              </TableCell>
            </TableRow>
          ) : (
            templates.map((template) => (
              <TableRow key={template.id}>
                <TableCell className="min-w-[200px] align-top">
                  <Link className="block" href={`/model/eval-templates/${template.name}`}>
                    <div className="font-medium text-foreground transition-colors hover:text-primary">
                      {template.name}
                    </div>
                    {template.description ? (
                      <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {template.description}
                      </div>
                    ) : null}
                  </Link>
                </TableCell>
                <TableCell className="align-top">
                  <Badge variant="outline">v{template.version}</Badge>
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {getTemplateTypeLabel(template.template_type)}
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {getPresetLabel(template.preset_id)}
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {OUTPUT_TYPE_LABELS[template.output_type] ?? template.output_type}
                </TableCell>
                <TableCell className="align-top">
                  <div className="flex flex-wrap gap-1">
                    {template.vars.map((v) => (
                      <code key={v} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        {`{{${v}}}`}
                      </code>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="align-top text-foreground">
                  {formatJudgeModel(template)}
                </TableCell>
                <TableCell className="align-top text-muted-foreground">
                  {formatDateTime(template.created_at)}
                </TableCell>
                <TableCell className="align-top text-right">
                  <Link
                    className={buttonVariants({ size: "sm", variant: "outline" })}
                    href={`/model/eval-templates/${encodeURIComponent(template.name)}/edit`}
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
  if (!value) return "--";
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatJudgeModel(template: EvalTemplateSummary) {
  if (template.model && template.provider) {
    return `${template.model} @ ${template.provider}`;
  }
  return template.model || template.provider || "--";
}
