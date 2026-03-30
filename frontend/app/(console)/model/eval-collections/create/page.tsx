import { getBenchmarkCatalog } from "@/features/eval/api";
import { EvalCollectionCreateForm } from "@/features/eval/components/eval-collection-create-form";

export default async function CreateEvalCollectionPage() {
  const benchmarks = await getBenchmarkCatalog().catch(() => []);
  const runnableBenchmarks = benchmarks.filter((b) => b.runtime_available);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建评测套件</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          选择多个 Benchmark 和版本，组合成可重复运行的评测套件。
        </p>
      </div>
      <EvalCollectionCreateForm benchmarks={runnableBenchmarks} />
    </div>
  );
}
