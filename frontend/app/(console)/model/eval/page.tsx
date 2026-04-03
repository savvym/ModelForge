import Link from "next/link";
import {
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { buttonVariants } from "@/components/ui/button";
import {
  getEvaluationCatalog,
  getEvaluationLeaderboards,
  getEvaluationRuns
} from "@/features/eval/api";
import { EvaluationCatalogV2Panel } from "@/features/eval/components/evaluation-catalog-v2-panel";
import { EvaluationLeaderboardListTable } from "@/features/eval/components/evaluation-leaderboard-list-table";
import { EvaluationRunCreateSheet } from "@/features/eval/components/evaluation-run-create-sheet";
import { EvaluationRunListTable } from "@/features/eval/components/evaluation-run-list-table";
import { EvaluationTemplateRegistryPanel } from "@/features/eval/components/evaluation-template-registry-panel";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";
import type {
  EvaluationCatalogResponseV2,
  EvaluationLeaderboardSummaryV2,
  EvaluationRunSummaryV2,
  RegistryModelSummary
} from "@/types/api";

const evalTabs = [
  { key: "runs", label: "评测任务" },
  { key: "leaderboards", label: "排行榜" },
  { key: "catalog", label: "评测管理" },
  { key: "templates", label: "模板与策略" }
] as const;

export default async function ModelEvalPage({
  searchParams
}: {
  searchParams: Promise<{ tab?: string; q?: string; create?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const currentTab = evalTabs.some((tab) => tab.key === resolvedSearchParams.tab)
    ? (resolvedSearchParams.tab as (typeof evalTabs)[number]["key"])
    : "runs";
  const query = resolvedSearchParams.q?.trim() ?? "";
  const createOpen = currentTab === "runs" && resolvedSearchParams.create === "1";
  const projectId = await getCurrentProjectIdFromCookie();

  let catalog: EvaluationCatalogResponseV2 | null = null;
  let models: RegistryModelSummary[] = [];
  let runs: EvaluationRunSummaryV2[] = [];
  let leaderboards: EvaluationLeaderboardSummaryV2[] = [];

  if (currentTab === "runs") {
    const [catalogResult, modelsResult, runsResult] = await Promise.all([
      getEvaluationCatalog(projectId).catch(() => emptyCatalog()),
      getRegistryModels(projectId).catch(() => []),
      getEvaluationRuns(projectId).catch(() => [])
    ]);
    catalog = catalogResult;
    models = modelsResult;
    runs = filterRuns(runsResult, query);
  }

  if (currentTab === "leaderboards") {
    leaderboards = filterLeaderboards(
      await getEvaluationLeaderboards(projectId).catch(() => []),
      query
    );
  }

  if (currentTab === "catalog" || currentTab === "templates") {
    catalog = (await getEvaluationCatalog(projectId).catch(() => emptyCatalog()));
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800/80">
        <div className="flex min-w-0 items-center gap-5">
          {evalTabs.map((tab) => (
            <Link
              aria-current={currentTab === tab.key ? "page" : undefined}
              key={tab.key}
              className={cn(
                "-mb-px inline-flex h-9 items-center border-b-2 px-0.5 text-[13px] transition-colors",
                currentTab === tab.key
                  ? "border-slate-100 font-medium text-slate-50"
                  : "border-transparent text-slate-500 hover:text-slate-200"
              )}
              href={buildEvalQuery({ tab: tab.key, q: query })}
              prefetch
            >
              {tab.label}
            </Link>
          ))}
        </div>
      </div>

      {currentTab === "runs" && catalog ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[540px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索评测任务名称、ID 或模型"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <EvaluationRunCreateSheet
              catalog={catalog}
              initialOpen={createOpen}
              models={models}
            />
          </ConsoleListToolbar>

          <EvaluationRunListTable initialRuns={runs} />
        </>
      ) : null}

      {currentTab === "leaderboards" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[540px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索排行榜名称、目标或版本"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <Link className={buttonVariants({ size: "sm" })} href="/model/eval-leaderboards/create">
              创建排行榜
            </Link>
          </ConsoleListToolbar>

          <EvaluationLeaderboardListTable leaderboards={leaderboards} />
        </>
      ) : null}

      {currentTab === "catalog" && catalog ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索评测套件、类型或版本"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <div className="flex items-center gap-2">
              <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval-suites/create">
                创建评测套件
              </Link>
              <Link className={buttonVariants({ size: "sm" })} href="/model/eval-specs/create">
                创建评测类型
              </Link>
            </div>
          </ConsoleListToolbar>

          <EvaluationCatalogV2Panel catalog={filterCatalog(catalog, query)} />
        </>
      ) : null}

      {currentTab === "templates" && catalog ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索模板、Policy 或策略类型"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <div className="flex items-center gap-2">
              <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval-policies/create">
                创建 Judge Policy
              </Link>
              <Link className={buttonVariants({ size: "sm" })} href="/model/eval-templates/create">
                创建模板资产
              </Link>
            </div>
          </ConsoleListToolbar>

          <EvaluationTemplateRegistryPanel catalog={filterTemplates(catalog, query)} />
        </>
      ) : null}
    </div>
  );
}

function buildEvalQuery({
  tab,
  q
}: {
  tab: string;
  q: string;
}) {
  const params = new URLSearchParams();
  params.set("tab", tab);
  if (q) {
    params.set("q", q);
  }
  return `/model/eval?${params.toString()}`;
}

function emptyCatalog(): EvaluationCatalogResponseV2 {
  return {
    specs: [],
    suites: [],
    templates: [],
    judge_policies: []
  };
}

function filterRuns(runs: EvaluationRunSummaryV2[], query: string) {
  if (!query) {
    return runs;
  }
  const normalizedQuery = query.toLowerCase();
  return runs.filter((run) =>
    [run.name, run.id, run.model_name ?? "", run.kind, run.status]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}

function filterCatalog(catalog: EvaluationCatalogResponseV2, query: string): EvaluationCatalogResponseV2 {
  if (!query) {
    return catalog;
  }
  const normalizedQuery = query.toLowerCase();
  return {
    ...catalog,
    suites: catalog.suites.filter((suite) =>
      [
        suite.name,
        suite.display_name,
        suite.description ?? "",
        ...suite.versions.flatMap((version) => [
          version.version,
          version.display_name,
          version.description ?? "",
          ...version.items.map((item) => item.display_name)
        ])
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery)
    ),
    specs: catalog.specs.filter((spec) =>
      [
        spec.name,
        spec.display_name,
        spec.description ?? "",
        spec.capability_group ?? "",
        spec.capability_category ?? "",
        ...spec.versions.flatMap((version) => [
          version.version,
          version.display_name,
          version.description ?? "",
          version.engine,
          version.execution_mode,
          version.engine_benchmark_name ?? "",
          ...version.dataset_files.flatMap((file) => [
            file.file_key,
            file.display_name,
            file.file_name ?? "",
            file.source_uri ?? "",
            file.status
          ])
        ])
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery)
    )
  };
}

function filterTemplates(
  catalog: EvaluationCatalogResponseV2,
  query: string
): EvaluationCatalogResponseV2 {
  if (!query) {
    return catalog;
  }
  const normalizedQuery = query.toLowerCase();
  return {
    ...catalog,
    templates: catalog.templates.filter((template) =>
      [
        template.name,
        template.display_name,
        template.description ?? "",
        template.template_type,
        ...template.versions.map((version) => `v${version.version}`)
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery)
    ),
    judge_policies: catalog.judge_policies.filter((policy) =>
      [
        policy.name,
        policy.display_name,
        policy.description ?? "",
        policy.strategy,
        JSON.stringify(policy.execution_params_json),
        JSON.stringify(policy.model_selector_json)
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery)
    )
  };
}

function filterLeaderboards(
  leaderboards: EvaluationLeaderboardSummaryV2[],
  query: string
) {
  if (!query) {
    return leaderboards;
  }
  const normalizedQuery = query.toLowerCase();
  return leaderboards.filter((leaderboard) =>
    [
      leaderboard.name,
      leaderboard.description ?? "",
      leaderboard.target_kind,
      leaderboard.target_name,
      leaderboard.target_display_name,
      leaderboard.target_version,
      leaderboard.target_version_display_name
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}
