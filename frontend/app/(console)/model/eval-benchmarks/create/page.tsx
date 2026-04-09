import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { BenchmarkCreateForm } from "@/features/eval/components/benchmark-create-form";
import { getEvalTemplates } from "@/features/eval/api";

export default async function CreateBenchmarkPage() {
  const evalTemplates = await getEvalTemplates().catch(() => []);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="space-y-2">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "Benchmark", href: "/model/eval?tab=benchmarks" },
            { label: "创建 Benchmark" }
          ]}
        />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">创建 Benchmark</h1>
          <p className="mt-1 text-sm text-slate-400">
            创建自定义 Benchmark 时，需要先绑定一个评测维度。后续的 Benchmark Version 就是这个 Benchmark 的数据集版本。
          </p>
        </div>
      </div>

      <BenchmarkCreateForm evalTemplates={evalTemplates} />
    </div>
  );
}
