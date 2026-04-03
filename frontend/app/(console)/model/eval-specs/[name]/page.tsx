import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { EvalSpecDetailPanel } from "@/features/eval/components/eval-spec-detail-panel";
import { getEvaluationSpec } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EvalSpecDetailPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const spec = await getEvaluationSpec(name, projectId).catch(() => null);

  if (!spec) {
    notFound();
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
        <div className="min-w-0">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: "评测管理", href: "/model/eval?tab=catalog" },
              { label: spec.display_name }
            ]}
          />
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <div className="console-workbench__scroll min-h-0 overflow-y-auto px-5 pb-8 pt-3">
          <EvalSpecDetailPanel spec={spec} />
        </div>
      </div>
    </div>
  );
}
