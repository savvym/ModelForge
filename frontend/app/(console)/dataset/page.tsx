import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import {
  ConsoleListFilterField,
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { getDatasets } from "@/features/dataset/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

const DATASET_SCOPE = "my-datasets";

export default async function DatasetPage({
  searchParams
}: {
  searchParams: Promise<{ scope?: string; q?: string; recipe?: string | string[] }>;
}) {
  const resolvedSearchParams = await searchParams;
  const query = resolvedSearchParams.q?.trim() ?? "";
  const recipeFilters = Array.isArray(resolvedSearchParams.recipe)
    ? resolvedSearchParams.recipe.map((value) => value.trim()).filter(Boolean)
    : resolvedSearchParams.recipe?.trim()
      ? [resolvedSearchParams.recipe.trim()]
      : [];
  const projectId = await getCurrentProjectIdFromCookie();
  const filteredDatasets = (await getDatasets(DATASET_SCOPE, projectId).catch(() => [])).filter(
    (dataset) => {
      const matchesQuery =
        !query ||
        dataset.name.toLowerCase().includes(query.toLowerCase()) ||
        dataset.id.includes(query);
      const matchesRecipe =
        recipeFilters.length === 0 || (!!dataset.recipe && recipeFilters.includes(dataset.recipe));
      return matchesQuery && matchesRecipe;
    }
  );

  return (
    <div className="flex flex-col gap-4">
      {await renderDatasetSurface(filteredDatasets, DATASET_SCOPE, query, recipeFilters)}
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
