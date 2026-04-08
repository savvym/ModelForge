import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { getEvaluationRun } from "@/features/eval/api";
import { EvaluationRunDetailActions } from "@/features/eval/components/evaluation-run-detail-actions";
import { formatEvaluationRunKind, getEvalStatusMeta } from "@/features/eval/status";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import type { EvaluationRunItemV2, EvaluationRunMetricV2 } from "@/types/api";

export default async function ModelEvalDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const detail = await getEvaluationRun(id, projectId).catch(() => null);

  if (!detail) {
    notFound();
  }

  const statusMeta = getEvalStatusMeta(detail.status);
  const overallMetrics = detail.metrics.filter((metric) => metric.metric_scope === "overall");
  const groupedMetrics = detail.metrics.filter((metric) => metric.metric_scope === "group");

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800/70 pb-4">
        <div className="space-y-1.5">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: detail.name }
            ]}
          />
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold tracking-tight text-slate-50">{detail.name}</h1>
            <Badge className={statusMeta.className} variant={statusMeta.variant}>
              {statusMeta.label}
            </Badge>
          </div>
          <p className="text-sm text-slate-400">{detail.id}</p>
        </div>

        <EvaluationRunDetailActions runId={detail.id} runName={detail.name} status={detail.status} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">运行信息</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <DetailItem label="评测类型" value={formatEvaluationRunKind(detail.kind)} />
            <DetailItem
              label="当前进度"
              value={
                typeof detail.progress_done === "number" && typeof detail.progress_total === "number"
                  ? `${detail.progress_done}/${detail.progress_total}`
                  : "--"
              }
            />
            <DetailItem
              label={detail.kind === "suite" ? "套件目标" : "评测目标"}
              value={`${detail.execution_plan_json.target_name}@${detail.execution_plan_json.target_version}`}
            />
            <DetailItem label="评测模型" value={detail.model_name ?? "--"} />
            <DetailItem
              label="Judge Policy"
              value={detail.judge_policy_id ?? "使用默认策略"}
            />
            <DetailItem label="Temporal Workflow" value={detail.temporal_workflow_id ?? "--"} />
            <DetailItem label="创建时间" value={formatDateTime(detail.created_at)} />
            <DetailItem label="开始时间" value={formatDateTime(detail.started_at)} />
            <DetailItem label="结束时间" value={formatDateTime(detail.finished_at)} />
            <DetailItem label="Summary Report" value={detail.summary_report_uri ?? "--"} />
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">结果概览</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {overallMetrics.length ? (
              <div className="grid gap-3">
                {overallMetrics.map((metric) => (
                  <MetricCard key={`${metric.metric_name}-${metric.metric_scope}`} metric={metric} />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-400">
                当前任务还没有聚合指标。
              </div>
            )}

            {groupedMetrics.length ? (
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Group Metrics</div>
                <div className="grid gap-3">
                  {groupedMetrics.map((metric) => (
                    <div
                      className="rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-4 py-3"
                      key={`${metric.metric_name}-${JSON.stringify(metric.dimension_json)}`}
                    >
                      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">
                        {String(metric.dimension_json.group_name ?? metric.metric_name)}
                      </div>
                      <div className="mt-1 text-lg font-semibold text-slate-100">
                        {metric.metric_value.toFixed(4)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader className="gap-2">
          <CardTitle className="text-base text-slate-50">运行项</CardTitle>
          <p className="text-sm text-slate-400">
            Suite 会 fan-out 成多个运行项；单项评测则只会生成一个 item。
          </p>
        </CardHeader>
        <CardContent>
          {detail.items.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>运行项</TableHead>
                  <TableHead>分组</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>执行引擎</TableHead>
                  <TableHead>分数</TableHead>
                  <TableHead>结果目录</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.items.map((item) => {
                  const itemStatus = getEvalStatusMeta(item.status);
                  const overallMetric = item.metrics.find((metric) => metric.metric_scope === "overall") ?? null;
                  return (
                    <TableRow key={item.id}>
                      <TableCell className="align-top">
                        <div className="font-medium text-slate-100">{item.display_name}</div>
                        <div className="mt-1 text-xs text-slate-500">{item.item_key}</div>
                        {item.error_message ? (
                          <div className="mt-2 line-clamp-2 text-xs text-rose-300">
                            {item.error_message}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell>{item.group_name ?? "--"}</TableCell>
                      <TableCell>
                        <Badge className={itemStatus.className} variant={itemStatus.variant}>
                          {itemStatus.label}
                        </Badge>
                      </TableCell>
                      <TableCell>{`${item.engine} / ${item.execution_mode}`}</TableCell>
                      <TableCell>
                        {overallMetric ? overallMetric.metric_value.toFixed(4) : "--"}
                      </TableCell>
                      <TableCell className="max-w-[360px] break-all text-xs text-slate-400">
                        {item.raw_output_prefix_uri ?? item.report_uri ?? "--"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-10 text-sm text-slate-400">
              当前任务还没有运行项。
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader className="gap-2">
          <CardTitle className="text-base text-slate-50">样本级结果</CardTitle>
          <p className="text-sm text-slate-400">
            展示运行项返回的 canonical sample report。若某些内置 benchmark 不产出样本细节，这里会保持为空。
          </p>
        </CardHeader>
        <CardContent>
          {flattenSamples(detail.items).length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>运行项</TableHead>
                  <TableHead>样本 ID</TableHead>
                  <TableHead>子集</TableHead>
                  <TableHead>分数</TableHead>
                  <TableHead>通过</TableHead>
                  <TableHead>原因</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flattenSamples(detail.items).map((row) => (
                  <TableRow key={`${row.item.id}-${row.sample.sample_id}`}>
                    <TableCell className="align-top text-slate-300">{row.item.display_name}</TableCell>
                    <TableCell className="align-top font-mono text-xs text-slate-300">
                      {row.sample.sample_id}
                    </TableCell>
                    <TableCell className="align-top text-slate-300">
                      {row.sample.subset_name ?? "--"}
                    </TableCell>
                    <TableCell className="align-top text-slate-300">
                      {typeof row.sample.score === "number" ? row.sample.score.toFixed(4) : "--"}
                    </TableCell>
                    <TableCell className="align-top text-slate-300">
                      {row.sample.passed ? "是" : "否"}
                    </TableCell>
                    <TableCell className="max-w-[720px] whitespace-pre-wrap text-sm leading-6 text-slate-400">
                      {row.sample.reason || row.sample.error || "--"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-10 text-sm text-slate-400">
              当前任务还没有样本级结果。
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader className="gap-2">
          <CardTitle className="text-base text-slate-50">执行计划快照</CardTitle>
          <p className="text-sm text-slate-400">
            Worker 只消费这份冻结后的 plan，不会在执行时重新解析评测目录或模型配置。
          </p>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-2xl border border-slate-800/80 bg-[rgba(8,12,18,0.72)] p-4 text-xs leading-6 text-slate-300">
            {JSON.stringify(detail.execution_plan_json, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ metric }: { metric: EvaluationRunMetricV2 }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{metric.metric_name}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-50">
        {metric.metric_value.toFixed(4)}
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

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function flattenSamples(items: EvaluationRunItemV2[]) {
  return items.flatMap((item) => item.samples.map((sample) => ({ item, sample })));
}
