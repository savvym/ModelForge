import Link from "next/link";
import {
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { buttonVariants } from "@/components/ui/button";
import { getBenchmarkCatalog, getEvalJobs, getEvalTemplates } from "@/features/eval/api";
import { EvalJobCreateSheet } from "@/features/eval/components/eval-job-create-sheet";
import { BenchmarkCatalogTable } from "@/features/eval/components/benchmark-catalog-table";
import { EvalJobListTable } from "@/features/eval/components/eval-job-list-table";
import { EvalTemplateListTable } from "@/features/eval/components/eval-template-list-table";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";
import type {
  BenchmarkDefinitionSummary,
  EvalJobSummary,
  RegistryModelSummary
} from "@/types/api";

const evalTabs = [
  { key: "jobs", label: "评测任务" },
  { key: "management", label: "评测管理" },
  { key: "templates", label: "评测模板" }
] as const;

export default async function ModelEvalPage({
  searchParams
}: {
  searchParams: Promise<{ tab?: string; q?: string; create?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const currentTab = evalTabs.some((tab) => tab.key === resolvedSearchParams.tab)
    ? (resolvedSearchParams.tab as (typeof evalTabs)[number]["key"])
    : "jobs";
  const query = resolvedSearchParams.q?.trim() ?? "";
  const createOpen = currentTab === "jobs" && resolvedSearchParams.create === "1";
  const projectId = await getCurrentProjectIdFromCookie();
  let createFormBenchmarks: BenchmarkDefinitionSummary[] = [];
  let createFormModels: RegistryModelSummary[] = [];
  let filteredJobs: EvalJobSummary[] = [];

  if (currentTab === "jobs") {
    const [benchmarksResult, modelsResult, jobsResult] = await Promise.all([
      getBenchmarkCatalog(projectId).catch(() => []),
      getRegistryModels(projectId).catch(() => []),
      getEvalJobs(projectId).catch(() => [])
    ]);

    createFormBenchmarks = benchmarksResult;
    createFormModels = modelsResult;
    filteredJobs = jobsResult.filter((job) => {
      const matchesQuery =
        !query ||
        job.name.toLowerCase().includes(query.toLowerCase()) ||
        job.id.includes(query) ||
        job.model_name.toLowerCase().includes(query.toLowerCase());
      return matchesQuery;
    });
  }

  const benchmarks =
    currentTab === "management"
      ? (await getBenchmarkCatalog(projectId).catch(() => []))
          .filter((benchmark) => {
            if (!query) {
              return true;
            }
            const normalizedQuery = query.toLowerCase();
            const versionHaystack = benchmark.versions
              .flatMap((version) => [version.id, version.display_name, version.description])
              .join(" ")
              .toLowerCase();
            const benchmarkHaystack = [
              benchmark.name,
              benchmark.display_name,
              benchmark.description,
              benchmark.default_eval_method,
              benchmark.category ?? "",
              benchmark.tags.join(" "),
            ]
              .join(" ")
              .toLowerCase();
            return (
              benchmarkHaystack.includes(normalizedQuery) ||
              versionHaystack.includes(normalizedQuery)
            );
          })
          .sort((left, right) => {
            if (left.eval_job_count !== right.eval_job_count) {
              return right.eval_job_count - left.eval_job_count;
            }
            return left.display_name.localeCompare(right.display_name);
          })
      : [];
  const templates =
    currentTab === "templates"
      ? (await getEvalTemplates().catch(() => []))
          .filter((t) => {
            if (!query) return true;
            const haystack = [t.name, t.description ?? "", t.output_type].join(" ").toLowerCase();
            return haystack.includes(query.toLowerCase());
          })
          .sort((a, b) => a.name.localeCompare(b.name))
      : [];

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

      {currentTab === "jobs" ? (
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

            <EvalJobCreateSheet
              benchmarks={createFormBenchmarks}
              initialOpen={createOpen}
              models={createFormModels}
            />
          </ConsoleListToolbar>

          <EvalJobListTable initialJobs={filteredJobs} />
        </>
      ) : null}

      {currentTab === "management" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索 Benchmark、Version ID 或版本描述"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <Link className={buttonVariants({ size: "sm" })} href="/model/eval-benchmarks/create">
              创建 Benchmark
            </Link>
          </ConsoleListToolbar>

          <BenchmarkCatalogTable benchmarks={benchmarks} />
        </>
      ) : null}

      {currentTab === "templates" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/eval"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索模板名称或描述"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <Link className={buttonVariants({ size: "sm" })} href="/model/eval-templates/create">
              创建模板
            </Link>
          </ConsoleListToolbar>

          <EvalTemplateListTable templates={templates} />
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
