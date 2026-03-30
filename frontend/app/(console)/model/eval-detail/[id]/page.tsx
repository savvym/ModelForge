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
import { getEvalJob } from "@/features/eval/api";
import { EvalJobDetailActions } from "@/features/eval/components/eval-job-detail-actions";
import {
  formatAccessSource,
  formatEvalDatasetSource,
  formatEvalMethod,
  formatEvalMode,
  formatInferenceMode,
  formatModelSource,
  formatTaskType,
  getEvalStatusMeta
} from "@/features/eval/status";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ModelEvalDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const detail = await getEvalJob(id, projectId).catch(() => null);

  if (!detail) {
    notFound();
  }

  const statusMeta = getEvalStatusMeta(detail.status);

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

        <EvalJobDetailActions jobId={detail.id} jobName={detail.name} status={detail.status} />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">任务信息</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <DetailItem label="状态" value={statusMeta.label} />
            <DetailItem
              label="当前进度"
              value={
                typeof detail.progress_done === "number" && typeof detail.progress_total === "number"
                  ? `${detail.progress_done}/${detail.progress_total} (${detail.progress_percent}%)`
                  : `${detail.progress_percent}%`
              }
            />
            <DetailItem label="模型服务" value={formatModelSource(detail.model_source)} />
            <DetailItem label="评测模型" value={detail.model_name} />
            <DetailItem label="裁判员模型" value={detail.judge_model_name ?? "--"} />
            <DetailItem label="Benchmark" value={detail.benchmark_name ?? "--"} />
            <DetailItem label="Benchmark Version" value={detail.benchmark_version_name ?? "--"} />
            <DetailItem label="推理方式" value={formatInferenceMode(detail.inference_mode)} />
            <DetailItem label="评测方法" value={formatEvalMethod(detail.eval_method)} />
            <DetailItem label="访问来源" value={formatAccessSource(detail.access_source)} />
            <DetailItem label="任务类型" value={formatTaskType(detail.task_type)} />
            <DetailItem label="评测模式" value={formatEvalMode(detail.eval_mode)} />
            <DetailItem label="数据源类型" value={formatEvalDatasetSource(detail.dataset_source_type)} />
            <DetailItem label="数据源名称" value={detail.dataset_name} />
            <DetailItem label="创建人" value={detail.created_by ?? "--"} />
            <DetailItem label="创建时间" value={formatDateTime(detail.created_at)} />
            <DetailItem label="开始时间" value={formatDateTime(detail.started_at)} />
            <DetailItem label="结束时间" value={formatDateTime(detail.finished_at)} />
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">结果概览</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {detail.metrics.length ? (
              <div className="grid gap-3">
                {detail.metrics.map((metric) => (
                  <div
                    key={`${metric.metric_name}-${metric.metric_value}`}
                    className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3"
                  >
                    <div className="text-xs uppercase tracking-wide text-slate-500">
                      {metric.metric_name}
                    </div>
                    <div className="mt-1 text-2xl font-semibold text-slate-50">
                      {metric.metric_value.toFixed(4)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-400">
                当前任务还没有聚合指标。
              </div>
            )}

            <div className="space-y-2 text-sm text-slate-400">
              <PathRow label="数据源" value={detail.source_object_uri} />
              <PathRow label="结果目录" value={detail.results_prefix_uri ?? detail.artifact_prefix_uri} />
              <PathRow label="报告文件" value={detail.report_object_uri} />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader className="gap-2">
          <CardTitle className="text-base text-slate-50">样本级结果</CardTitle>
          <p className="text-sm text-slate-400">
            当前展示每个样本的分数、是否通过和 judge 给出的原因。
          </p>
        </CardHeader>
        <CardContent>
          {detail.sample_analysis.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>样本 ID</TableHead>
                  <TableHead>方法</TableHead>
                  <TableHead>分数</TableHead>
                  <TableHead>通过</TableHead>
                  <TableHead>原因</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.sample_analysis.map((sample) => (
                  <TableRow key={`${sample.sample_id}-${sample.method}`}>
                    <TableCell className="align-top font-mono text-xs text-slate-300">
                      {sample.sample_id}
                    </TableCell>
                    <TableCell className="align-top text-slate-300">{sample.method}</TableCell>
                    <TableCell className="align-top text-slate-300">
                      {typeof sample.score === "number" ? sample.score.toFixed(4) : "--"}
                    </TableCell>
                    <TableCell className="align-top text-slate-300">
                      {sample.passed ? "是" : "否"}
                    </TableCell>
                    <TableCell className="max-w-[720px] whitespace-pre-wrap text-sm leading-6 text-slate-400">
                      {sample.reason || sample.error || "--"}
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

function PathRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <span className="text-slate-500">{label}：</span>
      <span className="break-all text-slate-300">{value || "--"}</span>
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
