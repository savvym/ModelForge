"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ChevronDown,
  Cpu,
  ExternalLink,
  KeyRound,
  Play,
  Plus,
  RefreshCw,
  Server,
  SlidersHorizontal,
  Square,
  Terminal,
  Trash2
} from "lucide-react";
import { ConsolePage } from "@/components/console/console-page";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  checkInferenceMachineHealth,
  createInferenceMachine,
  deleteInferenceMachine,
  getMyDeployments,
  getModelDeployments,
  getModelDeploymentEvents,
  getInferenceMachines,
  refreshModelDeployment,
  startModelDeployment,
  stopModelDeployment,
  unloadModelDeployment
} from "@/features/model-deployments/api";
import { cn } from "@/lib/utils";
import type {
  InferenceMachineHealth,
  InferenceMachineSummary,
  ModelDeploymentEvent,
  ModelDeploymentSummary
} from "@/types/api";

function createInitialMachineForm() {
  return {
    agent_base_url: "",
    agent_token: "",
    description: "",
    dtype: "bfloat16",
    gpu_memory_utilization: "0.85",
    listen_port: "8000",
    max_model_len: "",
    name: "",
    runtime_api_key: "",
    runtime_public_host: "",
    tensor_parallel_size: "8",
    vllm_image: "vllm/vllm-openai:latest"
  };
}

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
    stopping: "停止中",
    stopped: "已停止",
    stopping_previous: "切换中",
    superseded: "已替换",
    unloaded: "已卸载",
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
  if (value === "stopped" || value === "superseded" || value === "unloaded") {
    return "secondary";
  }
  return "outline";
}

function healthVariant(value?: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (value === "ok") {
    return "default";
  }
  if (value === "unreachable" || value === "error") {
    return "destructive";
  }
  if (!value) {
    return "secondary";
  }
  return "outline";
}

function shouldPollDeployment(deployment: ModelDeploymentSummary) {
  const phase = deployment.phase ?? deployment.status;
  return [
    "deploying",
    "downloading",
    "pending",
    "smoke_testing",
    "starting",
    "stopping",
    "stopping_previous",
    "warming"
  ].includes(phase);
}

function isDeploymentRunning(deployment: ModelDeploymentSummary) {
  const phase = deployment.phase ?? deployment.status;
  return ["ready", "active"].includes(phase);
}

function isDeploymentStopped(deployment: ModelDeploymentSummary) {
  const phase = deployment.phase ?? deployment.status;
  return phase === "stopped";
}

function isDeploymentBusy(deployment: ModelDeploymentSummary) {
  return shouldPollDeployment(deployment);
}

function parseRequiredNumber(value: string, label: string) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    throw new Error(`${label} 需要填写数字。`);
  }
  return numberValue;
}

function readNumberField(value: Record<string, unknown> | undefined, key: string) {
  const rawValue = value?.[key];
  return typeof rawValue === "number" && Number.isFinite(rawValue) ? rawValue : null;
}

function readStringField(value: Record<string, unknown> | undefined, key: string) {
  const rawValue = value?.[key];
  return typeof rawValue === "string" && rawValue.trim() ? rawValue : null;
}

function formatGpuSummary(machine: InferenceMachineSummary) {
  const firstGpu = machine.last_gpus[0];
  const count = machine.last_gpu_count ?? machine.last_gpus.length;
  const name = readStringField(firstGpu, "name");
  if (!count) {
    return "待检查";
  }
  return name ? `${count} x ${name}` : `${count} GPU`;
}

function formatGpuMemory(machine: InferenceMachineSummary) {
  const firstGpu = machine.last_gpus[0];
  const memoryTotalMb = readNumberField(firstGpu, "memory_total_mb");
  if (memoryTotalMb == null) {
    return "GPU all";
  }
  return `${Math.round(memoryTotalMb / 1024)} GB / GPU`;
}

function applyMachineHealth(
  machine: InferenceMachineSummary,
  health: InferenceMachineHealth
): InferenceMachineSummary {
  return {
    ...machine,
    last_gpu_count: health.gpus.length,
    last_gpus: health.gpus,
    last_health_checked_at: health.checked_at,
    last_health_error: health.error,
    last_health_status: health.status,
    last_node_name: health.node_name
  };
}

export function ModelDeploymentsConsole({
  initialDeployments,
  initialMyDeployments,
  initialMachines,
  selectedDeploymentId
}: {
  initialDeployments: ModelDeploymentSummary[];
  initialMyDeployments: ModelDeploymentSummary[];
  initialMachines: InferenceMachineSummary[];
  selectedDeploymentId?: string | null;
}) {
  const [deployments, setDeployments] = useState(initialDeployments);
  const [myDeployments, setMyDeployments] = useState(initialMyDeployments);
  const [machines, setMachines] = useState(initialMachines);
  const [events, setEvents] = useState<ModelDeploymentEvent[]>([]);
  const [selectedId, setSelectedId] = useState(
    selectedDeploymentId ?? initialDeployments[0]?.id ?? null
  );
  const [isPending, startTransition] = useTransition();
  const [isMachinePending, startMachineTransition] = useTransition();
  const [isMachineDialogOpen, setIsMachineDialogOpen] = useState(false);
  const [isMachineAdvancedOpen, setIsMachineAdvancedOpen] = useState(false);
  const [machineForm, setMachineForm] = useState(createInitialMachineForm);
  const [machineFeedback, setMachineFeedback] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [deploymentFeedback, setDeploymentFeedback] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const selectedTask = useMemo(
    () => deployments.find((deployment) => deployment.id === selectedId) ?? deployments[0] ?? null,
    [deployments, selectedId]
  );
  const pollingDeploymentIds = useMemo(
    () =>
      [...deployments, ...myDeployments]
        .filter(shouldPollDeployment)
        .map((deployment) => deployment.id)
        .filter((deploymentId, index, deploymentIds) => deploymentIds.indexOf(deploymentId) === index)
        .sort()
        .join("|"),
    [deployments, myDeployments]
  );

  useEffect(() => {
    if (!selectedTask?.id) {
      setEvents([]);
      return;
    }
    void getModelDeploymentEvents(selectedTask.id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [selectedTask?.id]);

  useEffect(() => {
    if (!pollingDeploymentIds) {
      return;
    }

    let isCancelled = false;
    let isRefreshing = false;
    const deploymentIds = pollingDeploymentIds.split("|").filter(Boolean);

    async function refreshPollingDeployments() {
      if (isRefreshing) {
        return;
      }
      isRefreshing = true;
      try {
        await Promise.allSettled(
          deploymentIds.map((deploymentId) => refreshModelDeployment(deploymentId))
        );
        const [updatedDeployments, updatedMyDeployments] = await Promise.all([
          getModelDeployments(),
          getMyDeployments()
        ]);
        if (isCancelled) {
          return;
        }
        setDeployments(updatedDeployments);
        setMyDeployments(updatedMyDeployments);
        if (selectedId) {
          void getModelDeploymentEvents(selectedId).then(setEvents).catch(() => setEvents([]));
        }
      } catch {
        // The next interval will retry; keep the current snapshot visible.
      } finally {
        isRefreshing = false;
      }
    }

    void refreshPollingDeployments();
    const intervalId = window.setInterval(refreshPollingDeployments, 2500);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [pollingDeploymentIds, selectedId]);

  function refreshSelected() {
    if (!selectedTask?.id) {
      return;
    }
    startTransition(() => {
      void refreshModelDeployment(selectedTask.id)
        .then(() => Promise.all([getModelDeployments(), getMyDeployments()]))
        .then(([updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
          void getModelDeploymentEvents(selectedTask.id)
            .then(setEvents)
            .catch(() => setEvents([]));
        });
    });
  }

  function refreshDeploymentLists() {
    startTransition(() => {
      void Promise.all([getModelDeployments(), getMyDeployments()])
        .then(([updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
        })
        .catch((error: unknown) => {
          setDeploymentFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "刷新部署列表失败。"
          });
        });
    });
  }

  function runDeploymentAction(
    deployment: ModelDeploymentSummary,
    action: "start" | "stop" | "unload"
  ) {
    if (action === "unload" && !window.confirm(`确认卸载部署 ${deployment.name}？`)) {
      return;
    }
    setDeploymentFeedback(null);
    const actionLabels = {
      start: "启动",
      stop: "停止",
      unload: "卸载"
    };
    const actionMap = {
      start: startModelDeployment,
      stop: stopModelDeployment,
      unload: unloadModelDeployment
    };
    startTransition(() => {
      void actionMap[action](deployment.id)
        .then(() => Promise.all([getModelDeployments(), getMyDeployments()]))
        .then(([updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
          setDeploymentFeedback({
            tone: "success",
            text: `${deployment.name} 已提交${actionLabels[action]}。`
          });
        })
        .catch((error: unknown) => {
          setDeploymentFeedback({
            tone: "error",
            text:
              error instanceof Error
                ? error.message
                : `${deployment.name} ${actionLabels[action]}失败。`
          });
        });
    });
  }

  function refreshMachines() {
    startMachineTransition(() => {
      void getInferenceMachines()
        .then(setMachines)
        .catch((error: unknown) => {
          setMachineFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "刷新推理机器失败。"
          });
        });
    });
  }

  function updateMachineForm(key: keyof typeof machineForm, value: string) {
    setMachineForm((current) => ({ ...current, [key]: value }));
  }

  function submitMachine() {
    setMachineFeedback(null);
    startMachineTransition(() => {
      void (async () => {
        const tensorParallelSize = parseRequiredNumber(
          machineForm.tensor_parallel_size,
          "Tensor Parallel Size"
        );
        const gpuMemoryUtilization = parseRequiredNumber(
          machineForm.gpu_memory_utilization,
          "GPU Memory Utilization"
        );
        const listenPort = parseRequiredNumber(machineForm.listen_port, "Listen Port");
        const maxModelLen = machineForm.max_model_len.trim()
          ? parseRequiredNumber(machineForm.max_model_len, "Max Model Len")
          : null;
        const created = await createInferenceMachine({
          agent_base_url: machineForm.agent_base_url.trim(),
          agent_token: machineForm.agent_token.trim(),
          description: machineForm.description.trim() || null,
          dtype: machineForm.dtype,
          gpu_memory_utilization: gpuMemoryUtilization,
          listen_port: listenPort,
          max_model_len: maxModelLen,
          name: machineForm.name.trim(),
          runtime_api_key: machineForm.runtime_api_key.trim(),
          runtime_public_host: machineForm.runtime_public_host.trim() || null,
          tensor_parallel_size: tensorParallelSize,
          vllm_image: machineForm.vllm_image.trim()
        });
        let nextMachine = created;
        try {
          const health = await checkInferenceMachineHealth(created.id);
          nextMachine = applyMachineHealth(created, health);
        } catch {
          nextMachine = created;
        }
        setMachines((current) => [nextMachine, ...current]);
        setMachineForm(createInitialMachineForm());
        setIsMachineDialogOpen(false);
        setMachineFeedback({ tone: "success", text: `${nextMachine.name} 已添加。` });
      })().catch((error: unknown) => {
        setMachineFeedback({
          tone: "error",
          text: error instanceof Error ? error.message : "新增推理机器失败。"
        });
      });
    });
  }

  function checkMachine(machine: InferenceMachineSummary) {
    setMachineFeedback(null);
    startMachineTransition(() => {
      void checkInferenceMachineHealth(machine.id)
        .then((health) => {
          setMachines((current) =>
            current.map((item) =>
              item.id === machine.id ? applyMachineHealth(item, health) : item
            )
          );
          setMachineFeedback({
            tone: health.status === "ok" ? "success" : "error",
            text:
              health.status === "ok"
                ? `${machine.name} 连接正常。`
                : `${machine.name} 连接失败：${health.error ?? health.status}`
          });
        })
        .catch((error: unknown) => {
          setMachineFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "健康检查失败。"
          });
        });
    });
  }

  function removeMachine(machine: InferenceMachineSummary) {
    if (!window.confirm(`确认删除推理机器 ${machine.name}？`)) {
      return;
    }
    setMachineFeedback(null);
    startMachineTransition(() => {
      void deleteInferenceMachine(machine.id)
        .then(() => {
          setMachines((current) => current.filter((item) => item.id !== machine.id));
          setMachineFeedback({ tone: "success", text: `${machine.name} 已删除。` });
        })
        .catch((error: unknown) => {
          setMachineFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "删除推理机器失败。"
          });
        });
    });
  }

  return (
    <ConsolePage pageKey="endpoint" showScaffold={false}>
      <section className="mb-4 overflow-hidden rounded-lg border border-border bg-card/80">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-medium text-foreground">推理机器</div>
            <div className="mt-1 text-xs text-muted-foreground">
              已添加 {machines.length} 台部署了 infer-agent 的机器，部署模型时可选择目标机器。
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              disabled={isMachinePending}
              onClick={refreshMachines}
              size="sm"
              type="button"
              variant="outline"
            >
              <RefreshCw className={cn(isMachinePending ? "animate-spin" : "")} />
              刷新
            </Button>
            <Button
              disabled={isMachinePending}
              onClick={() => {
                setMachineForm(createInitialMachineForm());
                setMachineFeedback(null);
                setIsMachineAdvancedOpen(false);
                setIsMachineDialogOpen(true);
              }}
              size="sm"
              type="button"
            >
              <Plus />
              新增机器
            </Button>
          </div>
        </div>

        {machineFeedback ? (
          <div
            className={cn(
              "mx-4 mt-4 rounded-md border px-3 py-2 text-sm",
              machineFeedback.tone === "success"
                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-destructive/20 bg-destructive/10 text-destructive"
            )}
          >
            {machineFeedback.text}
          </div>
        ) : null}

        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {machines.length ? (
            machines.map((machine) => (
              <div
                className="rounded-lg border border-border bg-background/40 p-4"
                key={machine.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-foreground">
                      {machine.name}
                    </div>
                    <div className="mt-1 truncate font-mono text-xs text-muted-foreground">
                      {machine.agent_base_url}
                    </div>
                  </div>
                  <Badge variant={healthVariant(machine.last_health_status)}>
                    {machine.last_health_status ?? "未检查"}
                  </Badge>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  <MachineMetric icon={<Cpu />} label="GPU" value={formatGpuSummary(machine)} />
                  <MachineMetric
                    icon={<Activity />}
                    label="TP"
                    value={String(machine.tensor_parallel_size)}
                  />
                  <MachineMetric label="显存" value={formatGpuMemory(machine)} />
                  <MachineMetric label="port" value={String(machine.listen_port)} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{machine.vllm_image}</span>
                  {machine.has_agent_token ? (
                    <span className="inline-flex items-center gap-1">
                      <KeyRound className="size-3" />
                      Token
                    </span>
                  ) : null}
                  {machine.has_runtime_api_key ? (
                    <span className="inline-flex items-center gap-1">
                      <KeyRound className="size-3" />
                      Runtime
                    </span>
                  ) : null}
                  {machine.last_node_name ? <span>{machine.last_node_name}</span> : null}
                  {machine.last_gpu_count != null ? <span>{machine.last_gpu_count} GPU</span> : null}
                </div>
                {machine.last_health_error ? (
                  <div className="mt-3 line-clamp-2 text-xs text-destructive">
                    {machine.last_health_error}
                  </div>
                ) : null}
                <div className="mt-4 flex justify-end gap-2">
                  <Button
                    disabled={isMachinePending}
                    onClick={() => checkMachine(machine)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    健康检查
                  </Button>
                  <Button
                    className="text-destructive hover:text-destructive"
                    disabled={isMachinePending}
                    onClick={() => removeMachine(machine)}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    <Trash2 />
                    删除
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full rounded-lg border border-dashed border-border bg-background/40 px-4 py-10 text-center text-sm text-muted-foreground">
              还没有推理机器。先在 H20 机器上部署 infer-agent，然后把 Agent URL 和 Token 添加到这里。
            </div>
          )}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_420px]">
        <section className="overflow-hidden rounded-lg border border-border bg-card/80">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
            <div>
              <div className="text-sm font-medium text-foreground">部署任务</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {deployments.length} 个在线推理部署记录
              </div>
            </div>
            <Button
              disabled={!selectedTask || isPending}
              onClick={refreshSelected}
              size="sm"
              variant="outline"
            >
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
                  <TableHead className="h-10 px-3">机器</TableHead>
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
                      data-state={deployment.id === selectedTask?.id ? "selected" : undefined}
                      key={deployment.id}
                      onClick={() => setSelectedId(deployment.id)}
                    >
                      <TableCell className="px-3 py-2.5 font-medium text-foreground">
                        {deployment.name}
                      </TableCell>
                      <TableCell className="px-3 py-2.5 text-muted-foreground">
                        {deployment.served_model_name ?? deployment.model_name ?? "--"}
                      </TableCell>
                      <TableCell className="px-3 py-2.5 text-muted-foreground">
                        {deployment.machine_name ?? "--"}
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
                    <TableCell className="h-40 text-center text-muted-foreground" colSpan={6}>
                      暂无部署任务。从“我的模型”点击部署后会出现在这里。
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ConsoleListTableSurface>

          <div className="border-t border-border p-4">
            <div className="rounded-lg border border-border bg-background/40">
              <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Terminal />
                    部署事件
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">
                    {selectedTask?.name ?? "选择一个部署任务查看事件"}
                  </div>
                </div>
              </div>
              <ScrollArea className="h-[300px]">
                <div className="flex flex-col gap-3 p-3">
                  {events.length ? (
                    events.map((event) => (
                      <div
                        className="rounded-md border border-border bg-card/80 px-3 py-2"
                        key={event.id ?? event.created_at}
                      >
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
        </section>

        <section className="overflow-hidden rounded-lg border border-border bg-card/80">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Server />
                我的部署
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {myDeployments.length} 个可管理部署
              </div>
            </div>
            <Button disabled={isPending} onClick={refreshDeploymentLists} size="sm" variant="outline">
              <RefreshCw className={cn(isPending ? "animate-spin" : "")} />
              刷新
            </Button>
          </div>

          <div className="flex flex-col gap-3 p-4">
            {deploymentFeedback ? (
              <div
                className={cn(
                  "rounded-md border px-3 py-2 text-sm",
                  deploymentFeedback.tone === "success"
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                    : "border-destructive/20 bg-destructive/10 text-destructive"
                )}
              >
                {deploymentFeedback.text}
              </div>
            ) : null}

            {myDeployments.length ? (
              <ScrollArea className="max-h-[620px] pr-1">
                <div className="flex flex-col gap-3">
                  {myDeployments.map((deployment) => {
                    const phase = deployment.phase ?? deployment.status;
                    const canStop = isDeploymentRunning(deployment);
                    const canStart = isDeploymentStopped(deployment);
                    const isBusy = isDeploymentBusy(deployment);

                    return (
                      <div
                        className="rounded-lg border border-border bg-background/40 p-4"
                        key={deployment.id}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-foreground">
                              {deployment.served_model_name ?? deployment.model_name ?? deployment.name}
                            </div>
                            <div className="mt-1 truncate text-xs text-muted-foreground">
                              {deployment.machine_name ?? "--"} · generation {deployment.generation}
                            </div>
                          </div>
                          <Badge variant={phaseVariant(phase)}>{formatPhase(phase)}</Badge>
                        </div>

                        <div className="mt-3 grid gap-2 text-sm">
                          <InfoRow label="任务" value={deployment.name} />
                          <InfoRow label="Agent" value={deployment.agent_base_url ?? "--"} />
                          <InfoRow label="最近事件" value={deployment.last_event ?? "--"} />
                          <InfoRow
                            label="错误"
                            tone="danger"
                            value={deployment.error_message ?? "--"}
                          />
                        </div>

                        <div className="mt-4 flex items-center gap-2">
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

                        {deployment.endpoint_url ? (
                          <a
                            className="mt-3 inline-flex max-w-full items-center gap-2 truncate rounded-md border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
                            href={deployment.endpoint_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            <ExternalLink className="shrink-0" />
                            <span className="truncate">{deployment.endpoint_url}</span>
                          </a>
                        ) : null}

                        <div className="mt-4 flex flex-wrap justify-end gap-2">
                          <Button
                            disabled={isPending || !canStart || isBusy}
                            onClick={() => runDeploymentAction(deployment, "start")}
                            size="sm"
                            type="button"
                            variant="outline"
                          >
                            <Play />
                            启动
                          </Button>
                          <Button
                            disabled={isPending || !canStop || isBusy}
                            onClick={() => runDeploymentAction(deployment, "stop")}
                            size="sm"
                            type="button"
                            variant="outline"
                          >
                            <Square />
                            停止
                          </Button>
                          <Button
                            className="text-destructive hover:text-destructive"
                            disabled={isPending || isBusy}
                            onClick={() => runDeploymentAction(deployment, "unload")}
                            size="sm"
                            type="button"
                            variant="ghost"
                          >
                            <Trash2 />
                            卸载
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-background/40 px-4 py-10 text-center text-sm text-muted-foreground">
                暂无可管理部署。模型完成部署后会出现在这里。
              </div>
            )}
          </div>
        </section>
      </div>

      <Dialog open={isMachineDialogOpen} onOpenChange={setIsMachineDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>新增推理机器</DialogTitle>
            <DialogDescription>
              添加已部署 infer-agent 的机器，控制面会通过 Agent URL 下发 vLLM 部署任务。
            </DialogDescription>
          </DialogHeader>
          <div className="flex max-h-[68vh] flex-col gap-5 overflow-y-auto pr-1">
            <div className="grid gap-4 md:grid-cols-2">
              <MachineFormField
                label="机器名称"
                onChange={(value) => updateMachineForm("name", value)}
                placeholder="h20-node-01"
                value={machineForm.name}
              />
              <MachineFormField
                label="Agent URL"
                onChange={(value) => updateMachineForm("agent_base_url", value)}
                placeholder="http://111.229.120.156:9000"
                value={machineForm.agent_base_url}
              />
              <MachineFormField
                label="Agent Token"
                onChange={(value) => updateMachineForm("agent_token", value)}
                placeholder="infer-agent 启动时配置的 token"
                type="password"
                value={machineForm.agent_token}
              />
              <MachineFormField
                label="Runtime API Key"
                onChange={(value) => updateMachineForm("runtime_api_key", value)}
                placeholder="下发给 vLLM 的 Bearer token"
                type="password"
                value={machineForm.runtime_api_key}
              />
              <MachineFormField
                label="Runtime Public Host"
                onChange={(value) => updateMachineForm("runtime_public_host", value)}
                placeholder="111.229.120.156"
                value={machineForm.runtime_public_host}
              />
              <div className="md:col-span-2">
                <MachineFormField
                  label="备注"
                  onChange={(value) => updateMachineForm("description", value)}
                  placeholder="机房、用途或管理员"
                  value={machineForm.description}
                />
              </div>
            </div>

            <Collapsible
              onOpenChange={setIsMachineAdvancedOpen}
              open={isMachineAdvancedOpen}
            >
              <CollapsibleTrigger asChild>
                <Button
                  className="w-full justify-between"
                  type="button"
                  variant="outline"
                >
                  <span className="inline-flex items-center gap-2">
                    <SlidersHorizontal className="size-4" />
                    高级配置
                  </span>
                  <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                    TP {machineForm.tensor_parallel_size} / {machineForm.dtype}
                    <ChevronDown
                      className={cn(
                        "size-4 transition-transform",
                        isMachineAdvancedOpen && "rotate-180"
                      )}
                    />
                  </span>
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-4 grid gap-4 rounded-lg border border-border bg-background/40 p-4 md:grid-cols-2">
                  <MachineFormField
                    label="vLLM Image"
                    onChange={(value) => updateMachineForm("vllm_image", value)}
                    placeholder="vllm/vllm-openai:latest"
                    value={machineForm.vllm_image}
                  />
                  <MachineFormField
                    label="Tensor Parallel Size"
                    onChange={(value) => updateMachineForm("tensor_parallel_size", value)}
                    placeholder="8"
                    type="number"
                    value={machineForm.tensor_parallel_size}
                  />
                  <div className="flex flex-col gap-2">
                    <Label>Dtype</Label>
                    <Select
                      onValueChange={(value) => updateMachineForm("dtype", value)}
                      value={machineForm.dtype}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="bfloat16">bfloat16</SelectItem>
                        <SelectItem value="float16">float16</SelectItem>
                        <SelectItem value="auto">auto</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <MachineFormField
                    label="GPU Memory Utilization"
                    onChange={(value) => updateMachineForm("gpu_memory_utilization", value)}
                    placeholder="0.85"
                    type="number"
                    value={machineForm.gpu_memory_utilization}
                  />
                  <MachineFormField
                    label="Listen Port"
                    onChange={(value) => updateMachineForm("listen_port", value)}
                    placeholder="8000"
                    type="number"
                    value={machineForm.listen_port}
                  />
                  <MachineFormField
                    label="Max Model Len"
                    onChange={(value) => updateMachineForm("max_model_len", value)}
                    placeholder="留空使用模型默认"
                    type="number"
                    value={machineForm.max_model_len}
                  />
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
          <DialogFooter>
            <Button
              disabled={isMachinePending}
              onClick={() => setIsMachineDialogOpen(false)}
              type="button"
              variant="outline"
            >
              取消
            </Button>
            <Button disabled={isMachinePending} onClick={submitMachine} type="button">
              {isMachinePending ? "添加中..." : "添加机器"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsolePage>
  );
}

function MachineMetric({
  icon,
  label,
  value
}: {
  icon?: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-card/60 px-2 py-1.5">
      <div className="flex items-center gap-1 text-muted-foreground">
        {icon ? <span className="[&>svg]:size-3">{icon}</span> : null}
        {label}
      </div>
      <div className="mt-0.5 truncate font-mono text-foreground">{value}</div>
    </div>
  );
}

function MachineFormField({
  label,
  value,
  onChange,
  placeholder,
  type = "text"
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label>{label}</Label>
      <Input
        autoComplete={type === "password" ? "off" : undefined}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
    </div>
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
