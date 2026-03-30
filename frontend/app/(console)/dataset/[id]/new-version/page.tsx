import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetVersionCreateForm } from "@/features/dataset/components/dataset-version-create-form";
import { getDataset } from "@/features/dataset/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function DatasetNewVersionPage({
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
                当前数据集可能已经被删除，或该 ID 不存在。
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  const nextVersion = (dataset.versions[0]?.version ?? 0) + 1;
  const formatLabel = buildDatasetFormatLabel(dataset);
  const isEvaluationDataset =
    dataset.purpose === "evaluation" || dataset.use_case === "evaluation";

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-2">
      <section className="flex flex-wrap items-center justify-between gap-3 pb-0">
        <div className="min-w-0">
          <ConsoleBreadcrumb
            items={[
              { label: "数据集", href: "/dataset" },
              { label: dataset.name, href: `/dataset/${dataset.id}` },
              { label: "新建版本" }
            ]}
          />
        </div>
      </section>

      <div className="console-workbench min-h-0 flex-1">
        <div className="flex h-full min-h-0">
          <div className="console-workbench__scroll min-h-0 w-full max-w-[1080px] overflow-y-auto px-5 pb-8 pt-1">
            <DatasetVersionCreateForm
              datasetId={dataset.id}
              datasetName={dataset.name}
              defaultDescription={dataset.description}
              formatLabel={formatLabel}
              isEvaluationDataset={isEvaluationDataset}
              nextVersion={nextVersion}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function buildDatasetFormatLabel(dataset: Awaited<ReturnType<typeof getDataset>>) {
  const purposeLabel =
    dataset.purpose === "evaluation" || dataset.use_case === "evaluation"
      ? "模型评测"
      : "模型精调";
  const modalityLabel =
    dataset.modality === "vectorization" || dataset.format === "vectorization"
      ? "向量化"
      : "文本生成";
  const recipeMap: Record<string, string> = {
    sft: "SFT 精调",
    dpo: "直接偏好学习",
    "continued-pretrain": "继续预训练",
    "generic-eval": "评测数据集"
  };
  const recipeLabel =
    recipeMap[dataset.recipe ?? ""] ??
    dataset.recipe ??
    (dataset.purpose === "evaluation" ? "评测数据集" : "SFT 精调");

  return `${purposeLabel} · ${modalityLabel} > ${recipeLabel}`;
}
