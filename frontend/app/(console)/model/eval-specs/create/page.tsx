import { getEvaluationCatalog } from "@/features/eval/api";
import { EvalSpecCreateForm } from "@/features/eval/components/eval-spec-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateEvalSpecPage() {
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
        <h1 className="text-lg font-semibold">创建评测类型</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          创建新的 Eval Spec，并同时定义一份初始版本快照。
        </p>
      </div>

      <EvalSpecCreateForm catalog={catalog} />
    </div>
  );
}
