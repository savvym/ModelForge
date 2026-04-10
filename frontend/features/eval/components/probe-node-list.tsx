import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ProbeSummary } from "@/types/api";

export function ProbeNodeList({
  probes,
  query,
  selectedProbeId
}: {
  probes: ProbeSummary[];
  query: string;
  selectedProbeId?: string | null;
}) {
  if (probes.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-10 text-sm text-slate-500">
        当前还没有 Probe 节点。先启动并注册一个 probe agent，它就会出现在这里。
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {probes.map((probe) => {
        const statusMeta = getProbeStatusMeta(probe.status);
        const active = probe.id === selectedProbeId;
        return (
          <Link
            className={cn(
              "block rounded-2xl border px-4 py-3 transition-colors",
              active
                ? "border-sky-400/40 bg-[rgba(17,28,42,0.9)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                : "border-slate-800/80 bg-[rgba(10,15,22,0.72)] hover:border-slate-700/90 hover:bg-[rgba(14,20,29,0.84)]"
            )}
            href={buildNodeHref({ probeId: probe.id, q: query })}
            key={probe.id}
            prefetch
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium text-slate-100">{probe.display_name}</div>
                <div className="mt-1 truncate text-xs text-slate-500">{probe.name}</div>
              </div>
              <Badge className={statusMeta.className} variant={statusMeta.variant}>
                {statusMeta.label}
              </Badge>
            </div>

            <div className="mt-3 space-y-1.5 text-xs text-slate-400">
              <div className="truncate">{formatProbeLocation(probe)}</div>
              <div className="truncate">{probe.agent_version ?? "--"} · {probe.network_type}</div>
              <div className="truncate">最近心跳 {formatDateTime(probe.last_heartbeat)}</div>
              <div className="truncate text-slate-600">{probe.id}</div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

function buildNodeHref({ probeId, q }: { probeId: string; q: string }) {
  const params = new URLSearchParams();
  params.set("tab", "nodes");
  params.set("probe", probeId);
  if (q) {
    params.set("q", q);
  }
  return `/model/probes?${params.toString()}`;
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
