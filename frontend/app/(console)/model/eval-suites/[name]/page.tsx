import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { EvalSuiteDetailPanel } from "@/features/eval/components/eval-suite-detail-panel";
import { getEvaluationCatalog, getEvaluationSuite } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EvalSuiteDetailPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const [catalog, suite] = await Promise.all([
    getEvaluationCatalog(projectId).catch(() => null),
    getEvaluationSuite(name, projectId).catch(() => null)
  ]);

  if (!suite) {
    notFound();
  }

  const specVersionLookup = Object.fromEntries(
    (catalog?.specs ?? []).flatMap((spec) =>
      spec.versions.map((version) => [
        version.id,
        {
          specName: spec.name,
          specDisplayName: spec.display_name,
          version: version.version,
          versionDisplayName: version.display_name
        }
      ])
    )
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
        <div className="min-w-0">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: "评测管理", href: "/model/eval?tab=catalog" },
              { label: suite.display_name }
            ]}
          />
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <div className="console-workbench__scroll min-h-0 overflow-y-auto px-5 pb-8 pt-3">
          <EvalSuiteDetailPanel suite={suite} specVersionLookup={specVersionLookup} />
        </div>
      </div>
    </div>
  );
}
