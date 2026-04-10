import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { getEvalStatusMeta } from "@/features/eval/status";
import type { ProbeSummary, ProbeTaskSummary } from "@/types/api";

export function ProbeTaskListTable({
  probes,
  tasks
}: {
  probes: ProbeSummary[];
  tasks: ProbeTaskSummary[];
}) {
  const probeNameMap = new Map(
    probes.map((probe) => [probe.id, probe.display_name || probe.name] as const)
  );
  const empty = tasks.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>任务名称/ID</TableHead>
            <TableHead>Probe</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>进度</TableHead>
            <TableHead>尝试次数</TableHead>
            <TableHead>租约/完成时间</TableHead>
            <TableHead>创建时间</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={7}>
                当前还没有 Probe 任务。你可以先创建一个压测任务，让在线 Probe 去拉取执行。
              </TableCell>
            </TableRow>
          ) : (
            tasks.map((task) => {
              const statusMeta = getEvalStatusMeta(task.status);
              const progress = getTaskProgress(task);
              const deadlineLabel = formatLeaseDeadline(task);

              return (
                <TableRow key={task.id}>
                  <TableCell className="min-w-[300px] align-top">
                    <div className="font-medium text-slate-100">{task.name}</div>
                    <div className="mt-1 text-xs text-slate-500">{task.task_type}</div>
                    <div className="mt-1 text-xs text-slate-600">{task.id}</div>
                    {task.error_message ? (
                      <div className="mt-2 line-clamp-2 text-xs text-rose-300">
                        {task.error_message}
                      </div>
                    ) : null}
                  </TableCell>
                  <TableCell>{probeNameMap.get(task.probe_id) ?? task.probe_id}</TableCell>
                  <TableCell>
                    <Badge className={statusMeta.className} variant={statusMeta.variant}>
                      {statusMeta.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="min-w-[220px]">
                    <div className="text-sm text-slate-300">{progress.label}</div>
                    {progress.summary ? (
                      <div className="mt-1 line-clamp-2 text-xs text-slate-500">{progress.summary}</div>
                    ) : null}
                  </TableCell>
                  <TableCell>{task.attempt_count}</TableCell>
                  <TableCell>{deadlineLabel}</TableCell>
                  <TableCell>{formatDateTime(task.created_at)}</TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
  );
}

function getTaskProgress(task: ProbeTaskSummary) {
  const step = getNumericValue(task.progress_json.step);
  const total = getNumericValue(task.progress_json.total);
  const summary =
    typeof task.progress_json.summary === "string" ? task.progress_json.summary : null;

  if (typeof step === "number" && typeof total === "number" && total > 0) {
    return {
      label: `${step}/${total}`,
      summary
    };
  }

  if (summary) {
    return {
      label: summary,
      summary: null
    };
  }

  return {
    label: "--",
    summary: null
  };
}

function getNumericValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function formatLeaseDeadline(task: ProbeTaskSummary) {
  if (task.finished_at) {
    return formatDateTime(task.finished_at);
  }
  if (task.lease_expires_at) {
    return `租约至 ${formatDateTime(task.lease_expires_at)}`;
  }
  return "--";
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}
