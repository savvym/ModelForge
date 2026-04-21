"use client";

import { useDeferredValue, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Database, FolderOpen, Rocket, Search, Trash2, UploadCloud } from "lucide-react";
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
  deleteRegistryModel,
  importRegistryModelFromObjectStorage
} from "@/features/model-registry/api";
import { cn } from "@/lib/utils";
import type { RegistryModelSummary } from "@/types/api";

type Feedback = { tone: "success" | "error"; text: string } | null;
type PendingDelete = { id: string; name: string } | null;

const MODEL_PAGE_SIZE = 12;

function createInitialImportForm() {
  return {
    base_model: "",
    name: "",
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
  if (model.source === "manual") {
    return "手动登记";
  }
  if (model.source === "finetune") {
    return "模型精调";
  }
  return model.source || "自定义";
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
  const deferredQuery = useDeferredValue(query);

  const myModels = useMemo(() => initialModels.filter(isMyModel), [initialModels]);

  const filteredModels = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return myModels;
    }

    return myModels.filter((model) =>
      [model.name, model.base_model, model.source]
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

  function updateImportField(key: keyof typeof importForm, value: string) {
    setImportForm((current) => ({ ...current, [key]: value }));
  }

  function openImportSheet() {
    setImportForm(createInitialImportForm());
    setFeedback(null);
    setIsImportOpen(true);
  }

  function closeImportSheet() {
    setIsImportOpen(false);
    setIsBrowserOpen(false);
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
    if (!importForm.name.trim() || !importForm.base_model.trim() || !importForm.source_uri.trim()) {
      setFeedback({ tone: "error", text: "请填写模型名称、基础模型和对象存储路径。" });
      return;
    }

    runAction(async () => {
      await importRegistryModelFromObjectStorage({
        base_model: importForm.base_model.trim(),
        name: importForm.name.trim(),
        source_uri: importForm.source_uri.trim()
      });
      closeImportSheet();
      refreshWithMessage("success", `${importForm.name.trim()} 已导入到我的模型。`);
    });
  }

  function deployModel(model: RegistryModelSummary) {
    router.push(`/endpoint?modelId=${encodeURIComponent(model.id)}`);
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
          description={`集中管理 ${myModels.length} 个自有模型资产，支持从 COS / S3 对象存储导入 safetensors checkpoint。`}
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
                      从对象存储导入一个 safetensors checkpoint 后，会在这里统一管理。
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
                从 COS / S3 对象存储导入 safetensors checkpoint。
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
                  <div className="flex h-10 items-center rounded-lg border border-border bg-background/50 px-3 text-sm text-foreground">
                    从对象存储导入
                  </div>
                </div>

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

                <div className="rounded-lg border border-border bg-background/40 px-4 py-3">
                  <div className="text-sm font-medium text-foreground">格式要求</div>
                  <div className="mt-1 text-sm leading-6 text-muted-foreground">
                    必须选择 Checkpoint 所在路径。当前仅支持 safetensors 格式文件。
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
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label>{label}</Label>
      <Input onChange={(event) => onChange(event.target.value)} placeholder={placeholder} value={value} />
    </div>
  );
}
