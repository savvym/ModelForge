import { notFound } from "next/navigation";
import { getBenchmark } from "@/features/eval/api";
import { BenchmarkVersionEditorForm } from "@/features/eval/components/benchmark-version-editor-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditBenchmarkVersionPage({
  params
}: {
  params: Promise<{ name: string; versionId: string }>;
}) {
  const { name, versionId } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const benchmark = await getBenchmark(name, projectId).catch(() => null);

  if (!benchmark) {
    notFound();
  }

  if (!benchmark.runtime_available) {
    notFound();
  }

  const version = benchmark.versions.find((item) => item.id === versionId) ?? null;
  if (!version) {
    notFound();
  }

  return (
    <BenchmarkVersionEditorForm
      benchmark={{ name: benchmark.name, display_name: benchmark.display_name }}
      initialVersion={version}
      mode="edit"
      projectId={projectId}
    />
  );
}
