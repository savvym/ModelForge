import { EvalTemplateCreateForm } from "@/features/eval/components/eval-template-create-form";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateEvalTemplatePage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const models = await getRegistryModels(projectId).catch(() => []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建评测维度</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          评测维度用于定义评分方式、裁判模型和输出结构。自定义 Benchmark 创建时会绑定一个评测维度。
        </p>
      </div>

      <EvalTemplateCreateForm models={models} />
    </div>
  );
}
