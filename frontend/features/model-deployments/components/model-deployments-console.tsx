"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { ExternalLink, RefreshCw, Server, Terminal } from "lucide-react";
import { ConsolePage } from "@/components/console/console-page";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  getModelDeploymentEvents,
  refreshModelDeployment
} from "@/features/model-deployments/api";
import { cn } from "@/lib/utils";
import type { ModelDeploymentEvent, ModelDeploymentSummary } from "@/types/api";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function formatPhase(value?: string | null) {
  const labels: Record<string, string> = {
    deploying: "部署中",
    downloading: "下载中",
    error: "失败",
    pending: "等待中",
    ready: "可用",
    smoke_testing: "测试中",
    starting: "启动中",
    stopped: "已停止",
    stopping_previous: "切换中",
    warming: "预热中"
  };
  return labels[value ?? ""] ?? value ?? "--";
}

function phaseVariant(value?: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (value === "ready" || value === "active") {
    return "default";
  }
  if (value === "error" || value === "failed") {
    return "destructive";
  }
  if (value === "stopped") {
    return "secondary";
  }
  return "outline";
}

export function ModelDeploymentsConsole({
  initialDeployments,
  selectedDeploymentId
}: {
  initialDeployments: ModelDeploymentSummary[];
  selectedDeploymentId?: string | null;
}) {
  const [deployments, setDeployments] = useState(initialDeployments);
  const [events, setEvents] = useState<ModelDeploymentEvent[]>([]);
  const [selectedId, setSelectedId] = useState(
    selectedDeploymentId ?? initialDeployments[0]?.id ?? null
  );
  const [isPending, startTransition] = useTransition();
  const selected = useMemo(
    () => deployments.find((deployment) => deployment.id === selectedId) ?? deployments[0] ?? null,
    [deployments, selectedId]
  );

  useEffect(() => {
    if (!selected?.id) {
      setEvents([]);
      return;
    }
    void getModelDeploymentEvents(selected.id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [selected?.id]);

  function refreshSelected() {
    if (!selected?.id) {
      return;
    }
    startTransition(() => {
      void refreshModelDeployment(selected.id).then((updated) => {
        setDeployments((current) =>
          current.map((item) => (item.id === updated.id ? updated : item))
        );
        void getModelDeploymentEvents(updated.id).then(setEvents).catch(() => setEvents([]));
      });
    });
  }

  return (
    <ConsolePage pageKey="endpoint" showScaffold={false}>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_420px]">
        <section className="overflow-hidden rounded-lg border border-border bg-card/80">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
            <div>
              <div className="text-sm font-medium text-foreground">部署任务</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {deployments.length} 个在线推理部署记录
              </div>
            </div>
            <Button disabled={!selected || isPending} onClick={refreshSelected} size="sm" variant="outline">
              <RefreshCw className={cn(isPending ? "animate-spin" : "")} />
              刷新状态
            </Button>
          </div>

          <ConsoleListTableSurface>
            <Table className="text-sm">
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="h-10 px-3">部署名称</TableHead>
                  <TableHead className="h-10 px-3">模型</TableHead>
                  <TableHead className="h-10 px-3">状态</TableHead>
                  <TableHead className="h-10 px-3">进度</TableHead>
                  <TableHead className="h-10 px-3">更新时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployments.length ? (
                  deployments.map((deployment) => (
                    <TableRow
                      className="cursor-pointer"
                      data-state={deployment.id === selected?.id ? "selected" : undefined}
                      key={deployment.id}
                      onClick={() => setSelectedId(deployment.id)}
                    >
                      <TableCell className="px-3 py-2.5 font-medium text-foreground">
                        {deployment.name}
                      </TableCell>
                      <TableCell className="px-3 py-2.5 text-muted-foreground">
                        {deployment.served_model_name ?? deployment.model_name ?? "--"}
                      </TableCell>
                      <TableCell className="px-3 py-2.5">
                        <Badge variant={phaseVariant(deployment.phase ?? deployment.status)}>
                          {formatPhase(deployment.phase ?? deployment.status)}
                        </Badge>
                      </TableCell>
                      <TableCell className="px-3 py-2.5">
                        <div className="flex min-w-[120px] items-center gap-2">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-primary"
                              style={{ width: `${deployment.progress}%` }}
                            />
                          </div>
                          <span className="w-9 text-right text-xs text-muted-foreground">
                            {deployment.progress}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="px-3 py-2.5 text-muted-foreground">
                        {formatDateTime(deployment.updated_at)}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell className="h-40 text-center text-muted-foreground" colSpan={5}>
                      暂无部署任务。从“我的模型”点击部署后会出现在这里。
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ConsoleListTableSurface>
        </section>

        <section className="overflow-hidden rounded-lg border border-border bg-card/80">
          <div className="border-b border-border px-4 py-4">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Server />
              当前部署
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {selected?.name ?? "选择一个部署记录查看详情"}
            </div>
          </div>

          {selected ? (
            <div className="flex flex-col gap-4 p-4">
              <div className="grid gap-3 text-sm">
                <InfoRow label="模型" value={selected.served_model_name ?? selected.model_name ?? "--"} />
                <InfoRow label="Agent" value={selected.agent_base_url ?? "--"} />
                <InfoRow label="最近事件" value={selected.last_event ?? "--"} />
                <InfoRow label="错误" value={selected.error_message ?? "--"} tone="danger" />
              </div>

              {selected.endpoint_url ? (
                <a
                  className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
                  href={selected.endpoint_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink />
                  {selected.endpoint_url}
                </a>
              ) : null}

              <div className="rounded-lg border border-border bg-background/40">
                <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-sm font-medium">
                  <Terminal />
                  部署事件
                </div>
                <ScrollArea className="h-[380px]">
                  <div className="flex flex-col gap-3 p-3">
                    {events.length ? (
                      events.map((event) => (
                        <div className="rounded-md border border-border bg-card/80 px-3 py-2" key={event.id ?? event.created_at}>
                          <div className="flex items-start justify-between gap-3">
                            <div className="text-sm text-foreground">{event.message}</div>
                            <Badge variant={event.level === "error" ? "destructive" : "outline"}>
                              {event.event_type}
                            </Badge>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {formatDateTime(event.created_at)}
                            {typeof event.progress === "number" ? ` · ${event.progress}%` : ""}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="py-12 text-center text-sm text-muted-foreground">
                        暂无事件，刷新状态后再试。
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </ConsolePage>
  );
}

function InfoRow({
  label,
  value,
  tone
}: {
  label: string;
  value: string;
  tone?: "danger";
}) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-3">
      <div className="text-muted-foreground">{label}</div>
      <div className={cn("truncate text-foreground", tone === "danger" && "text-destructive")}>
        {value}
      </div>
    </div>
  );
}
