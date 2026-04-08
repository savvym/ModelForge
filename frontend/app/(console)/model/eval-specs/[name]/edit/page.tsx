import { notFound } from "next/navigation";
import { getEvaluationCatalog, getEvaluationSpec } from "@/features/eval/api";
import { EvalSpecCreateForm } from "@/features/eval/components/eval-spec-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditEvalSpecPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const [catalog, spec] = await Promise.all([
    getEvaluationCatalog(projectId).catch(() => ({
      specs: [],
      suites: [],
      templates: [],
      judge_policies: []
    })),
    getEvaluationSpec(name, projectId).catch(() => null)
  ]);

  if (!spec) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">编辑评测类型</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          修改评测类型元信息和当前管理版本的执行配置。
        </p>
      </div>

      <EvalSpecCreateForm catalog={catalog} initialValue={spec} mode="edit" />
    </div>
  );
}
