import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
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
import { getEvalTemplate, getEvalTemplateVersions } from "@/features/eval/api";

export default async function EvalTemplateDetailPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const [template, versions] = await Promise.all([
    getEvalTemplate(name).catch(() => null),
    getEvalTemplateVersions(name).catch(() => [])
  ]);

  if (!template) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-slate-800/70 pb-4">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "评测模板", href: "/model/eval?tab=templates" },
            { label: template.name }
          ]}
        />
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-[28px] font-semibold tracking-tight text-slate-50">
            {template.name}
          </h1>
          <Badge variant="outline">v{template.version}</Badge>
          <Badge variant="secondary">{getTemplateTypeLabel(template.template_type)}</Badge>
          <Badge variant="secondary">
            {OUTPUT_TYPE_LABELS[template.output_type] ?? template.output_type}
          </Badge>
        </div>
        {template.description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            {template.description}
          </p>
        ) : null}
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">Prompt 模板（最新版）</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] p-4 text-xs leading-6 text-slate-300">
              {template.prompt}
            </pre>
            <div className="mt-3 flex flex-wrap gap-2">
              {template.vars.map((v) => (
                <code key={v} className="rounded bg-muted px-2 py-0.5 text-xs">
                  {`{{${v}}}`}
                </code>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">输出配置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <DetailItem label="评测类型" value={getTemplateTypeLabel(template.template_type)} />
              <DetailItem label="预设" value={getPresetLabel(template.preset_id)} />
              <DetailItem label="输出类型" value={OUTPUT_TYPE_LABELS[template.output_type] ?? template.output_type} />
              <DetailItem label="Judge 模型" value={template.model ?? "使用任务级配置"} />
            </div>
            {renderConfigSummary(template.output_config)}
            <pre className="overflow-x-auto rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] p-4 text-xs leading-6 text-slate-300">
              {JSON.stringify(template.output_config, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <h2 className="text-base font-semibold text-slate-50">版本历史</h2>
        <ConsoleListTableSurface>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>评测类型</TableHead>
                <TableHead>输出类型</TableHead>
                <TableHead>变量</TableHead>
                <TableHead>Judge 模型</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((v) => (
                <TableRow key={v.id}>
                  <TableCell>
                    <Badge variant={v.version === template.version ? "default" : "outline"}>
                      v{v.version}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-slate-300">
                    {getTemplateTypeLabel(v.template_type)}
                  </TableCell>
                  <TableCell className="text-slate-300">
                    {OUTPUT_TYPE_LABELS[v.output_type] ?? v.output_type}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {v.vars.map((varName) => (
                        <code key={varName} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                          {`{{${varName}}}`}
                        </code>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-slate-300">{v.model ?? "--"}</TableCell>
                  <TableCell className="text-slate-400">{formatDateTime(v.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ConsoleListTableSurface>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 break-all text-sm text-slate-100">{value}</div>
    </div>
  );
}

function renderConfigSummary(outputConfig: Record<string, unknown>) {
  const details = getConfigSummaryRows(outputConfig);
  if (details.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {details.map((detail) => (
        <div
          key={detail.label}
          className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3"
        >
          <div className="text-xs uppercase tracking-wide text-slate-500">{detail.label}</div>
          <div className="mt-1 text-sm text-slate-100">{detail.value}</div>
        </div>
      ))}
    </div>
  );
}

function getConfigSummaryRows(outputConfig: Record<string, unknown>) {
  const rows: Array<{ label: string; value: string }> = [];

  const labelGroups = outputConfig.label_groups;
  if (Array.isArray(labelGroups) && labelGroups.length > 0) {
    const formattedGroups = labelGroups
      .flatMap((group) => {
        if (!group || typeof group !== "object") return [];
        const groupRecord = group as Record<string, unknown>;
        const groupLabel = String(groupRecord.label ?? groupRecord.key ?? "分组");
        const labels = Array.isArray(groupRecord.labels)
          ? groupRecord.labels.map((label) => String(label)).join(", ")
          : "";
        return labels ? [`${groupLabel}: ${labels}`] : [];
      })
      .join(" | ");
    if (formattedGroups) {
      rows.push({ label: "标签分组", value: formattedGroups });
    }
  }

  const numericRange =
    outputConfig.numeric_range && typeof outputConfig.numeric_range === "object"
      ? (outputConfig.numeric_range as Record<string, unknown>)
      : null;
  const scoreMin = numericRange?.min ?? outputConfig.score_min;
  const scoreMax = numericRange?.max ?? outputConfig.score_max;
  const passThreshold = numericRange?.pass_threshold ?? outputConfig.pass_threshold;
  if (scoreMin != null && scoreMax != null) {
    rows.push({ label: "评分范围", value: `${scoreMin} - ${scoreMax}` });
  }
  if (passThreshold != null) {
    rows.push({ label: "通过阈值", value: String(passThreshold) });
  }

  const ruleConfig =
    outputConfig.rule_config && typeof outputConfig.rule_config === "object"
      ? (outputConfig.rule_config as Record<string, unknown>)
      : null;
  if (ruleConfig?.operator) {
    rows.push({ label: "规则算子", value: String(ruleConfig.operator) });
  }
  if (ruleConfig?.metric) {
    rows.push({ label: "相似度指标", value: String(ruleConfig.metric) });
  }

  const textSources =
    outputConfig.text_sources && typeof outputConfig.text_sources === "object"
      ? (outputConfig.text_sources as Record<string, unknown>)
      : null;
  if (textSources?.left_template) {
    rows.push({ label: "左侧模板", value: String(textSources.left_template) });
  }
  if (textSources?.right_template) {
    rows.push({ label: "右侧模板", value: String(textSources.right_template) });
  }

  return rows;
}

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
