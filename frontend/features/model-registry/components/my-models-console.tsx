"use client";

import { useDeferredValue, useEffect, useMemo, useState, useTransition } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  Database,
  FolderOpen,
  Globe2,
  HardDrive,
  Loader2,
  Rocket,
  Search,
  Trash2,
  UploadCloud
} from "lucide-react";
import {
  ConsoleListHeader,
  consoleListSearchInputClassName,
  ConsoleListTableSurface,
  ConsoleListToolbar
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
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle
} from "@/components/ui/empty";
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
import { createDeploymentFromModel } from "@/features/model-deployments/api";
import {
  deleteRegistryModel,
  importRegistryModelFromHuggingFace,
  importRegistryModelFromObjectStorage,
  listHuggingFaceRevisions,
  searchHuggingFaceModels
} from "@/features/model-registry/api";
import { cn } from "@/lib/utils";
import type {
  RegistryModelHuggingFaceRevisionResult,
  RegistryModelHuggingFaceSearchResult,
  RegistryModelSummary
} from "@/types/api";

type Feedback = { tone: "success" | "error"; text: string } | null;
type PendingDelete = { id: string; name: string } | null;
type ImportSourceType = "object-storage" | "huggingface";

const MODEL_PAGE_SIZE = 12;

function createInitialImportForm() {
  return {
    base_model: "",
    name: "",
    repo_id: "",
    revision: "",
    source_type: "huggingface" as ImportSourceType,
    source_uri: ""
  };
}

function isMyModel(model: RegistryModelSummary) {
  return !model.is_provider_managed && model.source !== "provider-sync";
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

export function MyModelsConsole({ initialModels }: { initialModels: RegistryModelSummary[] }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [query, setQuery] = useState("");
  const [modelPage, setModelPage] = useState(1);
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

  const filteredModels = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return myModels;
    }

    return myModels.filter((model) =>
      [model.name, model.base_model, model.source, model.import_repo_id]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(normalizedQuery))
    );
  }, [deferredQuery, myModels]);

  const totalModelPages = Math.max(1, Math.ceil(filteredModels.length / MODEL_PAGE_SIZE));
  const currentModelPage = Math.min(modelPage, totalModelPages);
  const pagedModels = useMemo(() => {
    const startIndex = (currentModelPage - 1) * MODEL_PAGE_SIZE;
    return filteredModels.slice(startIndex, startIndex + MODEL_PAGE_SIZE);
  }, [currentModelPage, filteredModels]);

  useEffect(() => {
    setModelPage(1);
  }, [deferredQuery]);

  useEffect(() => {
    if (feedback?.tone !== "success") {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setFeedback((current) => (current?.tone === "success" ? null : current));
    }, 2200);

    return () => window.clearTimeout(timeoutId);
  }, [feedback]);

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
    setFeedback(null);
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
    setFeedback({ tone, text });
    router.refresh();
  }

  function runAction(action: () => Promise<void>) {
    setFeedback(null);
    startTransition(() => {
      void action().catch((error: unknown) => {
        setFeedback({ tone: "error", text: error instanceof Error ? error.message : "操作失败" });
      });
    });
  }

  function submitImport() {
    if (!importForm.name.trim() || !importForm.base_model.trim()) {
      setFeedback({ tone: "error", text: "请填写模型名称和基础模型。" });
      return;
    }

    if (importForm.source_type === "object-storage" && !importForm.source_uri.trim()) {
      setFeedback({ tone: "error", text: "请填写对象存储路径。" });
      return;
    }

    if (importForm.source_type === "huggingface" && !importForm.repo_id.trim()) {
      setFeedback({ tone: "error", text: "请填写 Hugging Face Repo ID。" });
      return;
    }

    if (importForm.source_type === "huggingface" && !importForm.revision.trim()) {
      setFeedback({ tone: "error", text: "请选择模型 Revision。" });
      return;
    }

    runAction(async () => {
      if (importForm.source_type === "huggingface") {
        await importRegistryModelFromHuggingFace({
          base_model: importForm.base_model.trim(),
          name: importForm.name.trim(),
          repo_id: importForm.repo_id.trim(),
          revision: importForm.revision.trim()
        });
      } else {
        await importRegistryModelFromObjectStorage({
          base_model: importForm.base_model.trim(),
          name: importForm.name.trim(),
          source_uri: importForm.source_uri.trim()
        });
      }
      closeImportSheet();
      refreshWithMessage("success", `${importForm.name.trim()} 已导入到我的模型。`);
    });
  }

  function deployModel(model: RegistryModelSummary) {
    runAction(async () => {
      const deployment = await createDeploymentFromModel(model.id, {
        name: `${model.name} 部署`,
        served_model_name: model.model_code ?? model.name
      });
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

  return (
    <>
      <div className="flex flex-col gap-4">
        <ConsoleListHeader
          actions={
            <Button onClick={openImportSheet} size="sm">
              <UploadCloud />
              导入模型
            </Button>
          }
          description={`集中管理 ${myModels.length} 个自有模型资产，支持从 Hugging Face 或 COS / S3 登记 safetensors checkpoint。`}
          title="我的模型"
        />

        {feedback?.tone === "success" ? (
          <div className="pointer-events-none fixed right-6 top-6 z-50">
            <div className="rounded-lg border border-border bg-card/80 px-3 py-2 text-sm text-foreground shadow-[0_18px_48px_rgba(2,6,23,0.42)] backdrop-blur">
              {feedback.text}
            </div>
          </div>
        ) : null}

        {feedback?.tone === "error" ? (
          <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {feedback.text}
          </div>
        ) : null}

        <section className="overflow-hidden rounded-lg border border-border bg-card/80">
          <div className="flex flex-col gap-3 border-b border-border px-4 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-sm font-medium text-foreground">模型资产</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {filteredModels.length} of {myModels.length}
              </div>
            </div>
            <ConsoleListToolbar className="justify-start lg:justify-end">
              <div className="relative min-w-[260px] flex-1 lg:flex-none">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className={cn(consoleListSearchInputClassName, "w-full")}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索模型名称或基础模型"
                  type="search"
                  value={query}
                />
              </div>
            </ConsoleListToolbar>
          </div>

          {filteredModels.length ? (
            <ConsoleListTableSurface>
              <ScrollArea className="max-h-[68vh]">
                <Table className="text-sm">
                  <TableHeader className="sticky top-0 z-10 bg-card/90 backdrop-blur">
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="h-10 min-w-[220px] px-3 normal-case tracking-normal">
                        模型名称
                      </TableHead>
                      <TableHead className="h-10 min-w-[180px] px-3 normal-case tracking-normal">
                        基础模型
                      </TableHead>
                      <TableHead className="h-10 min-w-[140px] px-3 normal-case tracking-normal">
                        来源
                      </TableHead>
                      <TableHead className="h-10 w-[140px] px-3 normal-case tracking-normal">
                        状态
                      </TableHead>
                      <TableHead className="h-10 w-[180px] px-3 normal-case tracking-normal">
                        创建时间
                      </TableHead>
                      <TableHead className="h-10 w-[180px] px-3 text-right normal-case tracking-normal">
                        操作
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pagedModels.map((model) => (
                      <TableRow key={model.id}>
                        <TableCell className="px-3 py-2.5">
                          <div className="truncate font-medium text-foreground">{model.name}</div>
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <span className="font-mono text-xs text-foreground">
                            {model.base_model ?? "--"}
                          </span>
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <span className="text-sm text-foreground">{formatModelSource(model)}</span>
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <Badge className={statusTone(model.status)} variant={statusVariant(model.status)}>
                            <span className={cn("size-1.5 rounded-full", statusDotTone(model.status))} />
                            {formatStatusLabel(model.status)}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-3 py-2.5 text-sm text-muted-foreground">
                          {formatDateTime(model.created_at)}
                        </TableCell>
                        <TableCell className="px-3 py-2.5">
                          <div className="flex justify-end gap-2">
                            <Button
                              disabled={isPending}
                              onClick={() => deployModel(model)}
                              size="sm"
                              variant="outline"
                            >
                              <Rocket />
                              部署
                            </Button>
                            <Button
                              className="text-destructive hover:text-destructive"
                              disabled={isPending}
                              onClick={() => setPendingDelete({ id: model.id, name: model.name })}
                              size="sm"
                              variant="ghost"
                            >
                              <Trash2 />
                              删除
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ScrollArea>

              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="text-xs text-muted-foreground">
                  {(currentModelPage - 1) * MODEL_PAGE_SIZE + 1}
                  {" - "}
                  {Math.min(currentModelPage * MODEL_PAGE_SIZE, filteredModels.length)} of{" "}
                  {filteredModels.length}
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
            </ConsoleListTableSurface>
          ) : (
            <div className="flex min-h-[460px] items-center justify-center p-8">
              <Empty className="w-full max-w-md border border-dashed border-border bg-card/80 px-6 py-8">
                <EmptyContent>
                  <EmptyHeader>
                    <EmptyMedia
                      className="border border-border bg-card/80 text-foreground"
                      variant="icon"
                    >
                      <Database />
                    </EmptyMedia>
                    <EmptyTitle className="text-base text-foreground">还没有我的模型</EmptyTitle>
                    <EmptyDescription className="text-sm leading-6 text-muted-foreground">
                      从 Hugging Face 或对象存储登记一个 safetensors checkpoint 后，会在这里统一管理。
                    </EmptyDescription>
                  </EmptyHeader>
                  <Button onClick={openImportSheet} size="sm">
                    <UploadCloud />
                    导入模型
                  </Button>
                </EmptyContent>
              </Empty>
            </div>
          )}
        </section>
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
                    {importForm.source_type === "huggingface"
                      ? "录入时会使用系统配置中的 Hugging Face 凭据校验 repo、revision 和 safetensors 权重权限。"
                      : "必须选择 Checkpoint 所在路径。当前仅支持 safetensors 格式文件。"}
                  </div>
                  <pre className="mt-3 whitespace-pre-wrap rounded-md bg-card/80 px-3 py-2 font-mono text-xs leading-6 text-muted-foreground">
{`|-- *.safetensors
|-- adapter_config.json (LoRA)
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
