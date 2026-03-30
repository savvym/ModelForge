import { BenchmarkCreateForm } from "@/features/eval/components/benchmark-create-form";

export default function CreateBenchmarkPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建 Benchmark</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          定义评测类型、数据格式和评测方法。创建后可上传评测数据集作为 Version 来运行评测。
        </p>
      </div>
      <BenchmarkCreateForm />
    </div>
  );
}
