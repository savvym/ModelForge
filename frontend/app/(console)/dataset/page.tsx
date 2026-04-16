import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { RouteTabs } from "@/components/console/route-tabs";
import {
  ConsoleListFilterField,
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { getDatasets } from "@/features/dataset/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

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
  const filteredDatasets =
    currentScope === "my-datasets"
      ? (await getDatasets(currentScope, projectId).catch(() => [])).filter((dataset) => {
          const matchesQuery =
            !query ||
            dataset.name.toLowerCase().includes(query.toLowerCase()) ||
            dataset.id.includes(query);
          const matchesRecipe =
            recipeFilters.length === 0 || (!!dataset.recipe && recipeFilters.includes(dataset.recipe));
          return matchesQuery && matchesRecipe;
        })
      : [];

  const lakePanelPayload =
    currentScope === "my-data-lake"
      ? await loadDataLakePayload(projectId)
      : null;

  const datasetsSurface =
    currentScope === "my-datasets"
      ? await renderDatasetSurface(filteredDatasets, currentScope, query, recipeFilters)
      : null;
  const scopeTabs = datasetScopes.map((scope) => ({
    href: buildDatasetQuery({
      scope: scope.key,
      q: query,
      recipe: recipeFilters
    }),
    label: scope.label,
    value: scope.key
  }));

  return (
    <div className="flex flex-col gap-4">
      <div className="border-b border-border/70 pb-3">
        <RouteTabs items={scopeTabs} value={currentScope} />
      </div>

      {datasetsSurface}
      {lakePanelPayload?.panel ?? null}
    </div>
  );
}

async function renderDatasetSurface(
  filteredDatasets: Awaited<ReturnType<typeof getDatasets>>,
  currentScope: string,
  query: string,
  recipeFilters: string[]
) {
  const [{ DatasetListTable }, { DatasetFormatFilter }] = await Promise.all([
    import("@/features/dataset/components/dataset-list-table"),
    import("@/features/dataset/components/dataset-format-filter")
  ]);

  return (
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

        <Link className={buttonVariants({ size: "sm" })} href="/dataset-create">
          创建数据集
        </Link>
      </ConsoleListToolbar>

      <DatasetListTable datasets={filteredDatasets} />
    </>
  );
}

async function loadDataLakePayload(projectId: string | null) {
  const [
    { getLakeAssets, getLakeBatches },
    { DataLakePanel }
  ] = await Promise.all([
    import("@/features/lake/api"),
    import("@/features/lake/components/data-lake-panel")
  ]);

  const [lakeBatches, lakeAssets] = await Promise.all([
    getLakeBatches(projectId).catch(() => []),
    getLakeAssets({ stage: "raw", projectId }).catch(() => [])
  ]);

  return {
    panel: <DataLakePanel initialAssets={lakeAssets} initialBatches={lakeBatches} />
  };
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
