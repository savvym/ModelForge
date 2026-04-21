import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { getEvalTemplate } from "@/features/eval/api";
import { EvalTemplateCreateForm } from "@/features/eval/components/eval-template-create-form";

export default async function EditEvalTemplatePage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const template = await getEvalTemplate(name).catch(() => null);

  if (!template) {
    notFound();
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="space-y-2">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "评测维度", href: "/model/eval?tab=dimensions" },
            { label: template.name },
            { label: "编辑" },
          ]}
        />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">编辑评测维度</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            修改 Prompt、标签分组和 Judge 配置。保存后会创建新版本，已绑定 Benchmark 需要重新选择新版本才会生效。
          </p>
        </div>
      </div>

      <EvalTemplateCreateForm initialTemplate={template} mode="edit" />
    </div>
  );
}
