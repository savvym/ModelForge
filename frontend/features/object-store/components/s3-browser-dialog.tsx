"use client";

import * as React from "react";
import {
  Check,
  ChevronRight,
  FileText,
  Folder,
  HardDrive,
  RefreshCw,
  Search
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  consoleListFilterTriggerClassName,
  consoleListSearchInputClassName
} from "@/components/console/list-surface";
import { Input } from "@/components/ui/input";
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
  SheetHeader,
  SheetTitle
} from "@/components/ui/sheet";
import { browseObjectStore } from "@/features/object-store/api";
import { cn } from "@/lib/utils";
import type { ObjectStoreBrowserResponse } from "@/types/api";

const secondaryButtonClassName =
  "h-8 whitespace-nowrap rounded-full border border-[rgb(243,243,247)] bg-transparent px-3.5 text-[13px] font-medium text-[#f3f3f7] shadow-[rgb(243,243,247)_0_0_0_1px_inset] transition-colors hover:bg-[rgba(255,255,255,0.05)]";

export function S3BrowserDialog({
  description = "浏览 RustFS / S3 对象存储，选择一个对象路径用于导入。",
  initialUri,
  onClose,
  onSelect,
  open,
  title = "对象存储资源选择"
}: {
  description?: string;
  initialUri?: string | null;
  onClose: () => void;
  onSelect: (uri: string) => void;
  open: boolean;
  title?: string;
}) {
  const [browser, setBrowser] = React.useState<ObjectStoreBrowserResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedKey, setSelectedKey] = React.useState("");
  const [searchQuery, setSearchQuery] = React.useState("");
  const deferredSearchQuery = React.useDeferredValue(searchQuery.trim());

  const loadBrowser = React.useCallback(
    async (
      bucket?: string,
      prefix?: string,
      nextSelectedKey?: string,
      query?: string,
    ) => {
      setLoading(true);
      setError(null);

      try {
        const data = await browseObjectStore({ bucket, prefix, q: query });
        setBrowser(data);
        setSelectedKey(
          data.objects.some((item) => item.key === nextSelectedKey) ? nextSelectedKey ?? "" : ""
        );
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "加载对象存储失败";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  React.useEffect(() => {
    if (!open) {
      return;
    }

    const parsed = parseS3Uri(initialUri);
    setSearchQuery("");
    void loadBrowser(parsed?.bucket, parsed?.prefix ?? "", parsed?.key, "");
  }, [initialUri, loadBrowser, open]);

  React.useEffect(() => {
    if (!open || !browser) {
      return;
    }

    const activeQuery = browser.search_query?.trim() ?? "";
    if (activeQuery === deferredSearchQuery) {
      return;
    }

    void loadBrowser(browser.bucket, browser.prefix, selectedKey, deferredSearchQuery);
  }, [browser, deferredSearchQuery, loadBrowser, open, selectedKey]);

  const selectedUri =
    browser && selectedKey ? `s3://${browser.bucket}/${selectedKey}` : initialUri ?? "";
  const breadcrumbSegments = buildBreadcrumbSegments(browser?.prefix ?? "");
  const visiblePrefixes = browser?.prefixes ?? [];
  const visibleObjects = browser?.objects ?? [];
  const visibleCount = visiblePrefixes.length + visibleObjects.length;
  const isSearchMode = Boolean(browser?.search_query);

  return (
    <Sheet
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          onClose();
        }
      }}
      open={open}
    >
      <SheetContent className="w-full max-w-[760px] gap-0 overflow-hidden border-l border-slate-800/85 bg-[linear-gradient(180deg,rgba(10,15,22,0.98),rgba(8,12,19,0.95))] p-0 text-slate-100 shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-[760px] [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-slate-500 [&>button]:hover:bg-slate-800/80 [&>button]:hover:text-slate-100">
        <SheetHeader className="border-b border-slate-800/70 bg-[rgba(10,15,22,0.46)] px-5 py-4 pr-16 text-left">
          <SheetTitle className="text-[17px] font-semibold text-slate-100">{title}</SheetTitle>
          <SheetDescription className="text-[12px] leading-5 text-slate-400">{description}</SheetDescription>
        </SheetHeader>

        <div className="border-b border-slate-800/70 bg-[rgba(10,15,22,0.22)] px-5 py-4">
          <div className="space-y-3">
            <Select
              onValueChange={(value) => {
                void loadBrowser(value, "", "", deferredSearchQuery);
              }}
              value={browser?.bucket ?? ""}
            >
              <SelectTrigger
                className={cn(
                  consoleListFilterTriggerClassName,
                  "h-9 w-full rounded-lg text-[13px]"
                )}
              >
                <SelectValue placeholder="选择 bucket" />
              </SelectTrigger>
              <SelectContent className="border-slate-800/85 bg-[#111923]/98 text-slate-100">
                {(browser?.buckets ?? []).map((bucket) => (
                  <SelectItem key={bucket} value={bucket}>
                    {bucket}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex items-center gap-2">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
                <Input
                  className={cn(
                    consoleListSearchInputClassName,
                    "h-9 rounded-lg border-slate-800/85 bg-[rgba(10,15,22,0.72)] pl-9 text-[13px]"
                  )}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="支持全桶搜索文件名或路径"
                  value={searchQuery}
                />
              </div>

              <Button
                className="h-9 w-9 rounded-lg border-slate-800/90 bg-[rgba(10,15,22,0.28)] px-0 text-slate-300 shadow-none hover:bg-[rgba(20,28,38,0.42)] hover:text-white"
                disabled={loading}
                onClick={() =>
                  void loadBrowser(
                    browser?.bucket,
                    browser?.prefix,
                    selectedKey,
                    deferredSearchQuery,
                  )
                }
                type="button"
                variant="outline"
              >
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              </Button>
            </div>
          </div>

          <div className="mt-3 space-y-2">
            <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">
              {isSearchMode ? "全桶搜索结果" : browser?.prefix ? "当前目录" : "对象存储资源"}
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
              <button
                className="rounded-md px-2 py-1 transition-colors hover:bg-slate-800/80 hover:text-slate-100"
                onClick={() => void loadBrowser(browser?.bucket, "", "", deferredSearchQuery)}
                type="button"
              >
                {browser?.bucket ?? "根目录"}
              </button>
              {isSearchMode ? (
                <>
                  <span className="rounded-full border border-slate-800/85 bg-[rgba(10,15,22,0.36)] px-2.5 py-1 text-slate-400">
                    关键词：{browser?.search_query}
                  </span>
                  {browser?.prefix ? (
                    <span className="rounded-full border border-slate-800/85 bg-[rgba(10,15,22,0.36)] px-2.5 py-1 text-slate-400">
                      当前浏览位置：{browser.prefix}
                    </span>
                  ) : null}
                </>
              ) : (
                breadcrumbSegments.map((segment) => (
                  <React.Fragment key={segment.prefix}>
                    <ChevronRight className="h-3.5 w-3.5 text-slate-700" />
                    <button
                      className="rounded-md px-2 py-1 transition-colors hover:bg-slate-800/80 hover:text-slate-100"
                      onClick={() => void loadBrowser(browser?.bucket, segment.prefix, "", "")}
                      type="button"
                    >
                      {segment.label}
                    </button>
                  </React.Fragment>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 px-5 py-4">
          <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-slate-800/80 bg-[rgba(10,15,22,0.18)]">
            <div className="grid grid-cols-[minmax(0,1fr)_168px] border-b border-slate-800/70 bg-[rgba(15,20,28,0.78)] px-4 py-2.5 text-[12px] font-medium text-slate-500">
              <div>名称</div>
              <div>更新时间</div>
            </div>

            <div className="console-scrollbar-subtle min-h-0 flex-1 overflow-y-auto">
              {browser?.parent_prefix && !isSearchMode ? (
                <BrowserRow
                  icon={<Folder className="h-4 w-4 text-zinc-500" />}
                  onClick={() => void loadBrowser(browser.bucket, browser.parent_prefix ?? "", "", "")}
                  title="返回上一级"
                  updatedAt="--"
                />
              ) : null}

              {visiblePrefixes.map((entry) => (
                <BrowserRow
                  icon={<Folder className="h-4 w-4 text-zinc-700" />}
                  key={entry.prefix}
                  onClick={() => void loadBrowser(browser!.bucket, entry.prefix, "", "")}
                  title={entry.name}
                  updatedAt="--"
                />
              ))}

              {visibleObjects.map((entry) => {
                const selected = entry.key === selectedKey;
                return (
                  <BrowserRow
                    icon={
                      selected ? (
                        <Check className="h-4 w-4 text-zinc-900" />
                      ) : (
                        <FileText className="h-4 w-4 text-zinc-500" />
                      )
                    }
                    key={entry.key}
                    onClick={() => setSelectedKey(entry.key)}
                    onDoubleClick={() => {
                      onSelect(`s3://${browser!.bucket}/${entry.key}`);
                      onClose();
                    }}
                    selected={selected}
                    subtitle={
                      isSearchMode && entry.key !== entry.name ? entry.key : undefined
                    }
                    title={entry.name}
                    updatedAt={formatTimestamp(entry.last_modified)}
                  />
                );
              })}

              {!loading && !error && visibleCount === 0 ? (
                <div className="flex min-h-[240px] items-center justify-center px-6 text-center text-[13px] leading-6 text-slate-500">
                  {isSearchMode ? "全桶未找到匹配对象" : "当前目录为空"}
                </div>
              ) : null}

              {loading ? (
                <div className="flex min-h-[240px] items-center justify-center text-[13px] text-slate-500">
                  正在加载对象列表...
                </div>
              ) : null}

              {error ? (
                <div className="flex min-h-[240px] items-center justify-center px-6 text-center text-[13px] leading-6 text-rose-300">
                  {error}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800/70 bg-[rgba(10,15,22,0.22)] px-5 py-4">
          <div className="rounded-lg border border-slate-800/80 bg-[rgba(10,15,22,0.32)] px-4 py-3">
            <div className="flex items-center gap-2 text-[12px] text-slate-500">
              <HardDrive className="h-4 w-4" />
              <span>已选择对象路径</span>
            </div>
            <div className="mt-2 break-all text-[13px] leading-6 text-slate-100">
              {selectedUri || "请选择一个对象文件"}
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-[480px] text-[12px] leading-6 text-slate-500">
              仅支持选择具体对象文件。确认后会将 `s3://bucket/key` 回填到表单。
            </div>
            <div className="flex shrink-0 items-center gap-3 self-end">
              <Button className={secondaryButtonClassName} onClick={onClose} type="button" variant="outline">
                取消
              </Button>
              <Button
                className="h-8 rounded-full bg-sky-500 px-4 text-[13px] font-medium text-slate-950 hover:bg-sky-400"
                disabled={!browser || !selectedKey}
                onClick={() => {
                  if (!browser || !selectedKey) {
                    return;
                  }

                  onSelect(`s3://${browser.bucket}/${selectedKey}`);
                  onClose();
                }}
                type="button"
              >
                确认
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function BrowserRow({
  icon,
  onClick,
  onDoubleClick,
  selected = false,
  subtitle,
  title,
  updatedAt
}: {
  icon: React.ReactNode;
  onClick: () => void;
  onDoubleClick?: () => void;
  selected?: boolean;
  subtitle?: string;
  title: string;
  updatedAt?: string;
}) {
  return (
    <button
      className={cn(
        "grid w-full grid-cols-[minmax(0,1fr)_168px] items-center gap-4 border-b border-slate-800/70 px-4 py-3 text-left text-slate-200 transition-colors last:border-b-0",
        selected ? "bg-[rgba(33,50,71,0.55)] text-slate-50" : "hover:bg-[rgba(16,24,34,0.52)]"
      )}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      type="button"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="shrink-0">{icon}</div>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-medium">{title}</div>
          {subtitle ? (
            <div className="mt-1 truncate text-[12px] text-slate-500">{subtitle}</div>
          ) : null}
        </div>
      </div>
      <div className="text-[12px] text-slate-500">{updatedAt ?? "--"}</div>
    </button>
  );
}

function parseS3Uri(value?: string | null) {
  if (!value || !value.startsWith("s3://")) {
    return null;
  }

  const trimmed = value.slice(5);
  const slashIndex = trimmed.indexOf("/");
  if (slashIndex < 0) {
    return { bucket: trimmed, key: "", prefix: "" };
  }

  const bucket = trimmed.slice(0, slashIndex);
  const key = trimmed.slice(slashIndex + 1);
  const lastSlashIndex = key.lastIndexOf("/");
  return {
    bucket,
    key,
    prefix: lastSlashIndex >= 0 ? `${key.slice(0, lastSlashIndex + 1)}` : ""
  };
}

function buildBreadcrumbSegments(prefix: string) {
  const segments = prefix.split("/").filter(Boolean);
  let current = "";
  return segments.map((segment) => {
    current = `${current}${segment}/`;
    return { label: segment, prefix: current };
  });
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false
  });
}
