import { notFound, redirect } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { BenchmarkCreateForm } from "@/features/eval/components/benchmark-create-form";
import { getBenchmark, getEvalTemplates } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditBenchmarkPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const [benchmark, evalTemplates] = await Promise.all([
    getBenchmark(name, projectId).catch(() => null),
    getEvalTemplates().catch(() => [])
  ]);

  if (!benchmark) {
    notFound();
  }

  if (benchmark.source_type === "builtin") {
    redirect(`/model/eval-benchmarks/${benchmark.name}`);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="space-y-2">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "Benchmark", href: "/model/eval?tab=benchmarks" },
            { label: benchmark.display_name, href: `/model/eval-benchmarks/${benchmark.name}` },
            { label: "编辑 Benchmark" }
          ]}
        />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">编辑 Benchmark</h1>
          <p className="mt-1 text-sm text-slate-400">
            调整 Benchmark 的基础信息和绑定的评测维度。已存在的数据集版本不会被自动改写。
          </p>
        </div>
      </div>

      <BenchmarkCreateForm
        evalTemplates={evalTemplates}
        initialBenchmark={benchmark}
        mode="edit"
      />
    </div>
  );
}
