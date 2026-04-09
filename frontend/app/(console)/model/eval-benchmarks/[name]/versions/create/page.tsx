import { notFound, redirect } from "next/navigation";
import { BenchmarkVersionEditorForm } from "@/features/eval/components/benchmark-version-editor-form";
import { getBenchmark } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateBenchmarkVersionPage({
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

  if (benchmark.source_type === "builtin") {
    redirect(`/model/eval-benchmarks/${benchmark.name}`);
  }

  return (
    <BenchmarkVersionEditorForm
      benchmark={{ display_name: benchmark.display_name, name: benchmark.name }}
      mode="create"
      projectId={projectId}
    />
  );
}
