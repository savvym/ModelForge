import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { BenchmarkDetailPanel } from "@/features/eval/components/benchmark-detail-panel";
import { getBenchmark } from "@/features/eval/api";
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
      <section className="flex flex-wrap items-start justify-between gap-3 pb-0">
        <div className="min-w-0 space-y-2">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: "Benchmark", href: "/model/eval?tab=benchmarks" },
              { label: benchmark.display_name }
            ]}
          />
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold tracking-tight text-slate-50">
              {benchmark.display_name}
            </h1>
            <Badge variant={benchmark.source_type === "builtin" ? "outline" : "secondary"}>
              {benchmark.source_type === "builtin" ? "平台预置" : "自定义"}
            </Badge>
          </div>
          <p className="max-w-4xl text-sm leading-6 text-slate-400">
            {benchmark.description || "当前 Benchmark 还没有额外描述。"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <a className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval?tab=benchmarks">
            返回 Benchmark 列表
          </a>
          {benchmark.source_type !== "builtin" ? (
            <a
              className={buttonVariants({ size: "sm" })}
              href={`/model/eval-benchmarks/${benchmark.name}/edit`}
            >
              编辑 Benchmark
            </a>
          ) : null}
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <div className="console-workbench__scroll min-h-0 overflow-y-auto px-5 pb-8 pt-3">
          <BenchmarkDetailPanel benchmark={benchmark} />
        </div>
      </div>
    </div>
  );
}
