import { notFound } from "next/navigation";
import { getEvaluationCatalog, getEvaluationSuite } from "@/features/eval/api";
import { EvalSuiteCreateForm } from "@/features/eval/components/eval-suite-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditEvalSuitePage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const [catalog, suite] = await Promise.all([
    getEvaluationCatalog(projectId).catch(() => ({
      specs: [],
      suites: [],
      templates: [],
      judge_policies: []
    })),
    getEvaluationSuite(name, projectId).catch(() => null)
  ]);

  if (!suite) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">编辑评测套件</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          调整套件元信息，并重新编排评测类型与版本组合。
        </p>
      </div>

      <EvalSuiteCreateForm catalog={catalog} initialValue={suite} mode="edit" />
    </div>
  );
}
