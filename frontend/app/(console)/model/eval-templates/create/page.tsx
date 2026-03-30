import { EvalTemplateCreateForm } from "@/features/eval/components/eval-template-create-form";

export default function CreateEvalTemplatePage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建评测模板</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          先选择评测类型，再配置 Prompt、标签分组、规则算子和评分参数。模板可被多个 Benchmark 复用。
        </p>
      </div>

      <EvalTemplateCreateForm />
    </div>
  );
}
