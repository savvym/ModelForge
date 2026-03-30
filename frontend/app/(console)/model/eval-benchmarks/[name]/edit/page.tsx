import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { getBenchmark, getEvalTemplates } from "@/features/eval/api";
import { BenchmarkCreateForm } from "@/features/eval/components/benchmark-create-form";
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

  if (benchmark.source_type !== "custom") {
    notFound();
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-2">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "评测管理", href: "/model/eval?tab=management" },
            { label: benchmark.display_name, href: `/model/eval-benchmarks/${benchmark.name}` },
            { label: "编辑 Benchmark" }
          ]}
        />
        <div>
          <h1 className="text-lg font-semibold">编辑 Benchmark</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            调整 Benchmark 的描述、评测模板和数据字段映射配置。
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
