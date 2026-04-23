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
  PowerOff,
  RefreshCw,
  Server,
  SlidersHorizontal,
  Square,
  Terminal,
  Trash2
} from "lucide-react";
import { toast } from "sonner";
import { ConsolePage } from "@/components/console/console-page";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
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
  checkModelDeploymentPassiveHealth,
  createInferenceMachine,
  deleteInferenceMachine,
  deleteModelDeploymentTask,
  getMyDeployments,
  getModelDeployments,
  getModelDeploymentEvents,
  getInferenceMachines,
  refreshModelDeployment,
  startModelDeployment,
  stopModelDeployment,
  unloadModelDeployment
} from "@/features/model-deployments/api";
import { ApiRequestError } from "@/lib/api-client/http";
import { cn } from "@/lib/utils";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    failed: "失败部署",
    completed_with_warnings: "已完成，有警告",
    pending: "等待中",
    ready: "可用",
    running: "执行中",
    smoke_testing: "测试中",
    starting: "启动中",
    stopping: "停止中",
    stopped: "已停止",
    stopping_previous: "切换中",
    succeeded: "成功部署",
    superseded: "已替换",
    unloaded: "已卸载",
    unloading: "卸载中",
    warming: "预热中"
  };
  return labels[value ?? ""] ?? value ?? "--";
}

function phaseVariant(value?: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (value === "ready" || value === "active" || value === "succeeded") {
    return "default";
  }
  if (value === "error" || value === "failed") {
    return "destructive";
  }
  if (
    value === "completed_with_warnings" ||
    value === "stopped" ||
    value === "superseded" ||
    value === "unloaded"
  ) {
    return "secondary";
  }
  return "outline";
}

type MachineHealthState = "healthy" | "probing" | "unhealthy";

function machineHealthVariant(
  value: MachineHealthState
): "default" | "secondary" | "destructive" | "outline" {
  if (value === "unhealthy") {
    return "destructive";
  }
  return "outline";
}

function formatMachineHealthState(value: MachineHealthState) {
  const labels: Record<MachineHealthState, string> = {
    healthy: "健康",
    probing: "探测中",
    unhealthy: "不健康"
  };
  return labels[value];
}

function readMachineHealthState(
  machine: InferenceMachineSummary,
  probingMachineIds: Set<string>
): MachineHealthState {
  if (probingMachineIds.has(machine.id)) {
    return "probing";
  }
  return machine.last_health_status === "ok" ? "healthy" : "unhealthy";
}

function machineHealthDotClassName(value: MachineHealthState) {
  const tones: Record<MachineHealthState, string> = {
    healthy: "bg-emerald-500",
    probing: "bg-amber-400",
    unhealthy: "bg-destructive"
  };
  return tones[value];
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
    "unloading",
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

function isDeploymentNotFoundError(error: unknown) {
  return (
    error instanceof ApiRequestError &&
    error.status === 404 &&
    error.detail === "Deployment not found"
  );
}

type ConsoleTask = {
  id: string;
  kind: "deployment" | "unload";
  kindLabel: string;
  deployment: ModelDeploymentSummary;
  name: string;
  phase: string;
  progress: number;
  lastEvent: string | null;
  errorMessage: string | null;
  updatedAt: string;
};

const RUNNING_TASK_PHASES = new Set([
  "deploying",
  "downloading",
  "pending",
  "running",
  "smoke_testing",
  "starting",
  "stopping",
  "stopping_previous",
  "unloading",
  "warming"
]);

const STOPPABLE_DEPLOYMENT_TASK_PHASES = new Set([
  "deploying",
  "downloading",
  "pending",
  "running",
  "smoke_testing",
  "starting",
  "stopping_previous",
  "warming"
]);

function isTaskRunning(task: ConsoleTask) {
  return RUNNING_TASK_PHASES.has(task.phase);
}

function canStopDeploymentTask(task: ConsoleTask) {
  return task.kind === "deployment" && STOPPABLE_DEPLOYMENT_TASK_PHASES.has(task.phase);
}

function buildConsoleTasks(deployments: ModelDeploymentSummary[]): ConsoleTask[] {
  return deployments.flatMap((deployment) => {
    const deletedTaskKinds = new Set(deployment.deleted_task_kinds ?? []);
    const deploymentTask: ConsoleTask = {
      id: `${deployment.id}:deployment`,
      kind: "deployment",
      kindLabel: "部署",
      deployment,
      name: deployment.name,
      phase: deployment.phase ?? deployment.status,
      progress: deployment.progress,
      lastEvent: deployment.last_event ?? null,
      errorMessage: deployment.error_message ?? null,
      updatedAt: deployment.updated_at
    };
    const tasks: ConsoleTask[] = [];
    if (!deletedTaskKinds.has("deployment")) {
      tasks.push(deploymentTask);
    }
    if (!deployment.unload_task_status || deletedTaskKinds.has("unload")) {
      return tasks;
    }
    tasks.push({
      id: `${deployment.id}:unload`,
      kind: "unload",
      kindLabel: "卸载",
      deployment,
      name: `${deployment.name} 卸载节点`,
      phase: deployment.unload_task_status,
      progress: deployment.unload_task_finished_at ? 100 : 20,
      lastEvent: deployment.unload_task_message ?? deployment.last_event ?? null,
      errorMessage: deployment.unload_task_warning ?? null,
      updatedAt: deployment.unload_task_finished_at ?? deployment.updated_at
    });
    return tasks;
  });
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
    selectedDeploymentId
      ? `${selectedDeploymentId}:deployment`
      : initialDeployments[0]
        ? `${initialDeployments[0].id}:deployment`
        : null
  );
  const [isPending, startTransition] = useTransition();
  const [isMachinePending, startMachineTransition] = useTransition();
  const [isMachineDialogOpen, setIsMachineDialogOpen] = useState(false);
  const [isMachineAdvancedOpen, setIsMachineAdvancedOpen] = useState(false);
  const [isTaskDetailOpen, setIsTaskDetailOpen] = useState(false);
  const [probingMachineIds, setProbingMachineIds] = useState<Set<string>>(() => new Set());
  const [machineForm, setMachineForm] = useState(createInitialMachineForm);
  const [pendingUnloadDeployment, setPendingUnloadDeployment] =
    useState<ModelDeploymentSummary | null>(null);
  const [pendingDeleteTask, setPendingDeleteTask] = useState<ConsoleTask | null>(null);
  const [pendingDeleteMachine, setPendingDeleteMachine] =
    useState<InferenceMachineSummary | null>(null);
  const consoleTasks = useMemo(() => buildConsoleTasks(deployments), [deployments]);
  const selectedTask = useMemo(
    () => consoleTasks.find((task) => task.id === selectedId) ?? consoleTasks[0] ?? null,
    [consoleTasks, selectedId]
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
    if (!selectedTask?.deployment.id) {
      setEvents([]);
      return;
    }
    void getModelDeploymentEvents(selectedTask.deployment.id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [selectedTask?.deployment.id]);

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
        if (selectedTask?.deployment.id) {
          void getModelDeploymentEvents(selectedTask.deployment.id)
            .then(setEvents)
            .catch(() => setEvents([]));
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
  }, [pollingDeploymentIds, selectedTask?.deployment.id]);

  function refreshSelected() {
    if (!selectedTask?.deployment.id) {
      return;
    }
    const task = selectedTask;
    startTransition(() => {
      void refreshModelDeployment(task.deployment.id)
        .then(() => Promise.all([getModelDeployments(), getMyDeployments()]))
        .then(([updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
          void getModelDeploymentEvents(task.deployment.id)
            .then(setEvents)
            .catch(() => setEvents([]));
        })
        .catch((error: unknown) => {
          if (isDeploymentNotFoundError(error)) {
            setDeployments((current) =>
              current.filter((deployment) => deployment.id !== task.deployment.id)
            );
            setMyDeployments((current) =>
              current.filter((deployment) => deployment.id !== task.deployment.id)
            );
            setEvents([]);
            setSelectedId((current) => (current === task.id ? null : current));
            toast.success("这个任务对应的部署已被清理，已从当前视图移除。");
            return;
          }
          toast.error(error instanceof Error ? error.message : "刷新任务失败。");
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
          toast.error(error instanceof Error ? error.message : "刷新部署列表失败。");
        });
    });
  }

  function openTaskDetails(task: ConsoleTask) {
    setSelectedId(task.id);
    setIsTaskDetailOpen(true);
  }

  function removeTask(task: ConsoleTask) {
    if (isTaskRunning(task)) {
      toast.error("进行中的任务不能删除。");
      return;
    }
    startTransition(() => {
      void deleteModelDeploymentTask(task.deployment.id, task.kind)
        .then(() => Promise.all([getModelDeployments(), getMyDeployments()]))
        .then(([updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
          setSelectedId((current) => (current === task.id ? null : current));
          setEvents((current) => (selectedTask?.id === task.id ? [] : current));
          if (selectedTask?.id === task.id) {
            setIsTaskDetailOpen(false);
          }
          toast.success(`${task.name} 已从任务列表删除。`);
        })
        .catch((error: unknown) => {
          if (isDeploymentNotFoundError(error)) {
            setDeployments((current) =>
              current.filter((deployment) => deployment.id !== task.deployment.id)
            );
            setMyDeployments((current) =>
              current.filter((deployment) => deployment.id !== task.deployment.id)
            );
            setSelectedId((current) => (current === task.id ? null : current));
            setEvents([]);
            setIsTaskDetailOpen(false);
            toast.success("这个任务对应的部署已被清理，已从当前视图移除。");
            return;
          }
          toast.error(error instanceof Error ? error.message : "删除任务失败。");
        });
    });
  }

  function runDeploymentAction(
    deployment: ModelDeploymentSummary,
    action: "start" | "stop" | "unload"
  ) {
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
        .then((result) => Promise.all([result, getModelDeployments(), getMyDeployments()]))
        .then(([result, updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(
            action === "unload"
              ? updatedMyDeployments.filter((item) => item.id !== deployment.id)
              : updatedMyDeployments
          );
          if (action === "unload") {
            setSelectedId(`${deployment.id}:unload`);
            const message = `${deployment.name} ${
              result.last_event ?? "已卸载"
            }；任务记录保留。`;
            if (result.error_message) {
              toast.warning(message);
            } else {
              toast.success(message);
            }
            return;
          }
          toast.success(
            `${deployment.name} 已提交${actionLabels[action]}。`
          );
        })
        .catch((error: unknown) => {
          const message = error instanceof Error ? error.message : "";
          if (
            action === "unload" &&
            isDeploymentNotFoundError(error)
          ) {
            setDeployments((current) => current.filter((item) => item.id !== deployment.id));
            setMyDeployments((current) => current.filter((item) => item.id !== deployment.id));
            toast.success(`${deployment.name} 是历史残留节点，已从当前列表移除。`);
            return;
          }
          toast.error(message || `${deployment.name} ${actionLabels[action]}失败。`);
        });
    });
  }

  function requestUnloadDeployment(deployment: ModelDeploymentSummary) {
    setPendingUnloadDeployment(deployment);
  }

  function runPassiveHealthCheck(deployment: ModelDeploymentSummary) {
    startTransition(() => {
      void checkModelDeploymentPassiveHealth(deployment.id)
        .then((result) => Promise.all([result, getModelDeployments(), getMyDeployments()]))
        .then(([result, updatedDeployments, updatedMyDeployments]) => {
          setDeployments(updatedDeployments);
          setMyDeployments(updatedMyDeployments);
          const message =
            result.status === "ok"
              ? `${deployment.name} 被动健康检查通过，耗时 ${result.latency_ms ?? "--"} ms。`
              : `${deployment.name} 被动健康检查失败：${result.error ?? result.status}`;
          if (result.status === "ok") {
            toast.success(message);
          } else {
            toast.error(message);
          }
        })
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : "被动健康检查失败。");
        });
    });
  }

  function refreshMachines() {
    startMachineTransition(() => {
      void getInferenceMachines()
        .then(setMachines)
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : "刷新推理机器失败。");
        });
    });
  }

  function updateMachineForm(key: keyof typeof machineForm, value: string) {
    setMachineForm((current) => ({ ...current, [key]: value }));
  }

  function submitMachine() {
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
        toast.success(`${nextMachine.name} 已添加。`);
      })().catch((error: unknown) => {
        toast.error(error instanceof Error ? error.message : "新增推理机器失败。");
      });
    });
  }

  function checkMachine(machine: InferenceMachineSummary) {
    setProbingMachineIds((current) => {
      const next = new Set(current);
      next.add(machine.id);
      return next;
    });
    startMachineTransition(() => {
      void checkInferenceMachineHealth(machine.id)
        .then((health) => {
          setMachines((current) =>
            current.map((item) =>
              item.id === machine.id ? applyMachineHealth(item, health) : item
            )
          );
          const message =
            health.status === "ok"
              ? `${machine.name} 连接正常。`
              : `${machine.name} 连接失败：${health.error ?? health.status}`;
          if (health.status === "ok") {
            toast.success(message);
          } else {
            toast.error(message);
          }
        })
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : "健康检查失败。");
        })
        .finally(() => {
          setProbingMachineIds((current) => {
            const next = new Set(current);
            next.delete(machine.id);
            return next;
          });
        });
    });
  }

  function removeMachine(machine: InferenceMachineSummary) {
    startMachineTransition(() => {
      void deleteInferenceMachine(machine.id)
        .then(() => {
          setMachines((current) => current.filter((item) => item.id !== machine.id));
          toast.success(`${machine.name} 已删除。`);
        })
        .catch((error: unknown) => {
          toast.error(error instanceof Error ? error.message : "删除推理机器失败。");
        });
    });
  }

  function requestDeleteMachine(machine: InferenceMachineSummary) {
    setPendingDeleteMachine(machine);
  }

  return (
    <ConsolePage pageKey="endpoint" showHeader={false} showScaffold={false}>
      <Tabs className="flex flex-col gap-4" defaultValue="my-deployments">
        <TabsList className="h-auto w-full justify-start gap-1 rounded-lg border border-border bg-card/80 p-1">
          <TabsTrigger value="my-deployments">我的部署</TabsTrigger>
          <TabsTrigger value="machines">推理机器</TabsTrigger>
          <TabsTrigger value="tasks">任务</TabsTrigger>
        </TabsList>

        <TabsContent value="my-deployments">
          <section className="overflow-hidden rounded-lg border border-border bg-card/80">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Server />
                  我的部署
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {myDeployments.length} 个可管理部署节点，节点状态独立于任务状态。
                </div>
              </div>
              <Button disabled={isPending} onClick={refreshDeploymentLists} size="sm" variant="outline">
                <RefreshCw className={cn(isPending ? "animate-spin" : "")} />
                刷新
              </Button>
            </div>

            <div className="p-4">
              {myDeployments.length ? (
                <div className="grid gap-3 lg:grid-cols-2">
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
                          <InfoRow label="来源任务" value={deployment.name} />
                          <InfoRow label="Agent" value={deployment.agent_base_url ?? "--"} />
                          <InfoRow label="最近事件" value={deployment.last_event ?? "--"} />
                          <InfoRow
                            label="被动检查"
                            tone={deployment.last_passive_health_status === "error" ? "danger" : undefined}
                            value={formatPassiveHealth(deployment)}
                          />
                          <InfoRow
                            label="错误"
                            tone="danger"
                            value={deployment.error_message ?? deployment.last_passive_health_error ?? "--"}
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
                            disabled={isPending || !canStop || isBusy}
                            onClick={() => runPassiveHealthCheck(deployment)}
                            size="sm"
                            type="button"
                            variant="outline"
                          >
                            <Activity />
                            被动检查
                          </Button>
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
                            onClick={() => requestUnloadDeployment(deployment)}
                            size="sm"
                            type="button"
                            variant="ghost"
                          >
                            <PowerOff />
                            卸载节点
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border bg-background/40 px-4 py-10 text-center text-sm text-muted-foreground">
                  暂无可管理部署。模型完成部署后会出现在这里。
                </div>
              )}
            </div>
          </section>
        </TabsContent>

        <TabsContent value="machines">
          <section className="overflow-hidden rounded-lg border border-border bg-card/80">
            <div className="flex justify-end border-b border-border px-4 py-3">
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

            <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
              {machines.length ? (
                machines.map((machine) => {
                  const healthState = readMachineHealthState(machine, probingMachineIds);
                  return (
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
                        <Badge
                          className="gap-1.5 px-3 py-1"
                          variant={machineHealthVariant(healthState)}
                        >
                          <span
                            className={cn(
                              "size-1.5 rounded-full",
                              machineHealthDotClassName(healthState)
                            )}
                          />
                          {formatMachineHealthState(healthState)}
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
                        {machine.last_gpu_count != null ? (
                          <span>{machine.last_gpu_count} GPU</span>
                        ) : null}
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
                          {healthState === "probing" ? "探测中..." : "健康检查"}
                        </Button>
                        <Button
                          className="text-destructive hover:text-destructive"
                          disabled={isMachinePending}
                          onClick={() => requestDeleteMachine(machine)}
                          size="sm"
                          type="button"
                          variant="ghost"
                        >
                          <Trash2 />
                          删除
                        </Button>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="col-span-full rounded-lg border border-dashed border-border bg-background/40 px-4 py-10 text-center text-sm text-muted-foreground">
                  还没有推理机器。先在 H20 机器上部署 infer-agent，然后把 Agent URL 和 Token 添加到这里。
                </div>
              )}
            </div>
          </section>
        </TabsContent>

        <TabsContent value="tasks">
          <section className="overflow-hidden rounded-lg border border-border bg-card/80">
            <div className="flex justify-end border-b border-border px-4 py-3">
              <Button
                disabled={!selectedTask || isPending}
                onClick={refreshSelected}
                size="sm"
                variant="outline"
              >
                <RefreshCw className={cn(isPending ? "animate-spin" : "")} />
                刷新任务
              </Button>
            </div>

            <ConsoleListTableSurface>
              <Table className="text-sm">
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="h-10 px-3">任务名称</TableHead>
                    <TableHead className="h-10 px-3">类型</TableHead>
                    <TableHead className="h-10 px-3">模型</TableHead>
                    <TableHead className="h-10 px-3">机器</TableHead>
                    <TableHead className="h-10 px-3">任务状态</TableHead>
                    <TableHead className="h-10 px-3">进度</TableHead>
                    <TableHead className="h-10 px-3">更新时间</TableHead>
                    <TableHead className="h-10 px-3 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {consoleTasks.length ? (
                    consoleTasks.map((task) => (
                      <TableRow
                        className="cursor-pointer"
                        data-state={task.id === selectedTask?.id ? "selected" : undefined}
                        key={task.id}
                        onClick={() => openTaskDetails(task)}
                      >
                        <TableCell className="px-3 py-2.5 font-medium text-foreground">
                          {task.name}
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <Badge variant="outline">{task.kindLabel}</Badge>
                        </TableCell>
                        <TableCell className="px-3 py-2.5 text-muted-foreground">
                          {task.deployment.served_model_name ?? task.deployment.model_name ?? "--"}
                        </TableCell>
                        <TableCell className="px-3 py-2.5 text-muted-foreground">
                          {task.deployment.machine_name ?? "--"}
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <Badge variant={phaseVariant(task.phase)}>
                            {formatPhase(task.phase)}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <div className="flex min-w-[120px] items-center gap-2">
                            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{ width: `${task.progress}%` }}
                              />
                            </div>
                            <span className="w-9 text-right text-xs text-muted-foreground">
                              {task.progress}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="px-3 py-2.5 text-muted-foreground">
                          {formatDateTime(task.updatedAt)}
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <div className="flex justify-end gap-2">
                            <Button
                              onClick={(event) => {
                                event.stopPropagation();
                                openTaskDetails(task);
                              }}
                              size="sm"
                              type="button"
                              variant="outline"
                            >
                              <Terminal />
                              查看
                            </Button>
                            {task.kind === "deployment" ? (
                              <Button
                                disabled={isPending || !canStopDeploymentTask(task)}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  runDeploymentAction(task.deployment, "stop");
                                }}
                                size="sm"
                                type="button"
                                variant="outline"
                              >
                                <Square />
                                停止
                              </Button>
                            ) : null}
                            <Button
                              className="text-destructive hover:text-destructive"
                              disabled={isPending || isTaskRunning(task)}
                              onClick={(event) => {
                                event.stopPropagation();
                                setPendingDeleteTask(task);
                              }}
                              size="sm"
                              type="button"
                              variant="ghost"
                            >
                              <Trash2 />
                              删除
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell className="h-40 text-center text-muted-foreground" colSpan={8}>
                        暂无任务。从“我的模型”点击部署，或在“我的部署”卸载节点后会出现在这里。
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </ConsoleListTableSurface>
          </section>
        </TabsContent>
      </Tabs>

      <Dialog open={isTaskDetailOpen && Boolean(selectedTask)} onOpenChange={setIsTaskDetailOpen}>
        <DialogContent className="max-w-3xl">
          {selectedTask ? (
            <>
              <DialogHeader>
                <DialogTitle>{selectedTask.name}</DialogTitle>
                <DialogDescription>
                  {selectedTask.kindLabel} · {formatPhase(selectedTask.phase)}
                </DialogDescription>
              </DialogHeader>

              <div className="flex max-h-[68vh] flex-col gap-4 overflow-y-auto pr-1">
                <div className="grid gap-2 text-sm">
                  <InfoRow label="类型" value={selectedTask.kindLabel} />
                  <InfoRow label="状态" value={formatPhase(selectedTask.phase)} />
                  <InfoRow
                    label="模型"
                    value={
                      selectedTask.deployment.served_model_name ??
                      selectedTask.deployment.model_name ??
                      "--"
                    }
                  />
                  <InfoRow label="机器" value={selectedTask.deployment.machine_name ?? "--"} />
                  <InfoRow label="最近事件" value={selectedTask.lastEvent ?? "--"} />
                  <InfoRow label="错误" tone="danger" value={selectedTask.errorMessage ?? "--"} />
                </div>

                <div className="rounded-lg border border-border bg-background/40">
                  <div className="border-b border-border px-3 py-2 text-sm font-medium text-foreground">
                    任务事件
                  </div>
                  <ScrollArea className="h-[360px]">
                    <div className="flex flex-col gap-3 p-3">
                      {selectedTask.kind === "unload" ? (
                        <div className="rounded-md border border-border bg-card/80 px-3 py-2">
                          <div className="flex items-start justify-between gap-3">
                            <div className="text-sm text-foreground">
                              {selectedTask.lastEvent ?? "卸载任务已记录"}
                            </div>
                            <Badge variant={selectedTask.errorMessage ? "secondary" : "outline"}>
                              unload
                            </Badge>
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {formatDateTime(selectedTask.updatedAt)}
                            {selectedTask.errorMessage ? ` · ${selectedTask.errorMessage}` : ""}
                          </div>
                        </div>
                      ) : null}
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
                          暂无事件，刷新任务后再试。
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </div>

              <DialogFooter>
                <Button
                  disabled={isPending}
                  onClick={refreshSelected}
                  type="button"
                  variant="outline"
                >
                  <RefreshCw className={cn(isPending ? "animate-spin" : "")} />
                  刷新
                </Button>
                {selectedTask?.kind === "deployment" ? (
                  <Button
                    disabled={isPending || !canStopDeploymentTask(selectedTask)}
                    onClick={() => runDeploymentAction(selectedTask.deployment, "stop")}
                    type="button"
                    variant="outline"
                  >
                    <Square />
                    停止部署
                  </Button>
                ) : null}
                <Button onClick={() => setIsTaskDetailOpen(false)} type="button">
                  关闭
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteTask(null);
          }
        }}
        open={Boolean(pendingDeleteTask)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除任务</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDeleteTask?.name ?? "这个任务"} 会从任务列表移除，部署节点和历史事件会保留。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isPending || !pendingDeleteTask || isTaskRunning(pendingDeleteTask)}
              onClick={() => {
                if (!pendingDeleteTask) {
                  return;
                }
                removeTask(pendingDeleteTask);
                setPendingDeleteTask(null);
              }}
            >
              删除任务
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setPendingUnloadDeployment(null);
          }
        }}
        open={Boolean(pendingUnloadDeployment)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>卸载部署节点</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingUnloadDeployment?.name ?? "这个部署"} 会从“我的部署”节点列表移除，并尝试停止对应
              infer-agent 运行实例；相关任务记录会保留在“任务”里用于追踪。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isPending || !pendingUnloadDeployment}
              onClick={() => {
                if (!pendingUnloadDeployment) {
                  return;
                }
                runDeploymentAction(pendingUnloadDeployment, "unload");
                setPendingUnloadDeployment(null);
              }}
            >
              卸载节点
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteMachine(null);
          }
        }}
        open={Boolean(pendingDeleteMachine)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除推理机器</AlertDialogTitle>
            <AlertDialogDescription>
              将从控制面移除 {pendingDeleteMachine?.name ?? "这台机器"} 的 Agent 配置。正在运行的远端
              infer-agent 进程不会被自动停止。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMachinePending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isMachinePending || !pendingDeleteMachine}
              onClick={() => {
                if (!pendingDeleteMachine) {
                  return;
                }
                removeMachine(pendingDeleteMachine);
                setPendingDeleteMachine(null);
              }}
            >
              删除机器
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={isMachineDialogOpen} onOpenChange={setIsMachineDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>新增推理机器</DialogTitle>
            <DialogDescription>
              添加已部署 infer-agent 的机器，控制面会通过 Agent URL 下发 vLLM 运行请求。
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

function formatPassiveHealth(deployment: ModelDeploymentSummary) {
  if (!deployment.last_passive_health_status) {
    return "未检查";
  }
  const checkedAt = formatDateTime(deployment.last_passive_health_checked_at);
  if (deployment.last_passive_health_status === "ok") {
    const latency = deployment.last_passive_health_latency_ms;
    return `通过 · ${latency ?? "--"} ms · ${checkedAt}`;
  }
  return `失败 · ${checkedAt}`;
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
