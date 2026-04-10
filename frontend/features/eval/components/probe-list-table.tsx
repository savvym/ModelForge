import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import type { ProbeSummary } from "@/types/api";

export function ProbeListTable({ probes }: { probes: ProbeSummary[] }) {
  const empty = probes.length === 0;

  return (
    <ConsoleListTableSurface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>节点名称/ID</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>网络位置</TableHead>
            <TableHead>Agent 版本</TableHead>
            <TableHead>最近心跳</TableHead>
            <TableHead>标签</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {empty ? (
            <TableRow className="hover:bg-transparent">
              <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={6}>
                当前还没有 Probe 节点。先启动并注册一个 probe agent，它就会出现在这里。
              </TableCell>
            </TableRow>
          ) : (
            probes.map((probe) => {
              const statusMeta = getProbeStatusMeta(probe.status);
              const location = formatProbeLocation(probe);
              const tags = normalizeTags(probe.tags_json);

              return (
                <TableRow key={probe.id}>
                  <TableCell className="min-w-[260px] align-top">
                    <div className="font-medium text-slate-100">{probe.display_name}</div>
                    <div className="mt-1 text-xs text-slate-500">{probe.name}</div>
                    <div className="mt-1 text-xs text-slate-600">{probe.id}</div>
                    {probe.last_error_message ? (
                      <div className="mt-2 line-clamp-2 text-xs text-rose-300">
                        {probe.last_error_message}
                      </div>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Badge className={statusMeta.className} variant={statusMeta.variant}>
                      {statusMeta.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="min-w-[220px]">
                    <div className="text-sm text-slate-300">{location}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {probe.network_type}
                      {probe.ip_address ? ` · ${probe.ip_address}` : ""}
                    </div>
                  </TableCell>
                  <TableCell>{probe.agent_version ?? "--"}</TableCell>
                  <TableCell>{formatDateTime(probe.last_heartbeat)}</TableCell>
                  <TableCell className="min-w-[220px]">
                    <div className="flex flex-wrap gap-1.5">
                      {tags.length ? (
                        tags.map((tag) => (
                          <span
                            className="rounded-full border border-slate-800/80 bg-slate-900/70 px-2 py-0.5 text-xs text-slate-300"
                            key={`${probe.id}-${tag}`}
                          >
                            {tag}
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-slate-500">--</span>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
  );
}

function getProbeStatusMeta(status: string) {
  if (status === "online") {
    return {
      label: "在线",
      variant: "outline" as const,
      className: "border-emerald-400/35 bg-emerald-500/10 text-emerald-200"
    };
  }
  if (status === "offline") {
    return {
      label: "离线",
      variant: "outline" as const,
      className: "border-amber-400/25 bg-amber-500/10 text-amber-200"
    };
  }
  if (status === "disabled") {
    return {
      label: "已禁用",
      variant: "outline" as const,
      className: "border-rose-400/25 bg-rose-500/10 text-rose-200"
    };
  }
  return {
    label: status,
    variant: "outline" as const,
    className: "border-slate-700 bg-slate-900/70 text-slate-300"
  };
}

function normalizeTags(value: unknown[]): string[] {
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function formatProbeLocation(probe: ProbeSummary) {
  const parts = [probe.city, probe.region, probe.country].filter(Boolean);
  if (parts.length) {
    return parts.join(" / ");
  }
  if (probe.isp) {
    return probe.isp;
  }
  return "未知位置";
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
