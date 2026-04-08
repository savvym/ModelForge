import { TemplateSpecCreateForm } from "@/features/eval/components/template-spec-create-form";

export default function CreateEvalTemplatePage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建模板资产</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          这里创建的是 v2 `TemplateSpec`，只负责保存 Prompt、变量和输出结构，不直接绑定模型。
        </p>
      </div>

      <TemplateSpecCreateForm />
    </div>
  );
}
