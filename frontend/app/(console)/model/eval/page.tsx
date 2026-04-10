import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { buttonVariants } from "@/components/ui/button";
import {
  getBenchmarkCatalog,
  getEvalTemplates,
  getEvaluationLeaderboards,
  getEvaluationRuns
} from "@/features/eval/api";
import { BenchmarkCatalogTable } from "@/features/eval/components/benchmark-catalog-table";
import { EvalDimensionCatalogTable } from "@/features/eval/components/eval-dimension-catalog-table";
import { EvaluationLeaderboardListTable } from "@/features/eval/components/evaluation-leaderboard-list-table";
import { EvaluationRunCreateSheet } from "@/features/eval/components/evaluation-run-create-sheet";
import { EvaluationRunListTable } from "@/features/eval/components/evaluation-run-list-table";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";
import type {
  BenchmarkDefinitionSummary,
  EvalTemplateSummary,
  EvaluationLeaderboardSummaryV2,
  EvaluationRunSummaryV2,
  RegistryModelSummary
} from "@/types/api";

const evalTabs = [
  { key: "runs", label: "评测任务" },
  { key: "leaderboards", label: "排行榜" },
  { key: "benchmarks", label: "Benchmark" },
  { key: "dimensions", label: "评测维度" }
] as const;

export default async function ModelEvalPage({
  searchParams
}: {
  searchParams: Promise<{ tab?: string; q?: string; create?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  if (resolvedSearchParams.tab === "probes") {
    const params = new URLSearchParams();
    params.set("tab", resolvedSearchParams.create === "1" ? "tasks" : "nodes");
    if (resolvedSearchParams.q?.trim()) {
      params.set("q", resolvedSearchParams.q.trim());
    }
    if (resolvedSearchParams.create === "1") {
      params.set("create", "1");
    }
    redirect(`/model/probes?${params.toString()}`);
  }
  const currentTab = evalTabs.some((tab) => tab.key === resolvedSearchParams.tab)
    ? (resolvedSearchParams.tab as (typeof evalTabs)[number]["key"])
    : "runs";
  const query = resolvedSearchParams.q?.trim() ?? "";
  const runCreateOpen = currentTab === "runs" && resolvedSearchParams.create === "1";
  const projectId = await getCurrentProjectIdFromCookie();

  let benchmarks: BenchmarkDefinitionSummary[] = [];
  let models: RegistryModelSummary[] = [];
  let runs: EvaluationRunSummaryV2[] = [];
  let leaderboards: EvaluationLeaderboardSummaryV2[] = [];
  let dimensions: EvalTemplateSummary[] = [];

  if (currentTab === "runs") {
    const [benchmarkResult, modelResult, runResult] = await Promise.all([
      getBenchmarkCatalog(projectId).catch(() => []),
      getRegistryModels(projectId).catch(() => []),
      getEvaluationRuns(projectId).catch(() => [])
    ]);
    benchmarks = benchmarkResult;
    models = modelResult;
    runs = filterRuns(runResult, query);
  }

  if (currentTab === "leaderboards") {
    leaderboards = filterLeaderboards(
      await getEvaluationLeaderboards(projectId).catch(() => []),
      query
    );
  }

  if (currentTab === "benchmarks") {
    benchmarks = filterBenchmarks(
      await getBenchmarkCatalog(projectId).catch(() => []),
      query
    );
  }

  if (currentTab === "dimensions") {
    dimensions = filterDimensions(await getEvalTemplates().catch(() => []), query);
  }

  const builtinBenchmarks = benchmarks.filter((benchmark) => benchmark.source_type === "builtin");
  const customBenchmarks = benchmarks.filter((benchmark) => benchmark.source_type !== "builtin");

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

      {currentTab === "runs" ? (
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
              benchmarks={benchmarks}
              initialOpen={runCreateOpen}
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

      {currentTab === "benchmarks" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索 Benchmark、分类或评测维度"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <div className="flex items-center gap-2">
              <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval-templates/create">
                创建评测维度
              </Link>
              <Link className={buttonVariants({ size: "sm" })} href="/model/eval-benchmarks/create">
                创建 Benchmark
              </Link>
            </div>
          </ConsoleListToolbar>

          <div className="space-y-6">
            <section className="space-y-3">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-slate-100">基线 Benchmark</h2>
                <p className="text-sm text-slate-400">
                  平台预置的标准能力评测集合，只展示与使用，不在这里做维护。
                </p>
              </div>
              <BenchmarkCatalogTable
                benchmarks={builtinBenchmarks}
                emptyMessage="当前没有可展示的基线 Benchmark。"
              />
            </section>

            <section className="space-y-3">
              <div className="space-y-1">
                <h2 className="text-base font-semibold text-slate-100">我的 Benchmark</h2>
                <p className="text-sm text-slate-400">
                  自定义 Benchmark 会绑定一个评测维度，Benchmark Version 就是该 Benchmark 的数据集版本。
                </p>
              </div>
              <BenchmarkCatalogTable
                benchmarks={customBenchmarks}
                emptyMessage="当前还没有自定义 Benchmark。请先创建 Benchmark，并上传至少一个 Version。"
              />
            </section>
          </div>
        </>
      ) : null}

      {currentTab === "dimensions" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索评测维度名称、类型或评分器"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <Link className={buttonVariants({ size: "sm" })} href="/model/eval-templates/create">
              创建评测维度
            </Link>
          </ConsoleListToolbar>

          <EvalDimensionCatalogTable dimensions={dimensions} />
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

function filterLeaderboards(leaderboards: EvaluationLeaderboardSummaryV2[], query: string) {
  if (!query) {
    return leaderboards;
  }
  const normalizedQuery = query.toLowerCase();
  return leaderboards.filter((leaderboard) =>
    [leaderboard.name, leaderboard.target_name, leaderboard.target_version]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}

function filterBenchmarks(benchmarks: BenchmarkDefinitionSummary[], query: string) {
  if (!query) {
    return benchmarks;
  }
  const normalizedQuery = query.toLowerCase();
  return benchmarks.filter((benchmark) =>
    [
      benchmark.name,
      benchmark.display_name,
      benchmark.description,
      benchmark.category ?? "",
      benchmark.eval_template_name ?? "",
      ...benchmark.tags
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}

function filterDimensions(dimensions: EvalTemplateSummary[], query: string) {
  if (!query) {
    return dimensions;
  }
  const normalizedQuery = query.toLowerCase();
  return dimensions.filter((dimension) =>
    [
      dimension.name,
      dimension.description ?? "",
      dimension.template_type,
      dimension.preset_id ?? "",
      dimension.model ?? ""
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}
