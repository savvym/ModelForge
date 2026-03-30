import { notFound } from "next/navigation";
import { getBenchmark } from "@/features/eval/api";
import { BenchmarkVersionEditorForm } from "@/features/eval/components/benchmark-version-editor-form";
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

  return (
    <BenchmarkVersionEditorForm
      benchmark={{ name: benchmark.name, display_name: benchmark.display_name }}
      mode="create"
      projectId={projectId}
    />
  );
}
