"use client";

import { useDeferredValue, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Bot, Copy, MoreHorizontal, Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import {
  consoleListSearchInputClassName,
  ConsoleListTableSurface,
  ConsoleListToolbar
} from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
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
import { Textarea } from "@/components/ui/textarea";
import {
  deleteModelProvider,
  deleteRegistryModel,
  syncModelProvider,
  testRegistryModel,
  updateModelProvider,
  updateRegistryModel
} from "@/features/model-registry/api";
import { formatModelApiFormat } from "@/features/model-registry/api-format";
import { cn } from "@/lib/utils";
import type {
  ModelProviderSummary,
  RegistryModelSummary,
  RegistryModelTestResponse
} from "@/types/api";

type PendingDelete = { kind: "provider" | "model"; id: string; name: string } | null;
const MODEL_PAGE_SIZE = 12;
const DEFAULT_TEST_PROMPT = "请用一句话介绍你自己，并说明你当前使用的模型名称。";

function statusTone(status: string) {
  if (status === "active") {
    return "border-emerald-500/60 bg-emerald-50 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-400/60 dark:bg-emerald-500/20 dark:text-emerald-100 dark:hover:bg-emerald-500/20";
  }
  if (status === "inactive") {
    return "border-border bg-card/80 text-muted-foreground";
  }
  return "border-border bg-card/80 text-foreground";
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

function formatProviderFormat(value: string) {
  return formatModelApiFormat(value);
}

function formatProviderType(value?: string | null) {
  if (!value) {
    return "--";
  }

  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function formatModelCategory(value?: string | null) {
  if (!value) {
    return "--";
  }

  const normalized = value.toLowerCase();
  if (normalized === "chat-model" || normalized === "text-generation") {
    return "文本生成";
  }
  if (normalized === "reasoning-model") {
    return "深度思考";
  }
  if (normalized === "video-model") {
    return "视频生成";
  }
  if (normalized === "image-model") {
    return "图片生成";
  }
  if (
    normalized === "voice-model" ||
    normalized === "audio-model" ||
    normalized === "asr-model" ||
    normalized === "tts-model"
  ) {
    return "语音模型";
  }
  if (
    normalized === "vector-model" ||
    normalized === "embedding-model" ||
    normalized === "embeddings-model"
  ) {
    return "向量模型";
  }

  return value;
}

function isLocalDeploymentProviderName(value?: string | null) {
  return Boolean(value?.startsWith("infer-agent /"));
}

export function ModelRegistryConsole({
  initialProviders,
  initialModels,
  initialSelectedProviderId
}: {
  initialProviders: ModelProviderSummary[];
  initialModels: RegistryModelSummary[];
  initialSelectedProviderId?: string | null;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    initialSelectedProviderId ?? null
  );
  const [modelQuery, setModelQuery] = useState("");
  const [modelPage, setModelPage] = useState(1);
  const [testingModel, setTestingModel] = useState<RegistryModelSummary | null>(null);
  const [testPrompt, setTestPrompt] = useState(DEFAULT_TEST_PROMPT);
  const [isTestingModel, setIsTestingModel] = useState(false);
  const [testResult, setTestResult] = useState<RegistryModelTestResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const deferredModelQuery = useDeferredValue(modelQuery);

  const providerOptions = useMemo(
    () =>
      initialProviders.filter(
        (provider) =>
          provider.status !== "deleted" && !isLocalDeploymentProviderName(provider.name)
      ),
    [initialProviders]
  );

  const selectedProvider = useMemo(
    () => providerOptions.find((provider) => provider.id === selectedProviderId) ?? null,
    [providerOptions, selectedProviderId]
  );

  const selectedProviderModels = useMemo(() => {
    if (!selectedProviderId) {
      return [];
    }

    const query = deferredModelQuery.trim().toLowerCase();
    return initialModels.filter((model) => {
      if (
        isLocalDeploymentProviderName(model.provider_name) ||
        isLocalDeploymentProviderName(model.vendor)
      ) {
        return false;
      }
      if (model.provider_id !== selectedProviderId) {
        return false;
      }
      if (!query) {
        return true;
      }

      return [model.name, model.model_code, model.vendor, model.category]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(query));
    });
  }, [deferredModelQuery, initialModels, selectedProviderId]);

  const totalModelPages = Math.max(1, Math.ceil(selectedProviderModels.length / MODEL_PAGE_SIZE));
  const currentModelPage = Math.min(modelPage, totalModelPages);
  const pagedProviderModels = useMemo(() => {
    const startIndex = (currentModelPage - 1) * MODEL_PAGE_SIZE;
    return selectedProviderModels.slice(startIndex, startIndex + MODEL_PAGE_SIZE);
  }, [currentModelPage, selectedProviderModels]);

  useEffect(() => {
    setModelPage(1);
  }, [selectedProviderId, deferredModelQuery]);

  function navigate(path: string) {
    router.push(path);
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
        const text = error instanceof Error ? error.message : "操作失败";
        toast.error(text);
      });
    });
  }

  function toggleProvider(provider: ModelProviderSummary) {
    const nextStatus = provider.status === "active" ? "inactive" : "active";
    runAction(async () => {
      await updateModelProvider(provider.id, { status: nextStatus });
      refreshWithMessage("success", `${provider.name} 已${nextStatus === "active" ? "启用" : "停用"}。`);
    });
  }

  function toggleModel(model: RegistryModelSummary) {
    const nextStatus = model.status === "active" ? "inactive" : "active";
    runAction(async () => {
      await updateRegistryModel(model.id, { status: nextStatus });
      refreshWithMessage("success", `${model.name} 已${nextStatus === "active" ? "启用" : "停用"}。`);
    });
  }

  function confirmDelete() {
    if (!pendingDelete) {
      return;
    }

    runAction(async () => {
      if (pendingDelete.kind === "provider") {
        await deleteModelProvider(pendingDelete.id);
        if (selectedProviderId === pendingDelete.id) {
          setSelectedProviderId(null);
        }
        refreshWithMessage("success", `Provider ${pendingDelete.name} 已删除。`);
      } else {
        await deleteRegistryModel(pendingDelete.id);
        refreshWithMessage("success", `模型 ${pendingDelete.name} 已删除。`);
      }
      setPendingDelete(null);
    });
  }

  function syncProvider(provider: ModelProviderSummary) {
    runAction(async () => {
      const result = await syncModelProvider(provider.id);
      refreshWithMessage(
        "success",
        `${result.provider_name} 已同步 ${result.synced_count} 个模型，新建 ${result.created_count} 个。`
      );
    });
  }

  function copyModelCode(modelCode?: string | null) {
    if (!modelCode) {
      return;
    }

    void navigator.clipboard
      .writeText(modelCode)
      .then(() => toast.success(`已复制模型 ID：${modelCode}`))
      .catch(() => toast.error("复制模型 ID 失败"));
  }

  function openModelTest(model: RegistryModelSummary) {
    setTestingModel(model);
    setTestPrompt(DEFAULT_TEST_PROMPT);
    setTestResult(null);
    setTestError(null);
  }

  function closeModelTest() {
    setTestingModel(null);
    setTestPrompt(DEFAULT_TEST_PROMPT);
    setTestResult(null);
    setTestError(null);
    setIsTestingModel(false);
  }

  async function submitModelTest() {
    if (!testingModel) {
      return;
    }

    const prompt = testPrompt.trim();
    if (!prompt) {
      setTestError("请输入测试 Prompt。");
      return;
    }

    setIsTestingModel(true);
    setTestError(null);
    setTestResult(null);

    try {
      const result = await testRegistryModel(testingModel.id, { prompt });
      setTestResult(result);
    } catch (error: unknown) {
      setTestError(error instanceof Error ? error.message : "模型测试失败");
    } finally {
      setIsTestingModel(false);
    }
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button onClick={() => navigate("/model-square/provider/new")} size="sm">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            新增 Provider
          </Button>
        </div>

        {pendingDelete ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card/80 px-4 py-3">
            <div className="text-sm text-foreground">
              确认删除{pendingDelete.kind === "provider" ? " Provider " : "模型 "}
              <span className="font-medium text-foreground">{pendingDelete.name}</span>？
            </div>
            <div className="flex gap-2">
              <Button onClick={() => setPendingDelete(null)} size="sm" variant="outline">
                取消
              </Button>
              <Button onClick={confirmDelete} size="sm">
                确认删除
              </Button>
            </div>
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <section className="overflow-hidden rounded-lg border border-border bg-card/80">
            <ScrollArea className="max-h-[72vh]">
              <div className="space-y-2 px-3 py-3">
                {providerOptions.length ? (
                  providerOptions.map((provider) => {
                    const selected = provider.id === selectedProviderId;
                    return (
                      <button
                        className={cn(
                          "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                          selected
                            ? "border-border bg-muted/60"
                            : "border-transparent bg-transparent hover:border-border hover:bg-muted/40"
                        )}
                        key={provider.id}
                        onClick={() => setSelectedProviderId(provider.id)}
                        type="button"
                      >
                        <div className="grid min-h-[88px] grid-cols-[minmax(0,1fr)_70px] items-start gap-3">
                          <div className="min-w-0 space-y-2">
                            <div className="flex items-center gap-2">
                              <div className="truncate text-sm font-medium text-foreground">{provider.name}</div>
                              <Badge className={statusTone(provider.status)} variant="outline">
                                {formatStatusLabel(provider.status)}
                              </Badge>
                            </div>
                            <div className="truncate text-xs text-muted-foreground">{provider.base_url}</div>
                            <div className="line-clamp-2 text-xs leading-5 text-muted-foreground">
                              {provider.description || `${formatProviderType(provider.provider_type)} · ${provider.adapter}`}
                            </div>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                              <span>{formatProviderFormat(provider.api_format)}</span>
                              <span className="text-muted-foreground">/</span>
                              <span>{provider.last_synced_at ? formatDateTime(provider.last_synced_at) : "未同步"}</span>
                            </div>
                          </div>
                          <div className="flex h-full flex-col items-end justify-between text-right">
                            <div className="text-lg font-semibold leading-none text-foreground">{provider.model_count}</div>
                            <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Models</div>
                          </div>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="px-1 py-1">
                    <EmptyState text="还没有 Provider。" />
                  </div>
                )}
              </div>
            </ScrollArea>
          </section>

          <section className="overflow-hidden rounded-lg border border-border bg-card/80">
            {selectedProvider ? (
              <div className="space-y-5 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-semibold text-foreground">{selectedProvider.name}</h2>
                      <Badge className={statusTone(selectedProvider.status)} variant="outline">
                        {formatStatusLabel(selectedProvider.status)}
                      </Badge>
                      <Badge variant="outline">{formatProviderFormat(selectedProvider.api_format)}</Badge>
                    </div>
                    <div className="text-sm text-muted-foreground">{selectedProvider.base_url}</div>
                    {selectedProvider.description ? (
                      <div className="max-w-3xl text-sm leading-7 text-muted-foreground">
                        {selectedProvider.description}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={isPending}
                      onClick={() => navigate(`/model-square/provider/${selectedProvider.id}/edit`)}
                      size="sm"
                      variant="outline"
                    >
                      编辑 Provider
                    </Button>
                    <Button
                      disabled={isPending}
                      onClick={() => syncProvider(selectedProvider)}
                      size="sm"
                      variant="outline"
                    >
                      <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                      同步模型
                    </Button>
                    <Button
                      disabled={isPending}
                      onClick={() => navigate(`/model-square/model/new?providerId=${selectedProvider.id}`)}
                      size="sm"
                      variant="outline"
                    >
                      <Plus className="mr-1.5 h-3.5 w-3.5" />
                      增加 Model
                    </Button>
                    <Button
                      disabled={isPending}
                      onClick={() => toggleProvider(selectedProvider)}
                      size="sm"
                      variant="outline"
                    >
                      {selectedProvider.status === "active" ? "停用" : "启用"}
                    </Button>
                    <Button
                      disabled={isPending}
                      onClick={() =>
                        setPendingDelete({
                          kind: "provider",
                          id: selectedProvider.id,
                          name: selectedProvider.name
                        })
                      }
                      size="sm"
                    >
                      删除
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {[
                    { label: "Provider type", value: formatProviderType(selectedProvider.provider_type) },
                    { label: "Adapter", value: selectedProvider.adapter },
                    { label: "API key", value: selectedProvider.has_api_key ? "Configured" : "Missing" },
                    { label: "Last sync", value: formatDateTime(selectedProvider.last_synced_at) }
                  ].map((item) => (
                    <div
                      className="rounded-lg border border-border bg-card/80 px-4 py-3"
                      key={item.label}
                    >
                      <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{item.label}</div>
                      <div className="mt-2 text-sm font-medium text-foreground">{item.value}</div>
                    </div>
                  ))}
                </div>

                <div className="space-y-3">
                  <div className="text-sm font-medium text-foreground">模型列表</div>
                  <ConsoleListToolbar className="justify-start">
                    <div className="relative min-w-[260px] flex-1 max-w-sm">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        className={consoleListSearchInputClassName}
                        onChange={(event) => setModelQuery(event.target.value)}
                        placeholder="Find model"
                        value={modelQuery}
                      />
                    </div>
                  </ConsoleListToolbar>

                  {selectedProviderModels.length ? (
                    <>
                      <ConsoleListTableSurface>
                        <ScrollArea className="max-h-[56vh]">
                          <Table className="text-sm">
                            <TableHeader className="sticky top-0 z-10 bg-card/80 backdrop-blur">
                              <TableRow className="hover:bg-transparent">
                                <TableHead className="h-10 min-w-[220px] px-3 normal-case tracking-normal">
                                  模型名称
                                </TableHead>
                                <TableHead className="h-10 min-w-[220px] px-3 normal-case tracking-normal">
                                  模型 ID
                                </TableHead>
                                <TableHead className="h-10 w-[120px] px-3 normal-case tracking-normal">
                                  状态
                                </TableHead>
                                <TableHead className="h-10 w-[140px] px-3 normal-case tracking-normal">
                                  分类
                                </TableHead>
                                <TableHead className="h-10 w-[180px] px-3 normal-case tracking-normal">
                                  最近同步
                                </TableHead>
                                <TableHead className="h-10 w-[160px] px-3 text-right normal-case tracking-normal">
                                  操作
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {pagedProviderModels.map((model) => (
                                <TableRow key={model.id}>
                                  <TableCell className="px-3 py-2.5">
                                    <div className="min-w-0 space-y-1">
                                      <div className="truncate font-medium text-foreground">{model.name}</div>
                                      <div className="text-xs text-muted-foreground">{model.vendor ?? "未设置 Vendor"}</div>
                                    </div>
                                  </TableCell>
                                  <TableCell className="px-3 py-2.5">
                                    <div className="flex items-center gap-2">
                                      <div className="max-w-[220px] truncate font-mono text-xs text-muted-foreground">
                                        {model.model_code ?? "--"}
                                      </div>
                                      {model.model_code ? (
                                        <button
                                          aria-label={`复制 ${model.name} 的模型 ID`}
                                          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-card/80 hover:text-foreground"
                                          onClick={() => copyModelCode(model.model_code)}
                                          title="复制模型 ID"
                                          type="button"
                                        >
                                          <Copy className="h-3.5 w-3.5" />
                                        </button>
                                      ) : null}
                                    </div>
                                  </TableCell>
                                  <TableCell className="px-3 py-2.5">
                                    <Badge className={statusTone(model.status)} variant="outline">
                                      {formatStatusLabel(model.status)}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="px-3 py-2.5 text-sm text-foreground">
                                    {formatModelCategory(model.category)}
                                  </TableCell>
                                  <TableCell className="px-3 py-2.5 text-sm text-muted-foreground">
                                    {formatDateTime(model.last_synced_at)}
                                  </TableCell>
                                  <TableCell className="px-3 py-2.5">
                                    <div className="flex justify-end">
                                      <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                          <Button className="h-7 w-7 px-0" size="sm" variant="ghost">
                                            <MoreHorizontal className="h-3.5 w-3.5" />
                                            <span className="sr-only">{model.name} 操作菜单</span>
                                          </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end" className="w-36">
                                          <DropdownMenuItem
                                            disabled={isPending}
                                            onSelect={() => navigate(`/model-square/model/${model.id}/edit`)}
                                          >
                                            编辑
                                          </DropdownMenuItem>
                                          <DropdownMenuItem
                                            disabled={!model.provider_id || !model.model_code || isTestingModel}
                                            onSelect={() => openModelTest(model)}
                                          >
                                            测试
                                          </DropdownMenuItem>
                                          <DropdownMenuItem
                                            disabled={isPending}
                                            onSelect={() => toggleModel(model)}
                                          >
                                            {model.status === "active" ? "停用" : "启用"}
                                          </DropdownMenuItem>
                                          <DropdownMenuSeparator />
                                          <DropdownMenuItem
                                            className="text-destructive"
                                            disabled={isPending}
                                            onSelect={() =>
                                              setPendingDelete({
                                                kind: "model",
                                                id: model.id,
                                                name: model.name
                                              })
                                            }
                                          >
                                            删除
                                          </DropdownMenuItem>
                                        </DropdownMenuContent>
                                      </DropdownMenu>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </ScrollArea>

                        <div className="flex flex-wrap items-center justify-between gap-3 px-1 py-3">
                          <div className="text-xs text-muted-foreground">
                            {(currentModelPage - 1) * MODEL_PAGE_SIZE + 1}
                            {" - "}
                            {Math.min(currentModelPage * MODEL_PAGE_SIZE, selectedProviderModels.length)} of{" "}
                            {selectedProviderModels.length}
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
                    </>
                  ) : (
                    <div className="p-4">
                      <EmptyState text="当前 Provider 下没有匹配的模型。" />
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex min-h-[560px] items-center justify-center p-8">
                <Empty className="w-full max-w-md border border-dashed border-border bg-card/80 px-6 py-8">
                  <EmptyContent>
                    <EmptyHeader>
                      <EmptyMedia
                        variant="icon"
                        className="border border-border bg-card/80 text-foreground"
                      >
                        <Bot className="h-5 w-5" />
                      </EmptyMedia>
                      <EmptyTitle className="text-base text-foreground">选择一个 Provider</EmptyTitle>
                      <EmptyDescription className="text-sm leading-6 text-muted-foreground">
                        点击左侧 Provider 后显示对应模型列表，或者先创建一个新的 Provider 连接。
                      </EmptyDescription>
                    </EmptyHeader>
                    <div className="flex justify-center">
                      <Button onClick={() => navigate("/model-square/provider/new")} size="sm">
                        <Plus className="mr-1.5 h-3.5 w-3.5" />
                        创建 Provider
                      </Button>
                    </div>
                  </EmptyContent>
                </Empty>
              </div>
            )}
          </section>
        </div>
      </div>
      <Sheet
        onOpenChange={(open) => {
          if (!open) {
            closeModelTest();
          }
        }}
        open={!!testingModel}
      >
        <SheetContent className="w-full gap-0 overflow-hidden border-l border-border bg-card p-0 text-foreground shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-2xl [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-muted-foreground [&>button]:hover:bg-card/80 [&>button]:hover:text-foreground">
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b border-border bg-card px-6 py-5 pr-12">
              <SheetTitle className="text-foreground">测试模型</SheetTitle>
              <SheetDescription className="text-muted-foreground">
                {testingModel ? (
                  <>
                    通过 {testingModel.provider_name ?? "当前 Provider"} 对模型{" "}
                    <span className="font-medium text-foreground">{testingModel.name}</span> 发起一次最小调用，
                    验证模型是否可以正常返回结果。
                  </>
                ) : (
                  "通过 Provider 发起一次最小调用，验证模型是否可用。"
                )}
              </SheetDescription>
            </SheetHeader>

            <ScrollArea className="flex-1">
              <div className="space-y-6 px-6 py-5">
                {testingModel ? (
                  <div className="grid gap-3 rounded-lg border border-border bg-card/80 p-4 text-sm text-foreground sm:grid-cols-2">
                    <div>
                      <div className="text-xs text-muted-foreground">模型名称</div>
                      <div className="mt-1 font-medium text-foreground">{testingModel.name}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">模型 ID</div>
                      <div className="mt-1 break-all font-mono text-xs text-foreground">
                        {testingModel.model_code ?? "--"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Provider</div>
                      <div className="mt-1 font-medium text-foreground">
                        {testingModel.provider_name ?? "--"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">接口格式</div>
                      <div className="mt-1 font-medium text-foreground">
                        {formatProviderFormat(testingModel.api_format ?? "chat-completions")}
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="space-y-2">
                  <Label htmlFor="model-test-prompt">测试 Prompt</Label>
                  <Textarea
                    id="model-test-prompt"
                    onChange={(event) => setTestPrompt(event.target.value)}
                    placeholder="输入一条最小测试 Prompt"
                    value={testPrompt}
                  />
                  <div className="text-xs text-muted-foreground">
                    建议用一句短 Prompt 做联通性验证，避免不必要的长输出。
                  </div>
                </div>

                {testError ? (
                  <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    {testError}
                  </div>
                ) : null}

                {testResult ? (
                  <div className="space-y-4 rounded-lg border border-border bg-card/80">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">调用成功</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          延迟 {testResult.latency_ms} ms
                          {testResult.request_id ? ` · Request ID ${testResult.request_id}` : ""}
                        </div>
                      </div>
                      <Badge className="border-emerald-400/25 bg-emerald-400/12 text-emerald-100" variant="outline">
                        可用
                      </Badge>
                    </div>
                    <div className="space-y-2 px-4 pb-4">
                      <div className="text-xs text-muted-foreground">返回内容</div>
                      <ScrollArea className="max-h-[320px] rounded-lg border border-border bg-card/80 px-4 py-3 text-sm leading-6 text-foreground">
                        <pre className="whitespace-pre-wrap break-words font-sans">
                          {testResult.output_text}
                        </pre>
                      </ScrollArea>
                    </div>
                  </div>
                ) : null}
              </div>
            </ScrollArea>

            <SheetFooter className="border-t border-border px-6 py-4">
              <Button
                disabled={isTestingModel || !testingModel}
                onClick={() => {
                  void submitModelTest();
                }}
              >
                {isTestingModel ? "测试中..." : "开始测试"}
              </Button>
              <Button
                className="border-border text-foreground hover:border-border hover:bg-card/80"
                onClick={closeModelTest}
                variant="outline"
              >
                关闭
              </Button>
            </SheetFooter>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <Empty className="border border-dashed border-border bg-card/80 px-3 py-6">
      <EmptyContent>
        <EmptyHeader>
          <EmptyDescription className="text-sm text-muted-foreground">{text}</EmptyDescription>
        </EmptyHeader>
      </EmptyContent>
    </Empty>
  );
}
