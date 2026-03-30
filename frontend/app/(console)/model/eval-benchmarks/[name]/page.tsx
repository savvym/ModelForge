import Link from "next/link";
import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getPresetLabel, getTemplateTypeLabel } from "@/features/eval/eval-template-meta";
import { getBenchmark } from "@/features/eval/api";
import { BenchmarkDetailPanel } from "@/features/eval/components/benchmark-detail-panel";
import { formatEvalMethod } from "@/features/eval/status";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ModelEvalBenchmarkDetailPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const benchmark = await getBenchmark(name, projectId).catch(() => null);

  if (!benchmark) {
    notFound();
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-start justify-between gap-4 pb-0">
        <div className="space-y-1.5">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: "评测管理", href: "/model/eval?tab=management" },
              { label: benchmark.display_name }
            ]}
          />
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold tracking-tight text-slate-50">
              {benchmark.display_name}
            </h1>
            <Badge variant="outline">{benchmark.version_count} Versions</Badge>
            {benchmark.source_type ? <Badge variant="secondary">{benchmark.source_type}</Badge> : null}
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate-400">{benchmark.description}</p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link href="/model/eval?tab=management">
            <Button variant="outline">返回评测管理</Button>
          </Link>
          {benchmark.source_type === "custom" ? (
            <Link href={`/model/eval-benchmarks/${benchmark.name}/edit`}>
              <Button variant="outline">编辑 Benchmark</Button>
            </Link>
          ) : null}
          <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/create`}>
            <Button variant="outline">新增 Version</Button>
          </Link>
          <Link href="/model/eval?tab=jobs&create=1">
            <Button>创建评测任务</Button>
          </Link>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="绑定模板"
          value={
            benchmark.eval_template_name
              ? `${benchmark.eval_template_name}${benchmark.eval_template_version != null ? ` · v${benchmark.eval_template_version}` : ""}`
              : "--"
          }
        />
        <SummaryCard
          label="模板类型"
          value={
            benchmark.eval_template_type
              ? `${getTemplateTypeLabel(benchmark.eval_template_type)}${
                  benchmark.eval_template_preset_id
                    ? ` · ${getPresetLabel(benchmark.eval_template_preset_id)}`
                    : ""
                }`
              : "--"
          }
        />
        <SummaryCard
          label="默认评测方式"
          value={formatEvalMethod(benchmark.default_eval_method)}
        />
        <SummaryCard
          label="版本状态"
          value={`${benchmark.enabled_version_count}/${benchmark.version_count} Enabled`}
        />
      </div>

      <div className="console-workbench min-h-0 flex-1">
        <BenchmarkDetailPanel benchmark={benchmark} />
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
      <CardContent className="space-y-2 px-4 py-4">
        <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
        <div className="text-sm text-slate-100">{value}</div>
      </CardContent>
    </Card>
  );
}
