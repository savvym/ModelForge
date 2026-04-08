import { getEvaluationCatalog } from "@/features/eval/api";
import { JudgePolicyCreateForm } from "@/features/eval/components/judge-policy-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateJudgePolicyPage() {
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
        <h1 className="text-lg font-semibold">创建 Judge Policy</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Judge Policy 是模板之外的执行规则层，负责模型选择、执行参数、解析策略和重试策略。
        </p>
      </div>

      <JudgePolicyCreateForm catalog={catalog} />
    </div>
  );
}
