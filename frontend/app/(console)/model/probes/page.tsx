import Link from "next/link";
import {
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { getProbeDetail, getProbes, getProbeTasks } from "@/features/eval/api";
import { ProbeDetailPanel } from "@/features/eval/components/probe-detail-panel";
import { ProbeNodeList } from "@/features/eval/components/probe-node-list";
import { ProbeTaskCreateSheet } from "@/features/eval/components/probe-task-create-sheet";
import { ProbeTaskListTable } from "@/features/eval/components/probe-task-list-table";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";
import type { ProbeDetail, ProbeSummary, ProbeTaskSummary } from "@/types/api";

const probeTabs = [
  { key: "nodes", label: "Probe 节点" },
  { key: "tasks", label: "任务" }
] as const;

export default async function ModelProbePage({
  searchParams
}: {
  searchParams: Promise<{ tab?: string; q?: string; create?: string; probe?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const currentTab = probeTabs.some((tab) => tab.key === resolvedSearchParams.tab)
    ? (resolvedSearchParams.tab as (typeof probeTabs)[number]["key"])
    : "nodes";
  const query = resolvedSearchParams.q?.trim() ?? "";
  const createOpen = currentTab === "tasks" && resolvedSearchParams.create === "1";
  const projectId = await getCurrentProjectIdFromCookie();

  let probes: ProbeSummary[] = [];
  let probeOptions: ProbeSummary[] = [];
  let probeTasks: ProbeTaskSummary[] = [];
  let selectedProbeId: string | null = null;
  let selectedProbe: ProbeDetail | null = null;

  if (currentTab === "nodes") {
    const probeResult = await getProbes(projectId).catch(() => []);
    probeOptions = probeResult;
    probes = filterProbes(probeResult, query);
    selectedProbeId =
      probes.find((probe) => probe.id === resolvedSearchParams.probe)?.id ?? probes[0]?.id ?? null;
    selectedProbe = selectedProbeId
      ? await getProbeDetail(selectedProbeId, projectId).catch(() => null)
      : null;
  }

  if (currentTab === "tasks") {
    const [probeResult, taskResult] = await Promise.all([
      getProbes(projectId).catch(() => []),
      getProbeTasks(projectId).catch(() => [])
    ]);
    probeOptions = probeResult;
    probeTasks = filterProbeTasks(taskResult, query, probeResult);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800/80">
        <div className="flex min-w-0 items-center gap-5">
          {probeTabs.map((tab) => (
            <Link
              aria-current={currentTab === tab.key ? "page" : undefined}
              key={tab.key}
              className={cn(
                "-mb-px inline-flex h-9 items-center border-b-2 px-0.5 text-[13px] transition-colors",
                currentTab === tab.key
                  ? "border-slate-100 font-medium text-slate-50"
                  : "border-transparent text-slate-500 hover:text-slate-200"
              )}
              href={buildProbeQuery({ tab: tab.key, q: query })}
              prefetch
            >
              {tab.label}
            </Link>
          ))}
        </div>
      </div>

      {currentTab === "nodes" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/probes"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索 Probe 名称、地区、状态或标签"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>
          </ConsoleListToolbar>

          <div className="space-y-3">
            <div className="space-y-1">
              <h2 className="text-base font-semibold text-slate-100">Probe 节点</h2>
              <p className="text-sm text-slate-400">
                左侧选择节点，右侧查看该节点的设备信息、最近心跳和当前状态。
              </p>
            </div>
            <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
              <div className="min-w-0">
                <ProbeNodeList probes={probes} query={query} selectedProbeId={selectedProbeId} />
              </div>
              <div className="min-w-0">
                <ProbeDetailPanel probe={selectedProbe} />
              </div>
            </div>
          </div>
        </>
      ) : null}

      {currentTab === "tasks" ? (
        <>
          <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
            <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
              <ConsoleListSearchForm
                action="/model/probes"
                className="max-w-[560px] flex-none"
                defaultValue={query}
                inputClassName="min-w-[320px]"
                placeholder="搜索任务名称、Probe、状态或错误"
              >
                <input name="tab" type="hidden" value={currentTab} />
              </ConsoleListSearchForm>
            </ConsoleListToolbarCluster>

            <ProbeTaskCreateSheet initialOpen={createOpen} probes={probeOptions} />
          </ConsoleListToolbar>

          <div className="space-y-3">
            <div className="space-y-1">
              <h2 className="text-base font-semibold text-slate-100">Probe 任务</h2>
              <p className="text-sm text-slate-400">
                创建后的任务会被目标 Probe 领取执行；过期的 running 任务也会重新进入 claim 流程。
              </p>
            </div>
            <ProbeTaskListTable probes={probeOptions} tasks={probeTasks} />
          </div>
        </>
      ) : null}
    </div>
  );
}

function buildProbeQuery({
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
  return `/model/probes?${params.toString()}`;
}

function filterProbes(probes: ProbeSummary[], query: string) {
  if (!query) {
    return probes;
  }
  const normalizedQuery = query.toLowerCase();
  return probes.filter((probe) =>
    [
      probe.name,
      probe.display_name,
      probe.status,
      probe.ip_address ?? "",
      probe.region ?? "",
      probe.country ?? "",
      probe.city ?? "",
      probe.network_type,
      ...probe.tags_json.map((value) => (typeof value === "string" ? value : ""))
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}

function filterProbeTasks(
  tasks: ProbeTaskSummary[],
  query: string,
  probes: ProbeSummary[]
) {
  if (!query) {
    return tasks;
  }
  const normalizedQuery = query.toLowerCase();
  const probeNameMap = new Map(
    probes.map((probe) => [probe.id, `${probe.display_name} ${probe.name}`.toLowerCase()] as const)
  );
  return tasks.filter((task) =>
    [
      task.id,
      task.name,
      task.task_type,
      task.status,
      task.error_message ?? "",
      probeNameMap.get(task.probe_id) ?? "",
      typeof task.progress_json.summary === "string" ? task.progress_json.summary : ""
    ]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery)
  );
}
