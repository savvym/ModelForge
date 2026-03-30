import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  ConsoleListFilterField,
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { getDatasets } from "@/features/dataset/api";
import { DatasetListTable } from "@/features/dataset/components/dataset-list-table";
import { DatasetFormatFilter } from "@/features/dataset/components/dataset-format-filter";
import { getLakeAssets, getLakeBatches } from "@/features/lake/api";
import { DataLakePanel } from "@/features/lake/components/data-lake-panel";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";

const datasetScopes = [
  { key: "my-datasets", label: "我的数据集" },
  { key: "my-data-lake", label: "我的数据湖" }
] as const;

export default async function DatasetPage({
  searchParams
}: {
  searchParams: Promise<{ scope?: string; q?: string; recipe?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const currentScope = datasetScopes.some((scope) => scope.key === resolvedSearchParams.scope)
    ? (resolvedSearchParams.scope as (typeof datasetScopes)[number]["key"])
    : "my-datasets";
  const query = resolvedSearchParams.q?.trim() ?? "";
  const recipeFilters = Array.isArray(resolvedSearchParams.recipe)
    ? resolvedSearchParams.recipe.map((value) => value.trim()).filter(Boolean)
      : resolvedSearchParams.recipe?.trim()
      ? [resolvedSearchParams.recipe.trim()]
      : [];
  const projectId = await getCurrentProjectIdFromCookie();
  const datasets = await getDatasets(currentScope, projectId).catch(() => []);
  const [lakeBatches, lakeAssets] =
    currentScope === "my-data-lake"
      ? await Promise.all([
          getLakeBatches(projectId).catch(() => []),
          getLakeAssets({ stage: "raw", projectId }).catch(() => [])
        ])
      : [[], []];
  const filteredDatasets = datasets.filter((dataset) => {
    const matchesQuery =
      !query || dataset.name.toLowerCase().includes(query.toLowerCase()) || dataset.id.includes(query);
    const matchesRecipe =
      recipeFilters.length === 0 || (!!dataset.recipe && recipeFilters.includes(dataset.recipe));
    return matchesQuery && matchesRecipe;
  });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800/80">
        <div className="flex min-w-0 items-center gap-5">
          {datasetScopes.map((scope) => (
            <Link
              key={scope.key}
              className={cn(
                "-mb-px inline-flex h-9 items-center border-b-2 px-0.5 text-[13px] transition-colors",
                currentScope === scope.key
                  ? "border-slate-100 font-medium text-slate-50"
                  : "border-transparent text-slate-500 hover:text-slate-200"
              )}
              href={buildDatasetQuery({
                scope: scope.key,
                q: query,
                recipe: recipeFilters
              })}
            >
              {scope.label}
            </Link>
          ))}
        </div>
      </div>

      {currentScope === "my-datasets" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/dataset"
                className="max-w-[540px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索数据集名称或 ID"
              >
                <input name="scope" type="hidden" value={currentScope} />
                {recipeFilters.map((recipe) => (
                  <input key={recipe} name="recipe" type="hidden" value={recipe} />
                ))}
              </ConsoleListSearchForm>

              <ConsoleListFilterField className="w-[148px] min-w-[148px] shrink-0" label="数据格式">
                <DatasetFormatFilter
                  currentValues={recipeFilters}
                  q={query}
                  scope={currentScope}
                  variant="toolbar"
                />
              </ConsoleListFilterField>
            </ConsoleListToolbarCluster>

            <Link href="/dataset-create">
              <Button size="sm">创建数据集</Button>
            </Link>
          </ConsoleListToolbar>

          <DatasetListTable
            datasets={filteredDatasets}
          />
        </>
      ) : null}

      {currentScope === "my-data-lake" ? (
        <DataLakePanel initialAssets={lakeAssets} initialBatches={lakeBatches} />
      ) : null}
    </div>
  );
}

function buildDatasetQuery({
  scope,
  q,
  recipe
}: {
  scope: string;
  q: string;
  recipe?: string[];
}) {
  const params = new URLSearchParams();
  params.set("scope", scope);
  if (q) {
    params.set("q", q);
  }
  for (const recipeValue of recipe ?? []) {
    params.append("recipe", recipeValue);
  }
  return `/dataset?${params.toString()}`;
}
