"use client";

import { useDeferredValue, useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  FileSearch,
  FolderOpen,
  Globe2,
  HardDrive,
  Loader2,
  RefreshCw,
  Rocket,
  Search,
  Trash2,
  UploadCloud
} from "lucide-react";
import { toast } from "sonner";
import {
  consoleListSearchInputClassName,
  ConsoleListTableSurface,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { S3BrowserDialog } from "@/features/object-store/components/s3-browser-dialog";
import {
  checkInferenceMachineHealth,
  createDeploymentFromModel,
  getInferenceMachines
} from "@/features/model-deployments/api";
import {
  deleteRegistryModel,
  importRegistryModelFromHuggingFace,
  importRegistryModelFromObjectStorage,
  listHuggingFaceRevisions,
  refreshRegistryModelDeploymentHints,
  searchHuggingFaceModels
} from "@/features/model-registry/api";
import { cn } from "@/lib/utils";
import type {
  InferenceMachineSummary,
  RegistryModelHuggingFaceRevisionResult,
  RegistryModelHuggingFaceSearchResult,
  RegistryModelSummary
} from "@/types/api";

type PendingDelete = { id: string; name: string } | null;
type PendingDeploy = RegistryModelSummary | null;
type ImportSourceType = "object-storage" | "huggingface";
type ImportArtifactType = "full_model" | "lora_adapter";
type ModelListTab = "full_models" | "lora_adapters";

const MODEL_PAGE_SIZE = 12;
const MY_MODEL_SOURCES = new Set(["object-storage-import", "huggingface-import", "finetune"]);
const noAdapterValue = "__no_lora_adapter__";

function createInitialImportForm() {
  return {
    artifact_type: "full_model" as ImportArtifactType,
    base_model: "",
    name: "",
    repo_id: "",
    revision: "",
    source_type: "huggingface" as ImportSourceType,
    source_uri: ""
  };
}

function isMyModel(model: RegistryModelSummary) {
  return !model.is_provider_managed && MY_MODEL_SOURCES.has(model.source ?? "");
}

function isLoraAdapter(model: RegistryModelSummary) {
  return model.artifact_type === "lora_adapter";
}

function statusTone(status: string) {
  if (status === "active") {
    return "gap-1.5 px-3 py-1 shadow-sm";
  }
  if (status === "inactive") {
    return "gap-1.5 border-muted bg-muted px-3 py-1 text-muted-foreground";
  }
  return "gap-1.5 border-border bg-background px-3 py-1 text-foreground";
}

function statusVariant(status: string): "default" | "secondary" | "outline" {
  if (status === "active") {
    return "default";
  }
  if (status === "inactive") {
    return "secondary";
  }
  return "outline";
}

function statusDotTone(status: string) {
  if (status === "active") {
    return "bg-primary-foreground";
  }
  if (status === "inactive") {
    return "bg-muted-foreground";
  }
  return "bg-foreground";
}

function formatStatusLabel(status: string) {
  if (status === "active") {
    return "已启用";
  }
  if (status === "inactive") {
    return "已停用";
  }
  return status;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function formatModelSource(model: RegistryModelSummary) {
  if (model.source === "object-storage-import") {
    return "对象存储";
  }
  if (model.source === "huggingface-import") {
    return "Hugging Face";
  }
  if (model.source === "manual") {
    return "手动登记";
  }
  if (model.source === "finetune") {
    return "模型精调";
  }
  return model.source || "自定义";
}

function formatCount(value?: number | null) {
  if (value == null) {
    return null;
  }
  return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(value);
}

function repoDisplayName(repoId: string) {
  return repoId.split("/").filter(Boolean).at(-1) || repoId;
}

function isHuggingFaceRepoCandidate(value: string) {
  return /^[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(value.trim());
}

function formatRevisionKind(kind: RegistryModelHuggingFaceRevisionResult["kind"]) {
  if (kind === "branch") {
    return "branch";
  }
  if (kind === "tag") {
    return "tag";
  }
  return "convert";
}

function readMachineGpuString(machine: InferenceMachineSummary) {
  const firstGpu = machine.last_gpus[0];
  const gpuName =
    typeof firstGpu?.name === "string" && firstGpu.name.trim() ? firstGpu.name : "GPU";
  const gpuCount = machine.last_gpu_count ?? machine.last_gpus.length;
  if (!gpuCount) {
    return "GPU 未检查";
  }
  const memoryTotalMb =
    typeof firstGpu?.memory_total_mb === "number" ? firstGpu.memory_total_mb : null;
  const memoryText = memoryTotalMb == null ? "" : ` · ${Math.round(memoryTotalMb / 1024)} GB/卡`;
  return `${gpuCount} x ${gpuName}${memoryText}`;
}

function readMachineGpuCount(machine: InferenceMachineSummary | null) {
  if (!machine) {
    return null;
  }
  const detectedCount = machine.last_gpu_count ?? machine.last_gpus.length;
  if (detectedCount > 0) {
    return detectedCount;
  }
  return machine.gpu_ids.length > 0 ? machine.gpu_ids.length : null;
}

function readGpuNumber(gpu: Record<string, unknown>, key: string) {
  const value = gpu[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getSelectableGpus(machine: InferenceMachineSummary | null) {
  if (!machine) {
    return [];
  }
  const allowedIds = machine.gpu_ids.length ? new Set(machine.gpu_ids) : null;
  return machine.last_gpus
    .filter((gpu) => {
      const index = readGpuNumber(gpu, "index");
      return index != null && (allowedIds == null || allowedIds.has(index));
    })
    .sort((left, right) => {
      const leftIndex = readGpuNumber(left, "index") ?? 0;
      const rightIndex = readGpuNumber(right, "index") ?? 0;
      return leftIndex - rightIndex;
    });
}

function getDefaultGpuIds(machine: InferenceMachineSummary | null, tensorParallelSize: number) {
  if (!machine || tensorParallelSize <= 0) {
    return [];
  }
  const selectableGpus = getSelectableGpus(machine);
  if (!selectableGpus.length) {
    return machine.gpu_ids.slice(0, tensorParallelSize);
  }
  return [...selectableGpus]
    .sort((left, right) => {
      const leftMemoryUsed = readGpuNumber(left, "memory_used_mb") ?? Number.MAX_SAFE_INTEGER;
      const rightMemoryUsed = readGpuNumber(right, "memory_used_mb") ?? Number.MAX_SAFE_INTEGER;
      if (leftMemoryUsed !== rightMemoryUsed) {
        return leftMemoryUsed - rightMemoryUsed;
      }
      const leftUtil = readGpuNumber(left, "utilization_gpu_percent") ?? Number.MAX_SAFE_INTEGER;
      const rightUtil = readGpuNumber(right, "utilization_gpu_percent") ?? Number.MAX_SAFE_INTEGER;
      return leftUtil - rightUtil;
    })
    .slice(0, tensorParallelSize)
    .map((gpu) => readGpuNumber(gpu, "index"))
    .filter((index): index is number => index != null)
    .sort((left, right) => left - right);
}

function formatGpuCardUsage(gpu: Record<string, unknown>) {
  const memoryUsedMb = readGpuNumber(gpu, "memory_used_mb");
  const memoryTotalMb = readGpuNumber(gpu, "memory_total_mb");
  const utilization = readGpuNumber(gpu, "utilization_gpu_percent");
  const memoryText =
    memoryUsedMb == null || memoryTotalMb == null
      ? "显存 --"
      : `${Math.round(memoryUsedMb / 1024)} / ${Math.round(memoryTotalMb / 1024)} GB`;
  const utilizationText = utilization == null ? "占用 --" : `${utilization}%`;
  return `${memoryText} · ${utilizationText}`;
}

function getModelTensorParallelOptions(
  model: RegistryModelSummary | null,
  machine: InferenceMachineSummary | null
) {
  const rawOptions = model?.deployment_hints?.tensor_parallel_size_options ?? [];
  const normalized = Array.from(
    new Set(rawOptions.filter((value) => Number.isInteger(value) && value > 0))
  ).sort((left, right) => left - right);
  const gpuCount = readMachineGpuCount(machine);
  if (!gpuCount) {
    return normalized;
  }
  return normalized.filter((value) => value <= gpuCount);
}

function getDefaultTensorParallelSize(
  options: number[],
  machine: InferenceMachineSummary | null
) {
  if (options.length > 0) {
    if (machine && options.includes(machine.tensor_parallel_size)) {
      return machine.tensor_parallel_size;
    }
    if (options.includes(1)) {
      return 1;
    }
    return options[0];
  }
  return machine?.tensor_parallel_size ?? null;
}

function formatTensorParallelHint(model: RegistryModelSummary | null) {
  const hints = model?.deployment_hints;
  if (!hints?.num_attention_heads) {
    return "未读取到 config.json 中的 attention heads，使用机器默认 TP。";
  }
  const architecture = hints.architectures[0] ?? hints.model_type ?? "模型";
  const vocabText = hints.vocab_size ? ` · vocab ${hints.vocab_size}` : "";
  return `${architecture} · attention heads ${hints.num_attention_heads}${vocabText}`;
}

function shouldRefreshDeploymentHints(model: RegistryModelSummary) {
  const hasOptions = Boolean(model.deployment_hints?.tensor_parallel_size_options.length);
  return !hasOptions && Boolean(model.import_repo_id || model.import_source_type);
}

export function MyModelsConsole({ initialModels }: { initialModels: RegistryModelSummary[] }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [pendingDeploy, setPendingDeploy] = useState<PendingDeploy>(null);
  const [deployMachines, setDeployMachines] = useState<InferenceMachineSummary[]>([]);
  const [deployMachineId, setDeployMachineId] = useState("");
  const [deployModelId, setDeployModelId] = useState("");
  const [deployAdapterModelId, setDeployAdapterModelId] = useState(noAdapterValue);
  const [deployTensorParallelSize, setDeployTensorParallelSize] = useState("");
  const [deployGpuIds, setDeployGpuIds] = useState<number[]>([]);
  const [isDeployMachineLoading, setIsDeployMachineLoading] = useState(false);
  const [isDeployHintsLoading, setIsDeployHintsLoading] = useState(false);
  const [isDeployGpuRefreshing, setIsDeployGpuRefreshing] = useState(false);
  const [deployMachineError, setDeployMachineError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [modelPage, setModelPage] = useState(1);
  const [modelListTab, setModelListTab] = useState<ModelListTab>("full_models");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isBrowserOpen, setIsBrowserOpen] = useState(false);
  const [importForm, setImportForm] = useState(createInitialImportForm);
  const [isHfSearchOpen, setIsHfSearchOpen] = useState(false);
  const [hfSearchResults, setHfSearchResults] = useState<RegistryModelHuggingFaceSearchResult[]>(
    []
  );
  const [isHfSearching, setIsHfSearching] = useState(false);
  const [hfSearchError, setHfSearchError] = useState<string | null>(null);
  const [hfRevisionResults, setHfRevisionResults] = useState<
    RegistryModelHuggingFaceRevisionResult[]
  >([]);
  const [isHfRevisionsLoading, setIsHfRevisionsLoading] = useState(false);
  const [hfRevisionsError, setHfRevisionsError] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  const myModels = useMemo(() => initialModels.filter(isMyModel), [initialModels]);
  const fullModels = useMemo(() => myModels.filter((model) => !isLoraAdapter(model)), [myModels]);
  const loraAdapters = useMemo(() => myModels.filter(isLoraAdapter), [myModels]);
  const deployAdapterOptions = useMemo(
    () => loraAdapters.filter((model) => model.id !== pendingDeploy?.id),
    [loraAdapters, pendingDeploy]
  );
  const selectedDeployMachine = useMemo(
    () => deployMachines.find((machine) => machine.id === deployMachineId) ?? null,
    [deployMachineId, deployMachines]
  );
  const deployTensorParallelOptions = useMemo(
    () => getModelTensorParallelOptions(pendingDeploy, selectedDeployMachine),
    [pendingDeploy, selectedDeployMachine]
  );
  const hasDeployTensorParallelHints = Boolean(
    pendingDeploy?.deployment_hints?.tensor_parallel_size_options.length
  );
  const deployTensorParallelFallback = useMemo(
    () =>
      hasDeployTensorParallelHints && deployTensorParallelOptions.length === 0
        ? null
        : getDefaultTensorParallelSize(deployTensorParallelOptions, selectedDeployMachine),
    [deployTensorParallelOptions, hasDeployTensorParallelHints, selectedDeployMachine]
  );
  const deployTensorParallelSelectOptions = useMemo(
    () =>
      deployTensorParallelOptions.length > 0
        ? deployTensorParallelOptions
        : deployTensorParallelFallback != null
          ? [deployTensorParallelFallback]
          : [],
    [deployTensorParallelFallback, deployTensorParallelOptions]
  );
  const deploySelectableGpus = useMemo(
    () => getSelectableGpus(selectedDeployMachine),
    [selectedDeployMachine]
  );

  const filteredModels = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    const tabModels = modelListTab === "lora_adapters" ? loraAdapters : fullModels;
    if (!normalizedQuery) {
      return tabModels;
    }

    return tabModels.filter((model) =>
      [model.name, model.base_model, model.source, model.import_repo_id]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedQuery))
    );
  }, [deferredQuery, fullModels, loraAdapters, modelListTab]);

  const totalModelPages = Math.max(1, Math.ceil(filteredModels.length / MODEL_PAGE_SIZE));
  const currentModelPage = Math.min(modelPage, totalModelPages);
  const pagedModels = useMemo(() => {
    const startIndex = (currentModelPage - 1) * MODEL_PAGE_SIZE;
    return filteredModels.slice(startIndex, startIndex + MODEL_PAGE_SIZE);
  }, [currentModelPage, filteredModels]);

  useEffect(() => {
    setModelPage(1);
  }, [deferredQuery, modelListTab]);

  useEffect(() => {
    if (!pendingDeploy || !selectedDeployMachine) {
      return;
    }
    if (deployTensorParallelFallback == null) {
      setDeployTensorParallelSize("");
      return;
    }
    const fallbackValue = String(deployTensorParallelFallback);
    const allowedValues = deployTensorParallelOptions.length
      ? deployTensorParallelOptions.map(String)
      : [fallbackValue];
    setDeployTensorParallelSize((current) => {
      if (current && allowedValues.includes(current)) {
        return current;
      }
      return fallbackValue;
    });
  }, [
    deployTensorParallelFallback,
    deployTensorParallelOptions,
    pendingDeploy,
    selectedDeployMachine
  ]);

  useEffect(() => {
    if (!pendingDeploy || !selectedDeployMachine) {
      setDeployGpuIds([]);
      return;
    }
    const tensorParallelSize = Number.parseInt(deployTensorParallelSize, 10);
    if (!Number.isInteger(tensorParallelSize) || tensorParallelSize <= 0) {
      setDeployGpuIds([]);
      return;
    }
    const selectableIds = new Set(
      deploySelectableGpus
        .map((gpu) => readGpuNumber(gpu, "index"))
        .filter((index): index is number => index != null)
    );
    setDeployGpuIds((current) => {
      const stillAvailable = current.filter((gpuId) => selectableIds.has(gpuId));
      if (stillAvailable.length === tensorParallelSize) {
        return stillAvailable;
      }
      return getDefaultGpuIds(selectedDeployMachine, tensorParallelSize);
    });
  }, [
    deploySelectableGpus,
    deployTensorParallelSize,
    pendingDeploy,
    selectedDeployMachine
  ]);

  useEffect(() => {
    if (!isImportOpen || importForm.source_type !== "huggingface") {
      setHfSearchResults([]);
      setIsHfSearching(false);
      setHfSearchError(null);
      return;
    }

    const searchQuery = importForm.repo_id.trim();
    if (searchQuery.length < 2) {
      setHfSearchResults([]);
      setIsHfSearching(false);
      setHfSearchError(null);
      return;
    }

    let isStale = false;
    const timeoutId = window.setTimeout(() => {
      setIsHfSearching(true);
      setHfSearchError(null);
      void searchHuggingFaceModels(
        {
          limit: 12,
          query: searchQuery
        }
      )
        .then((results) => {
          if (!isStale) {
            setHfSearchResults(results);
          }
        })
        .catch((error: unknown) => {
          if (isStale) {
            return;
          }
          setHfSearchResults([]);
          setHfSearchError(error instanceof Error ? error.message : "搜索 Hugging Face 失败");
        })
        .finally(() => {
          if (!isStale) {
            setIsHfSearching(false);
          }
        });
    }, 320);

    return () => {
      isStale = true;
      window.clearTimeout(timeoutId);
    };
  }, [importForm.repo_id, importForm.source_type, isImportOpen]);

  useEffect(() => {
    if (!isImportOpen || importForm.source_type !== "huggingface") {
      setHfRevisionResults([]);
      setIsHfRevisionsLoading(false);
      setHfRevisionsError(null);
      return;
    }

    const repoId = importForm.repo_id.trim();
    if (!isHuggingFaceRepoCandidate(repoId)) {
      setHfRevisionResults([]);
      setIsHfRevisionsLoading(false);
      setHfRevisionsError(null);
      setImportForm((current) => (current.revision ? { ...current, revision: "" } : current));
      return;
    }

    let isStale = false;
    const timeoutId = window.setTimeout(() => {
      setIsHfRevisionsLoading(true);
      setHfRevisionsError(null);
      void listHuggingFaceRevisions({ repo_id: repoId })
        .then((results) => {
          if (isStale) {
            return;
          }
          setHfRevisionResults(results);
          setImportForm((current) => {
            if (current.repo_id.trim() !== repoId) {
              return current;
            }
            if (current.revision && results.some((revision) => revision.name === current.revision)) {
              return current;
            }
            const preferredRevision =
              results.find((revision) => revision.name === "main") ?? results[0];
            return { ...current, revision: preferredRevision?.name ?? "" };
          });
        })
        .catch((error: unknown) => {
          if (isStale) {
            return;
          }
          setHfRevisionResults([]);
          setImportForm((current) =>
            current.repo_id.trim() === repoId ? { ...current, revision: "" } : current
          );
          setHfRevisionsError(error instanceof Error ? error.message : "读取 Revision 失败");
        })
        .finally(() => {
          if (!isStale) {
            setIsHfRevisionsLoading(false);
          }
        });
    }, 320);

    return () => {
      isStale = true;
      window.clearTimeout(timeoutId);
    };
  }, [importForm.repo_id, importForm.source_type, isImportOpen]);

  function updateImportField(key: keyof typeof importForm, value: string) {
    setImportForm((current) => ({
      ...current,
      [key]: value,
      ...(key === "repo_id" ? { revision: "" } : {})
    }));
    if (key === "repo_id") {
      setHfRevisionResults([]);
      setHfRevisionsError(null);
    }
  }

  function selectHuggingFaceModel(result: RegistryModelHuggingFaceSearchResult) {
    const displayName = repoDisplayName(result.repo_id);
    setImportForm((current) => ({
      ...current,
      base_model: current.base_model.trim() ? current.base_model : displayName,
      name: current.name.trim() ? current.name : displayName,
      repo_id: result.repo_id,
      revision: ""
    }));
    setIsHfSearchOpen(false);
  }

  function openImportSheet() {
    setImportForm(createInitialImportForm());
    setHfSearchError(null);
    setHfSearchResults([]);
    setHfRevisionResults([]);
    setHfRevisionsError(null);
    setIsHfSearchOpen(false);
    setIsImportOpen(true);
  }

  function closeImportSheet() {
    setIsImportOpen(false);
    setIsBrowserOpen(false);
    setIsHfSearchOpen(false);
    setHfRevisionResults([]);
    setHfRevisionsError(null);
  }

  function refreshWithMessage(tone: "success" | "error", text: string) {
    if (tone === "success") {
      toast.success(text);
    } else {
      toast.error(text);
    }
    router.refresh();
  }

  function runAction(action: () => Promise<void>) {
    startTransition(() => {
      void action().catch((error: unknown) => {
        toast.error(error instanceof Error ? error.message : "操作失败");
      });
    });
  }

  function submitImport() {
    if (!importForm.name.trim() || !importForm.base_model.trim()) {
      toast.error("请填写模型名称和基础模型。");
      return;
    }

    if (importForm.source_type === "object-storage" && !importForm.source_uri.trim()) {
      toast.error("请填写对象存储路径。");
      return;
    }

    if (importForm.source_type === "huggingface" && !importForm.repo_id.trim()) {
      toast.error("请填写 Hugging Face Repo ID。");
      return;
    }

    if (importForm.source_type === "huggingface" && !importForm.revision.trim()) {
      toast.error("请选择模型 Revision。");
      return;
    }

    runAction(async () => {
      if (importForm.source_type === "huggingface") {
        await importRegistryModelFromHuggingFace({
          artifact_type: importForm.artifact_type,
          base_model: importForm.base_model.trim(),
          name: importForm.name.trim(),
          repo_id: importForm.repo_id.trim(),
          revision: importForm.revision.trim()
        });
      } else {
        await importRegistryModelFromObjectStorage({
          artifact_type: importForm.artifact_type,
          base_model: importForm.base_model.trim(),
          name: importForm.name.trim(),
          source_uri: importForm.source_uri.trim()
        });
      }
      closeImportSheet();
      refreshWithMessage("success", `${importForm.name.trim()} 已导入到我的模型。`);
    });
  }

  function openDeployDialog(model: RegistryModelSummary) {
    setPendingDeploy(model);
    setDeployMachines([]);
    setDeployMachineId("");
    setDeployModelId(model.model_code ?? model.name);
    setDeployTensorParallelSize("");
    setDeployGpuIds([]);
    setDeployMachineError(null);
    setIsDeployMachineLoading(true);
    setIsDeployHintsLoading(false);
    void getInferenceMachines()
      .then((machines) => {
        const activeMachines = machines.filter((machine) => machine.status === "active");
        setDeployMachines(activeMachines);
        setDeployMachineId(activeMachines[0]?.id ?? "");
        if (activeMachines[0]?.id) {
          refreshDeployMachineHealth(activeMachines[0].id);
        }
      })
      .catch((error: unknown) => {
        setDeployMachineError(error instanceof Error ? error.message : "读取推理机器失败。");
      })
      .finally(() => {
        setIsDeployMachineLoading(false);
      });
    if (shouldRefreshDeploymentHints(model)) {
      setIsDeployHintsLoading(true);
      void refreshRegistryModelDeploymentHints(model.id)
        .then((updatedModel) => {
          setPendingDeploy((current) => (current?.id === updatedModel.id ? updatedModel : current));
        })
        .catch((error: unknown) => {
          setDeployMachineError(
            error instanceof Error ? error.message : "读取模型 config.json 失败。"
          );
        })
        .finally(() => {
          setIsDeployHintsLoading(false);
        });
    }
  }

  function refreshDeployMachineHealth(machineId = deployMachineId) {
    if (!machineId) {
      return;
    }
    setIsDeployGpuRefreshing(true);
    void checkInferenceMachineHealth(machineId)
      .then((health) => {
        setDeployMachines((current) =>
          current.map((machine) =>
            machine.id === machineId
              ? {
                  ...machine,
                  last_gpu_count: health.gpus.length,
                  last_gpus: health.gpus,
                  last_health_checked_at: health.checked_at,
                  last_health_error: health.error,
                  last_health_status: health.status,
                  last_node_name: health.node_name
                }
              : machine
          )
        );
      })
      .catch((error: unknown) => {
        setDeployMachineError(error instanceof Error ? error.message : "刷新 GPU 占用失败。");
      })
      .finally(() => {
        setIsDeployGpuRefreshing(false);
      });
  }

  function deployModel() {
    if (!pendingDeploy) {
      return;
    }
    if (!deployMachineId) {
      setDeployMachineError("请选择一台推理机器。");
      return;
    }
    if (!deployModelId.trim()) {
      setDeployMachineError("请填写 Model ID。");
      return;
    }
    const tensorParallelSize = Number.parseInt(deployTensorParallelSize, 10);
    if (!Number.isInteger(tensorParallelSize) || tensorParallelSize <= 0) {
      setDeployMachineError("请选择 Tensor Parallel Size。");
      return;
    }
    if (
      deployTensorParallelOptions.length > 0 &&
      !deployTensorParallelOptions.includes(tensorParallelSize)
    ) {
      setDeployMachineError("当前 Tensor Parallel Size 不在 config.json 支持的可选值中。");
      return;
    }
    if (deploySelectableGpus.length > 0 && deployGpuIds.length !== tensorParallelSize) {
      setDeployMachineError("请选择与 Tensor Parallel Size 数量一致的 GPU。");
      return;
    }

    const model = pendingDeploy;
    runAction(async () => {
      const deployment = await createDeploymentFromModel(model.id, {
        adapter_model_id:
          deployAdapterModelId === noAdapterValue ? undefined : deployAdapterModelId,
        gpu_ids: deployGpuIds.length > 0 ? deployGpuIds : undefined,
        machine_id: deployMachineId,
        name: `${model.name} 部署`,
        served_model_name: deployModelId.trim(),
        tensor_parallel_size: tensorParallelSize
      });
      setPendingDeploy(null);
      refreshWithMessage("success", `${model.name} 已提交部署任务。`);
      router.push(`/endpoint?deploymentId=${encodeURIComponent(deployment.id)}`);
    });
  }

  function confirmDelete() {
    if (!pendingDelete) {
      return;
    }

    runAction(async () => {
      await deleteRegistryModel(pendingDelete.id);
      refreshWithMessage("success", `模型 ${pendingDelete.name} 已删除。`);
      setPendingDelete(null);
    });
  }

  const modelRangeStart = filteredModels.length ? (currentModelPage - 1) * MODEL_PAGE_SIZE + 1 : 0;
  const modelRangeEnd = Math.min(currentModelPage * MODEL_PAGE_SIZE, filteredModels.length);

  return (
    <>
      <div className="flex flex-col gap-4">
        <ConsoleListToolbar className="gap-y-1 border-b-0 pb-0">
          <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
            <div className="relative w-full max-w-[540px] min-w-[260px] sm:min-w-[320px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className={cn(consoleListSearchInputClassName, "w-full")}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索模型名称或基础模型"
                type="search"
                value={query}
              />
            </div>
          </ConsoleListToolbarCluster>

          <Button onClick={openImportSheet} size="sm">
            <UploadCloud />
            导入模型
          </Button>
        </ConsoleListToolbar>

        <Tabs
          className="w-full"
          onValueChange={(value) => setModelListTab(value as ModelListTab)}
          value={modelListTab}
        >
          <TabsList>
            <TabsTrigger value="full_models">完整模型 ({fullModels.length})</TabsTrigger>
            <TabsTrigger value="lora_adapters">LoRA Adapter ({loraAdapters.length})</TabsTrigger>
          </TabsList>
        </Tabs>

        <ConsoleListTableSurface>
          <Table className="w-full table-fixed">
            <TableHeader className="bg-transparent">
              <TableRow className="hover:bg-transparent">
                <TableHead className={modelStickyHeadClassName}>模型名称</TableHead>
                <TableHead className="w-[220px] min-w-[220px]">基础模型</TableHead>
                <TableHead className="w-[148px] min-w-[148px]">来源</TableHead>
                <TableHead className="w-[128px] min-w-[128px]">状态</TableHead>
                <TableHead className="w-[132px] min-w-[132px]">创建时间</TableHead>
                <TableHead className="w-[156px] min-w-[156px]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagedModels.length ? (
                pagedModels.map((model) => (
                  <TableRow className="bg-transparent" key={model.id}>
                    <TableCell className={modelStickyCellClassName}>
                      <div className="min-w-0">
                        <div className="block truncate font-medium text-foreground">
                          {model.name}
                        </div>
                        <div className="mt-1 truncate text-xs text-muted-foreground">
                          {model.model_code ?? model.id}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="truncate font-mono text-xs">
                      {model.base_model ?? "--"}
                    </TableCell>
                    <TableCell className="text-sm">{formatModelSource(model)}</TableCell>
                    <TableCell>
                      <Badge
                        className={statusTone(model.status)}
                        variant={statusVariant(model.status)}
                      >
                        <span
                          className={cn("size-1.5 rounded-full", statusDotTone(model.status))}
                        />
                        {formatStatusLabel(model.status)}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatDateTime(model.created_at)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          disabled={isPending || isLoraAdapter(model)}
                          onClick={() => openDeployDialog(model)}
                          size="sm"
                          variant="outline"
                        >
                          <Rocket />
                          部署
                        </Button>
                        <Button
                          aria-label="删除模型"
                          className="h-7 w-7 px-0 text-destructive hover:text-destructive"
                          disabled={isPending}
                          onClick={() => setPendingDelete({ id: model.id, name: model.name })}
                          size="sm"
                          variant="ghost"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow className="bg-transparent hover:bg-transparent">
                  <TableCell className={modelStickyCellClassName} colSpan={6}>
                    <div className="flex min-h-[180px] flex-col items-center justify-center gap-3 py-10 text-center">
                      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card/80 text-muted-foreground">
                        <FileSearch className="h-5 w-5" />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-foreground">
                          {modelListTab === "lora_adapters" ? "暂无 LoRA Adapter" : "暂无模型"}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {modelListTab === "lora_adapters"
                            ? "请导入 Hugging Face LoRA adapter，或调整搜索词"
                            : "请调整搜索词，或导入一个自有模型"}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {filteredModels.length ? (
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="text-xs text-muted-foreground">
                {modelRangeStart}
                {" - "}
                {modelRangeEnd} of {filteredModels.length}
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  disabled={currentModelPage <= 1}
                  onClick={() => setModelPage((page) => Math.max(1, page - 1))}
                  size="sm"
                  variant="ghost"
                >
                  上一页
                </Button>
                <div className="min-w-[56px] text-center text-xs text-muted-foreground">
                  {currentModelPage} / {totalModelPages}
                </div>
                <Button
                  disabled={currentModelPage >= totalModelPages}
                  onClick={() => setModelPage((page) => Math.min(totalModelPages, page + 1))}
                  size="sm"
                  variant="ghost"
                >
                  下一页
                </Button>
              </div>
            </div>
          ) : null}
        </ConsoleListTableSurface>
      </div>

      <Sheet
        onOpenChange={(open) => {
          if (!open) {
            closeImportSheet();
          }
        }}
        open={isImportOpen}
      >
        <SheetContent className="w-full gap-0 overflow-hidden border-l border-border bg-card p-0 text-foreground shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-2xl [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-muted-foreground [&>button]:hover:bg-card/80 [&>button]:hover:text-foreground">
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b border-border bg-card px-6 py-5 pr-12">
              <SheetTitle className="text-foreground">导入模型</SheetTitle>
              <SheetDescription className="text-muted-foreground">
                从 Hugging Face 或 COS / S3 对象存储登记 safetensors checkpoint。
              </SheetDescription>
            </SheetHeader>

            <ScrollArea className="flex-1">
              <div className="flex flex-col gap-5 px-6 py-5">
                <div className="grid gap-4">
                  <FormField
                    label="模型名称"
                    onChange={(value) => updateImportField("name", value)}
                    placeholder="请输入"
                    value={importForm.name}
                  />
                  <FormField
                    label="基础模型"
                    onChange={(value) => updateImportField("base_model", value)}
                    placeholder="例如 Qwen2.5-7B-Instruct"
                    value={importForm.base_model}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <Label>登记类型</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <SourceTypeButton
                      active={importForm.artifact_type === "full_model"}
                      icon={<FileSearch className="size-4" />}
                      label="完整模型"
                      onClick={() => updateImportField("artifact_type", "full_model")}
                    />
                    <SourceTypeButton
                      active={importForm.artifact_type === "lora_adapter"}
                      icon={<UploadCloud className="size-4" />}
                      label="LoRA Adapter"
                      onClick={() => updateImportField("artifact_type", "lora_adapter")}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <Label>导入来源</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <SourceTypeButton
                      active={importForm.source_type === "huggingface"}
                      icon={<Globe2 className="size-4" />}
                      label="Hugging Face"
                      onClick={() => updateImportField("source_type", "huggingface")}
                    />
                    <SourceTypeButton
                      active={importForm.source_type === "object-storage"}
                      icon={<HardDrive className="size-4" />}
                      label="对象存储"
                      onClick={() => updateImportField("source_type", "object-storage")}
                    />
                  </div>
                </div>

                {importForm.source_type === "huggingface" ? (
                  <div className="grid gap-4">
                    <HuggingFaceRepoField
                      error={hfSearchError}
                      isLoading={isHfSearching}
                      isOpen={isHfSearchOpen}
                      onChange={(value) => updateImportField("repo_id", value)}
                      onFocus={() => setIsHfSearchOpen(true)}
                      onOpenChange={setIsHfSearchOpen}
                      onSelect={selectHuggingFaceModel}
                      placeholder="例如 Qwen/Qwen2.5-7B-Instruct"
                      results={hfSearchResults}
                      value={importForm.repo_id}
                    />
                    <HuggingFaceRevisionSelect
                      error={hfRevisionsError}
                      isLoading={isHfRevisionsLoading}
                      onChange={(value) => updateImportField("revision", value)}
                      repoId={importForm.repo_id}
                      revisions={hfRevisionResults}
                      value={importForm.revision}
                    />
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="model-import-source-uri">Bucket / 对象路径</Label>
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Input
                        className="font-mono text-xs"
                        id="model-import-source-uri"
                        onChange={(event) => updateImportField("source_uri", event.target.value)}
                        placeholder="s3://bucket/path/to/checkpoint/ 或 cos://bucket/path/to/checkpoint/"
                        value={importForm.source_uri}
                      />
                      <Button
                        className="shrink-0"
                        onClick={() => setIsBrowserOpen(true)}
                        type="button"
                        variant="outline"
                      >
                        <FolderOpen />
                        浏览
                      </Button>
                    </div>
                  </div>
                )}

                <div className="rounded-lg border border-border bg-background/40 px-4 py-3">
                  <div className="text-sm font-medium text-foreground">格式要求</div>
                  <div className="mt-1 text-sm leading-6 text-muted-foreground">
                    {importForm.artifact_type === "lora_adapter"
                      ? "LoRA adapter 会登记为可部署 adapter，部署时由 infer-agent 下载到推理机器并挂载给 vLLM。"
                      : importForm.source_type === "huggingface"
                        ? "录入时会使用系统配置中的 Hugging Face 凭据校验 repo、revision 和 safetensors 权重权限。"
                        : "必须选择 Checkpoint 所在路径。当前仅支持 safetensors 格式文件。"}
                  </div>
                  <pre className="mt-3 whitespace-pre-wrap rounded-md bg-card/80 px-3 py-2 font-mono text-xs leading-6 text-muted-foreground">
                    {importForm.artifact_type === "lora_adapter"
                      ? `|-- adapter_config.json
|-- adapter_model.safetensors`
                      : `|-- *.safetensors
|-- config.json
|-- ...`}
                  </pre>
                </div>
              </div>
            </ScrollArea>

            <SheetFooter className="border-t border-border px-6 py-4">
              <Button disabled={isPending} onClick={submitImport} type="button">
                {isPending ? "导入中..." : "确定"}
              </Button>
              <Button
                className="border-border text-foreground hover:border-border hover:bg-card/80"
                disabled={isPending}
                onClick={closeImportSheet}
                type="button"
                variant="outline"
              >
                取消
              </Button>
            </SheetFooter>
          </div>
        </SheetContent>
      </Sheet>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open) {
            setPendingDelete(null);
          }
        }}
        open={Boolean(pendingDelete)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除模型</AlertDialogTitle>
            <AlertDialogDescription>
              确认删除模型 {pendingDelete?.name ?? ""}？删除后将从我的模型列表移除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isPending}
              onClick={confirmDelete}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeploy(null);
            setDeployModelId("");
            setDeployAdapterModelId(noAdapterValue);
            setDeployTensorParallelSize("");
            setDeployGpuIds([]);
            setIsDeployHintsLoading(false);
            setIsDeployGpuRefreshing(false);
            setDeployMachineError(null);
          }
        }}
        open={Boolean(pendingDeploy)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>选择推理机器</DialogTitle>
            <DialogDescription>
              将 {pendingDeploy?.name ?? ""} 部署到已接入 infer-agent 的机器。
            </DialogDescription>
          </DialogHeader>

          {deployMachineError ? (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {deployMachineError}
            </div>
          ) : null}

          {isDeployMachineLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">正在读取推理机器...</div>
          ) : deployMachines.length ? (
            <div className="grid gap-4">
              <FormField
                label="Model ID"
                onChange={setDeployModelId}
                placeholder="例如 Qwen2.5-1.5B"
                value={deployModelId}
              />
              <div className="flex flex-col gap-2">
                <Label>LoRA SFT Adapter</Label>
                <Select onValueChange={setDeployAdapterModelId} value={deployAdapterModelId}>
                  <SelectTrigger>
                    <SelectValue placeholder="不使用 Adapter" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={noAdapterValue}>不使用 Adapter</SelectItem>
                    {deployAdapterOptions.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-xs leading-5 text-muted-foreground">
                  选择已导入的 LoRA adapter 后，vLLM 会以 base model 挂载该 adapter 启动。
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Tensor Parallel Size</Label>
                <Select
                  disabled={isDeployHintsLoading || deployTensorParallelSelectOptions.length === 0}
                  onValueChange={setDeployTensorParallelSize}
                  value={deployTensorParallelSize}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="请选择 TP" />
                  </SelectTrigger>
                  <SelectContent>
                    {deployTensorParallelSelectOptions.map((option) => (
                      <SelectItem key={option} value={String(option)}>
                        TP {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="text-xs leading-5 text-muted-foreground">
                  {isDeployHintsLoading
                    ? "正在读取模型 config.json..."
                    : formatTensorParallelHint(pendingDeploy)}
                  {deployTensorParallelOptions.length > 0 ? (
                    <>
                      {" "}
                      当前机器可用：{deployTensorParallelOptions.join(" / ")}。
                    </>
                  ) : null}
                  {hasDeployTensorParallelHints && deployTensorParallelOptions.length === 0 ? (
                    <> 当前机器 GPU 数不足或未检查，未找到兼容 TP。</>
                  ) : null}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Label>推理机器</Label>
                <Select
                  onValueChange={(value) => {
                    setDeployMachineId(value);
                    setDeployGpuIds([]);
                    setDeployMachineError(null);
                    refreshDeployMachineHealth(value);
                  }}
                  value={deployMachineId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="请选择" />
                  </SelectTrigger>
                  <SelectContent>
                    {deployMachines.map((machine) => (
                      <SelectItem key={machine.id} value={machine.id}>
                        {machine.name} · {readMachineGpuString(machine)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedDeployMachine ? (
                  <div className="rounded-md border border-border bg-background/40 px-3 py-2">
                    <div className="text-sm text-foreground">
                      {readMachineGpuString(selectedDeployMachine)}
                    </div>
                    <div className="mt-1 font-mono text-xs text-muted-foreground">
                      {selectedDeployMachine.agent_base_url}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      状态：{selectedDeployMachine.last_health_status ?? "未检查"} · TP{" "}
                      {selectedDeployMachine.tensor_parallel_size} · {selectedDeployMachine.dtype}
                    </div>
                  </div>
                ) : null}
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label>GPU</Label>
                  <Button
                    disabled={!deployMachineId || isDeployGpuRefreshing}
                    onClick={() => refreshDeployMachineHealth()}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    <RefreshCw className={cn(isDeployGpuRefreshing ? "animate-spin" : "")} />
                    刷新占用
                  </Button>
                </div>
                {deploySelectableGpus.length ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {deploySelectableGpus.map((gpu) => {
                      const gpuId = readGpuNumber(gpu, "index");
                      if (gpuId == null) {
                        return null;
                      }
                      const isSelected = deployGpuIds.includes(gpuId);
                      const gpuName =
                        typeof gpu.name === "string" && gpu.name.trim() ? gpu.name : "GPU";
                      return (
                        <button
                          className={cn(
                            "flex min-h-[72px] items-start gap-3 rounded-md border px-3 py-2 text-left transition-colors",
                            isSelected
                              ? "border-primary bg-primary/10 text-foreground"
                              : "border-border bg-background/40 text-foreground hover:bg-card/80"
                          )}
                          key={gpuId}
                          onClick={() => {
                            const tensorParallelSize = Number.parseInt(
                              deployTensorParallelSize,
                              10
                            );
                            setDeployGpuIds((current) => {
                              if (current.includes(gpuId)) {
                                return current.filter((item) => item !== gpuId);
                              }
                              const next = [...current, gpuId].sort((left, right) => left - right);
                              if (
                                Number.isInteger(tensorParallelSize) &&
                                tensorParallelSize > 0 &&
                                next.length > tensorParallelSize
                              ) {
                                return [...next.slice(1)];
                              }
                              return next;
                            });
                            setDeployMachineError(null);
                          }}
                          type="button"
                        >
                          <span
                            className={cn(
                              "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded border text-[11px] font-medium",
                              isSelected
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border text-muted-foreground"
                            )}
                          >
                            {isSelected ? "✓" : ""}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium">
                              GPU {gpuId} · {gpuName}
                            </span>
                            <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                              <Activity className="size-3.5" />
                              {formatGpuCardUsage(gpu)}
                            </span>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed border-border px-3 py-3 text-xs leading-5 text-muted-foreground">
                    暂无单卡占用数据。刷新机器状态后可按 GPU 选择；未选择时使用机器默认 GPU 配置。
                  </div>
                )}
                {deploySelectableGpus.length ? (
                  <div className="text-xs leading-5 text-muted-foreground">
                    已选择 GPU {deployGpuIds.length ? deployGpuIds.join(" / ") : "--"}，需与 TP{" "}
                    {deployTensorParallelSize || "--"} 数量一致。
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center">
              <div className="text-sm text-foreground">还没有可用的推理机器</div>
              <div className="mt-1 text-xs leading-6 text-muted-foreground">
                先在“我的部署”页面添加已部署 infer-agent 的 H20 机器。
              </div>
              <Button className="mt-4" onClick={() => router.push("/endpoint")} size="sm">
                去添加机器
              </Button>
            </div>
          )}

          <DialogFooter>
            <Button
              disabled={isPending}
              onClick={() => {
                setPendingDeploy(null);
                setDeployTensorParallelSize("");
                setIsDeployHintsLoading(false);
              }}
              type="button"
              variant="outline"
            >
              取消
            </Button>
            <Button
              disabled={
                isPending ||
                isDeployMachineLoading ||
                isDeployHintsLoading ||
                !deployMachines.length ||
                !deployTensorParallelSize ||
                (deploySelectableGpus.length > 0 &&
                  deployGpuIds.length !== Number.parseInt(deployTensorParallelSize, 10))
              }
              onClick={deployModel}
              type="button"
            >
              {isPending ? "提交中..." : "部署"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <S3BrowserDialog
        description="浏览当前项目的 COS / S3 对象存储，进入 Checkpoint 所在路径后确认。"
        initialUri={importForm.source_uri}
        onClose={() => setIsBrowserOpen(false)}
        onSelect={(uri) => updateImportField("source_uri", uri)}
        open={isBrowserOpen}
        selectionMode="prefix"
        title="选择 Checkpoint 路径"
      />
    </>
  );
}

function FormField({
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

function HuggingFaceRepoField({
  value,
  onChange,
  onSelect,
  onFocus,
  onOpenChange,
  isOpen,
  isLoading,
  error,
  results,
  placeholder
}: {
  value: string;
  onChange: (value: string) => void;
  onSelect: (result: RegistryModelHuggingFaceSearchResult) => void;
  onFocus: () => void;
  onOpenChange: (open: boolean) => void;
  isOpen: boolean;
  isLoading: boolean;
  error: string | null;
  results: RegistryModelHuggingFaceSearchResult[];
  placeholder: string;
}) {
  const showPanel = isOpen && value.trim().length >= 2;

  return (
    <div className="relative flex flex-col gap-2">
      <Label>Repo ID</Label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoComplete="off"
          className="pl-9 font-mono text-xs"
          onBlur={() => {
            window.setTimeout(() => onOpenChange(false), 120);
          }}
          onChange={(event) => {
            onChange(event.target.value);
            onOpenChange(true);
          }}
          onFocus={onFocus}
          placeholder={placeholder}
          value={value}
        />
      </div>

      {showPanel ? (
        <div className="absolute left-0 right-0 top-[74px] z-50 max-h-72 overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-xl">
          {isLoading ? (
            <div className="flex h-16 items-center gap-2 px-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              搜索 Hugging Face...
            </div>
          ) : error ? (
            <div className="px-3 py-3 text-sm text-destructive">{error}</div>
          ) : results.length ? (
            <div className="max-h-72 overflow-y-auto py-1">
              {results.map((result) => {
                const downloads = formatCount(result.downloads);
                const likes = formatCount(result.likes);
                return (
                  <button
                    className="flex w-full flex-col gap-1 px-3 py-2.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                    key={result.repo_id}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      onSelect(result);
                    }}
                    type="button"
                  >
                    <div className="flex w-full min-w-0 items-center justify-between gap-3">
                      <span className="truncate font-mono text-xs font-medium">
                        {result.repo_id}
                      </span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {[downloads ? `${downloads} 下载` : null, likes ? `${likes} 喜欢` : null]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                      {result.pipeline_tag ? <span>{result.pipeline_tag}</span> : null}
                      {result.library_name ? <span>{result.library_name}</span> : null}
                      {result.is_gated ? <span>gated</span> : null}
                      {result.is_private ? <span>private</span> : null}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="px-3 py-3 text-sm text-muted-foreground">
              没有找到匹配模型，也可以继续手动输入 Repo ID。
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function HuggingFaceRevisionSelect({
  value,
  onChange,
  repoId,
  revisions,
  isLoading,
  error
}: {
  value: string;
  onChange: (value: string) => void;
  repoId: string;
  revisions: RegistryModelHuggingFaceRevisionResult[];
  isLoading: boolean;
  error: string | null;
}) {
  const repoReady = isHuggingFaceRepoCandidate(repoId);
  const disabled = !repoReady || isLoading || revisions.length === 0;

  return (
    <div className="flex flex-col gap-2">
      <Label>Revision</Label>
      <Select disabled={disabled} onValueChange={onChange} value={value || undefined}>
        <SelectTrigger className="font-mono text-xs">
          <SelectValue
            placeholder={
              repoReady
                ? isLoading
                  ? "正在读取 Revision..."
                  : "请选择 Revision"
                : "先选择 Repo ID"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {revisions.map((revision) => (
            <SelectItem key={`${revision.kind}:${revision.name}`} value={revision.name}>
              <span className="font-mono text-xs">{revision.name}</span>
              <span className="ml-2 text-[11px] text-muted-foreground">
                {formatRevisionKind(revision.kind)}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          正在从 Hugging Face 获取可用 Revision
        </div>
      ) : error ? (
        <div className="text-xs text-destructive">{error}</div>
      ) : repoReady && revisions.length ? (
        <div className="text-xs text-muted-foreground">
          已获取 {revisions.length} 个可用 Revision，默认优先选择 main。
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">
          选择 Repo ID 后会自动从 Hugging Face 获取 branches 和 tags。
        </div>
      )}
    </div>
  );
}

function SourceTypeButton({
  active,
  icon,
  label,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-background/50 text-foreground hover:bg-card/80"
      )}
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  );
}

const modelStickyHeadClassName =
  "sticky left-0 z-20 w-[260px] min-w-[260px] bg-card/80 pr-4 backdrop-blur";

const modelStickyCellClassName = cn(
  "sticky left-0 z-10 w-[260px] min-w-[260px] bg-card/80 pr-4 align-top",
  "after:absolute after:right-0 after:top-0 after:h-full after:w-px after:bg-card/80"
);
