import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetDetailPanel } from "@/features/dataset/components/dataset-detail-panel";
import { getDataset } from "@/features/dataset/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function DatasetDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const dataset = await getDataset(id, projectId).catch(() => null);

  if (!dataset) {
    return (
      <div className="flex h-full min-h-0 w-full flex-col gap-2">
        <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
          <div className="min-w-0">
            <ConsoleBreadcrumb
              items={[
                { label: "数据集", href: "/dataset" },
                { label: "数据集不存在" }
              ]}
            />
          </div>
        </section>

        <div className="console-workbench min-h-0 flex-1">
          <div className="console-workbench__scroll min-h-0 overflow-y-auto px-5 pb-8 pt-3">
            <Card className="max-w-xl">
              <CardHeader>
                <CardTitle>数据集不存在</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                当前数据集可能已被删除，或你访问的 ID 不存在。
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
        <div className="min-w-0">
          <ConsoleBreadcrumb
            items={[
              { label: "数据集", href: "/dataset" },
              { label: dataset.name }
            ]}
          />
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <DatasetDetailPanel dataset={dataset} />
      </div>
    </div>
  );
}
