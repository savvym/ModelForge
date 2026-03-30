import { BenchmarkCreateForm } from "@/features/eval/components/benchmark-create-form";
import { getEvalTemplates } from "@/features/eval/api";

export default async function CreateBenchmarkPage() {
  const evalTemplates = await getEvalTemplates().catch(() => []);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建 Benchmark</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          选择一个评测模板，把 Benchmark 创建成可上传和管理 Version 数据集的评测容器。系统会自动生成
          以 `bench-` 开头的 Benchmark ID。
        </p>
      </div>
      <BenchmarkCreateForm evalTemplates={evalTemplates} />
    </div>
  );
}
