"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { useRouter } from "next/navigation";
import { deleteProbe } from "@/features/eval/api";
import type { ProbeDetail } from "@/types/api";

export function ProbeDetailPanel({ probe }: { probe: ProbeDetail | null }) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [pendingDelete, setPendingDelete] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);

  if (!probe) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-800/80 px-6 py-14 text-sm text-slate-500">
        当前没有可展示的 Probe 节点详情。
      </div>
    );
  }

  const currentProbe = probe;
  const statusMeta = getProbeStatusMeta(probe.status);
  const latestHeartbeat = probe.heartbeats[0] ?? null;
  const canDelete = probe.status === "offline";

  async function handleDelete() {
    setPendingDelete(true);
    setActionError(null);
    try {
      await deleteProbe(currentProbe.id);
      router.push("/model/probes?tab=nodes");
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除 Probe 节点失败");
      setPendingDelete(false);
      setConfirmOpen(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="space-y-2 rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)] px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-50">{currentProbe.display_name}</h2>
            <Badge className={statusMeta.className} variant={statusMeta.variant}>
              {statusMeta.label}
            </Badge>
            <Badge variant="outline">{currentProbe.name}</Badge>
          </div>
          <Button
            className="border border-rose-500/35 bg-rose-950/20 text-rose-100 hover:bg-rose-950/40"
            disabled={!canDelete || pendingDelete}
            onClick={() => {
              setActionError(null);
              setConfirmOpen(true);
            }}
            title={canDelete ? undefined : "只有离线节点支持删除"}
            variant="outline"
          >
            删除节点
          </Button>
        </div>
        <div className="text-sm text-slate-400">{currentProbe.id}</div>
        {actionError ? (
          <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
            {actionError}
          </div>
        ) : null}
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="网络位置" value={formatProbeLocation(currentProbe)} />
        <SummaryCard label="Agent 版本" value={currentProbe.agent_version ?? "--"} />
        <SummaryCard label="最近心跳" value={formatDateTime(currentProbe.last_heartbeat)} />
        <SummaryCard label="网络类型" value={currentProbe.network_type || "--"} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">设备信息</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonBlock value={currentProbe.device_info_json} />
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">节点元数据</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonBlock value={currentProbe.metadata_json} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">最新网络指标</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonBlock value={(latestHeartbeat?.network_metrics_json as Record<string, unknown>) ?? {}} />
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">最新 Agent 状态</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonBlock value={(latestHeartbeat?.agent_status_json as Record<string, unknown>) ?? {}} />
          </CardContent>
        </Card>
      </section>

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader>
          <CardTitle className="text-base text-slate-50">最近心跳</CardTitle>
        </CardHeader>
        <CardContent>
          {currentProbe.heartbeats.length === 0 ? (
            <div className="text-sm text-slate-500">当前还没有心跳记录。</div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-slate-800/80">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>时间</TableHead>
                    <TableHead>上报 IP</TableHead>
                    <TableHead>本地 IP</TableHead>
                    <TableHead>活跃任务</TableHead>
                    <TableHead>当前任务</TableHead>
                    <TableHead>工作目录</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {currentProbe.heartbeats.map((heartbeat) => {
                    const agentStatus = heartbeat.agent_status_json as Record<string, unknown>;
                    const networkMetrics = heartbeat.network_metrics_json as Record<string, unknown>;
                    return (
                      <TableRow key={`${heartbeat.created_at}-${heartbeat.ip_address}`}>
                        <TableCell>{formatDateTime(heartbeat.created_at)}</TableCell>
                        <TableCell>{heartbeat.ip_address}</TableCell>
                        <TableCell>{formatUnknown(networkMetrics.local_ip)}</TableCell>
                        <TableCell>{formatUnknown(agentStatus.active_tasks)}</TableCell>
                        <TableCell className="max-w-[180px] truncate">
                          {formatUnknown(agentStatus.current_task_id)}
                        </TableCell>
                        <TableCell className="max-w-[280px] truncate">
                          {formatUnknown(agentStatus.work_dir)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog
        onOpenChange={(open) => {
          if (!pendingDelete) {
            setConfirmOpen(open);
          }
        }}
        open={confirmOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 Probe 节点</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除节点「{currentProbe.display_name}」以及它关联的心跳和 Probe 任务记录，当前操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingDelete}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500/90 text-white hover:bg-red-500"
              disabled={pendingDelete}
              onClick={() => void handleDelete()}
            >
              {pendingDelete ? "处理中..." : "删除节点"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.68)] px-4 py-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-sm text-slate-100">{value}</div>
    </div>
  );
}

function JsonBlock({ value }: { value: Record<string, unknown> }) {
  if (Object.keys(value).length === 0) {
    return <div className="text-sm text-slate-500">当前为空。</div>;
  }

  return (
    <pre className="overflow-x-auto rounded-2xl border border-slate-800/80 bg-[rgba(8,13,20,0.92)] p-4 text-xs leading-6 text-slate-300">
      {JSON.stringify(value, null, 2)}
    </pre>
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

function formatProbeLocation(probe: ProbeDetail) {
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

function formatUnknown(value: unknown) {
  if (value == null) {
    return "--";
  }
  if (typeof value === "string" && value.trim() === "") {
    return "--";
  }
  return String(value);
}
