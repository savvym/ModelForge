import { getEvaluationCatalog } from "@/features/eval/api";
import { EvalSuiteCreateForm } from "@/features/eval/components/eval-suite-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateEvalSuitePage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const catalog = await getEvaluationCatalog(projectId).catch(() => ({
    specs: [],
    suites: [],
    templates: [],
    judge_policies: []
  }));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建评测套件</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          创建新的 Eval Suite，并定义套件版本与评测项编排。
        </p>
      </div>

      <EvalSuiteCreateForm catalog={catalog} />
    </div>
  );
}
