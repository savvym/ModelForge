"use client";

import Link from "next/link";
import * as React from "react";
import {
  ArrowUp,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  ExternalLink,
  FileArchive,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder,
  FolderOpen,
  HardDrive,
  Info,
  Loader2,
  Link2,
  MoreVertical,
  PanelLeftClose,
  Plus,
  RefreshCw,
  Redo2,
  Search,
  Settings2,
  Trash2,
  Undo2,
  X,
  UploadCloud
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {
  consoleListFilterTriggerClassName,
  consoleListSearchInputClassName
} from "@/components/console/list-surface";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import {
  browseObjectStore,
  createManagedFolder,
  deleteObjectStorePrefix,
  deleteObjectStoreObject,
  getObjectStoreDownloadUrl,
  getObjectStoreObjectPreview,
  initiateDirectUpload,
  updateObjectStoreTextFile
} from "@/features/object-store/api";
import { cn } from "@/lib/utils";
import type {
  ObjectStoreBrowserResponse,
  ObjectStoreObjectPreviewResponse,
  ObjectStoreObjectEntry,
  ObjectStoreUploadResponse
} from "@/types/api";

type ObjectStoreConsoleMode = "files" | "data";
type UploadLifecycleStatus = "preparing" | "uploading" | "finalizing";
type UploadQueueItemStatus = "queued" | UploadLifecycleStatus | "completed" | "failed";
type ObjectPreviewKind = ObjectStoreObjectPreviewResponse["preview_kind"];
type FileViewMode = "read" | "edit";

type UploadQueueItem = {
  id: string;
  label: string;
  sizeBytes: number;
  uploadedBytes: number;
  status: UploadQueueItemStatus;
  error?: string | null;
};

export function ObjectStoreConsole({
  mode,
  initialBucket,
  initialPrefix,
  rootPrefix
}: {
  mode: ObjectStoreConsoleMode;
  initialBucket?: string | null;
  initialPrefix?: string | null;
  rootPrefix?: string;
}) {
  const [browser, setBrowser] = React.useState<ObjectStoreBrowserResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedKey, setSelectedKey] = React.useState("");
  const [activePreviewKey, setActivePreviewKey] = React.useState<string | null>(null);
  const [previewCache, setPreviewCache] = React.useState<
    Record<string, ObjectStoreObjectPreviewResponse>
  >({});
  const [loadingPreviewKey, setLoadingPreviewKey] = React.useState<string | null>(null);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [uploading, setUploading] = React.useState(false);
  const [uploadQueue, setUploadQueue] = React.useState<UploadQueueItem[]>([]);
  const [uploadPanelCollapsed, setUploadPanelCollapsed] = React.useState(false);
  const [creatingFolder, setCreatingFolder] = React.useState(false);
  const [createFolderOpen, setCreateFolderOpen] = React.useState(false);
  const [createFolderPrefix, setCreateFolderPrefix] = React.useState("");
  const [folderDraft, setFolderDraft] = React.useState("");
  const [folderDialogError, setFolderDialogError] = React.useState<string | null>(null);
  const [pendingUploadPrefix, setPendingUploadPrefix] = React.useState<string | null>(null);
  const [deletingKey, setDeletingKey] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);
  const [page, setPage] = React.useState(1);
  const [draggingFiles, setDraggingFiles] = React.useState(false);
  const [explorerPaneWidth, setExplorerPaneWidth] = React.useState(320);
  const [showInspector, setShowInspector] = React.useState(false);
  const [fileViewMode, setFileViewMode] = React.useState<FileViewMode>("read");
  const [draftContent, setDraftContent] = React.useState("");
  const [savingDraft, setSavingDraft] = React.useState(false);
  const [cursorPosition, setCursorPosition] = React.useState({ line: 1, column: 1 });
  const [wrapPreviewLines, setWrapPreviewLines] = React.useState(true);
  const [explorerDirectoryCache, setExplorerDirectoryCache] = React.useState<
    Record<string, ObjectStoreBrowserResponse>
  >({});
  const [expandedPrefixes, setExpandedPrefixes] = React.useState<string[]>([]);
  const [loadingExplorerPrefixes, setLoadingExplorerPrefixes] = React.useState<
    Record<string, boolean>
  >({});
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const folderInputRef = React.useRef<HTMLInputElement | null>(null);
  const resizeStateRef = React.useRef<{ startX: number; startWidth: number } | null>(null);
  const explorerAutoExpandScopeRef = React.useRef<string | null>(null);
  const lastTextPreviewObjectKeyRef = React.useRef<string | null>(null);
  const deferredSearchQuery = React.useDeferredValue(searchQuery.trim().toLowerCase());

  const loadBrowser = React.useCallback(
    async (bucket?: string, prefix?: string, nextSelectedKey?: string) => {
      setLoading(true);
      setError(null);

      try {
        const data = await browseObjectStore({
          bucket,
          prefix: constrainPrefix(prefix, rootPrefix, mode)
        });
        setBrowser(data);
        if (mode === "files") {
          setExplorerDirectoryCache((current) => ({
            ...current,
            [buildExplorerDirectoryCacheKey(data.bucket, data.prefix)]: data
          }));
        }
        setSelectedKey(
          data.objects.some((item) => item.key === nextSelectedKey) ? nextSelectedKey ?? "" : ""
        );
      } catch (requestError) {
        const message = requestError instanceof Error ? requestError.message : "加载对象存储失败";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [mode, rootPrefix]
  );

  React.useEffect(() => {
    void loadBrowser(initialBucket ?? undefined, initialPrefix ?? undefined, "");
  }, [initialBucket, initialPrefix, loadBrowser]);

  React.useEffect(() => {
    if (!folderInputRef.current) {
      return;
    }

    folderInputRef.current.setAttribute("webkitdirectory", "");
    folderInputRef.current.setAttribute("directory", "");
  }, []);

  const filteredPrefixes = (browser?.prefixes ?? []).filter((entry) =>
    matchesSearch(`${entry.name} ${entry.prefix}`, deferredSearchQuery)
  );
  const filteredObjects = (browser?.objects ?? []).filter((entry) =>
    matchesSearch(`${entry.name} ${entry.key}`, deferredSearchQuery)
  );
  const selectedEntry =
    browser?.objects.find((entry) => entry.key === selectedKey) ??
    filteredObjects.find((entry) => entry.key === selectedKey) ??
    null;
  const activePreviewEntry =
    browser?.objects.find((entry) => entry.key === activePreviewKey) ??
    filteredObjects.find((entry) => entry.key === activePreviewKey) ??
    null;
  const visibleObjectSize = filteredObjects.reduce((sum, entry) => sum + entry.size_bytes, 0);
  const currentPath = browser
    ? buildCurrentPathLabel({
        prefix: browser.prefix,
        rootPrefix,
        mode
      })
    : "/";
  const filesBreadcrumbs = buildBreadcrumbSegments(browser?.prefix ?? "", rootPrefix);
  const currentDirectoryTitle =
    mode === "files" ? filesBreadcrumbs.at(-1)?.label ?? "Files" : browser?.prefix || "对象存储";
  const filesDirectoryLocation =
    mode === "files" ? buildFilesLocationLabel(browser?.prefix ?? "", rootPrefix) : currentPath;
  const createFolderLocation =
    mode === "files"
      ? buildFilesLocationLabel(createFolderPrefix || browser?.prefix || rootPrefix || "", rootPrefix)
      : currentPath;
  const explorerRootPrefix = normalizePrefix(rootPrefix) || normalizePrefix(browser?.prefix) || "";
  const filesPathSegments = React.useMemo(
    () => [{ label: "Files", prefix: explorerRootPrefix }, ...filesBreadcrumbs],
    [explorerRootPrefix, filesBreadcrumbs]
  );
  const explorerItems = filteredPrefixes;
  const explorerFiles = filteredObjects;
  const expandedPrefixSet = React.useMemo(
    () => new Set(expandedPrefixes.map((prefix) => normalizePrefix(prefix))),
    [expandedPrefixes]
  );
  const selectedExplorerKey = activePreviewKey ?? selectedKey;
  const tableEntries = [
    ...filteredPrefixes.map((entry) => ({
      kind: "prefix" as const,
      id: entry.prefix,
      name: entry.name,
      prefix: entry.prefix
    })),
    ...filteredObjects.map((entry) => ({
      kind: "object" as const,
      id: entry.key,
      object: entry
    }))
  ];
  const pageSize = 25;
  const totalEntries = tableEntries.length;
  const totalPages = Math.max(1, Math.ceil(totalEntries / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageStartIndex = (currentPage - 1) * pageSize;
  const pagedEntries = tableEntries.slice(pageStartIndex, pageStartIndex + pageSize);
  const pageStart = totalEntries === 0 ? 0 : pageStartIndex + 1;
  const pageEnd = totalEntries === 0 ? 0 : Math.min(pageStartIndex + pageSize, totalEntries);
  const activePreviewCacheKey =
    browser && activePreviewKey ? buildObjectPreviewCacheKey(browser.bucket, activePreviewKey) : null;
  const activePreview = activePreviewCacheKey ? previewCache[activePreviewCacheKey] : null;
  const showPreviewPane =
    Boolean(activePreviewKey) &&
    Boolean(activePreviewEntry) &&
    isPreviewableFile(activePreviewEntry?.name ?? "");
  const canEditActiveTextFile =
    Boolean(
      activePreview &&
      activePreview.preview_kind === "text" &&
      !activePreview.truncated
    );
  const activePreviewTextContent =
    activePreview && activePreview.preview_kind === "text" ? activePreview.content ?? "" : "";
  const isActiveTextDraftDirty =
    canEditActiveTextFile && draftContent !== activePreviewTextContent;
  const panePathSegments = React.useMemo(() => {
    if (showPreviewPane && activePreviewEntry) {
      return [
        ...filesPathSegments.map((segment) => ({
          ...segment,
          kind: "directory" as const
        })),
        {
          label: activePreviewEntry.name,
          key: activePreviewEntry.key,
          kind: "file" as const
        }
      ];
    }

    return filesPathSegments.map((segment) => ({
      ...segment,
      kind: "directory" as const
    }));
  }, [activePreviewEntry, filesPathSegments, showPreviewPane]);
  const uploadQueueSummary = React.useMemo(() => {
    if (uploadQueue.length === 0) {
      return null;
    }

    let totalBytes = 0;
    let uploadedBytes = 0;
    let completedFiles = 0;
    let failedFiles = 0;

    for (const item of uploadQueue) {
      totalBytes += item.sizeBytes;
      uploadedBytes += Math.min(item.sizeBytes, item.uploadedBytes);
      if (item.status === "completed") {
        completedFiles += 1;
      }
      if (item.status === "failed") {
        failedFiles += 1;
      }
    }

    const activeItem =
      uploadQueue.find((item) => ["preparing", "uploading", "finalizing"].includes(item.status)) ??
      uploadQueue.find((item) => item.status === "failed") ??
      uploadQueue.at(-1) ??
      null;

    return {
      totalFiles: uploadQueue.length,
      totalBytes,
      uploadedBytes,
      completedFiles,
      failedFiles,
      activeItem
    };
  }, [uploadQueue]);

  const setExplorerPrefixExpanded = React.useCallback((prefix: string | undefined, expanded: boolean) => {
    const normalizedPrefix = normalizePrefix(prefix);
    setExpandedPrefixes((current) => {
      const next = new Set(current.map((entry) => normalizePrefix(entry)));
      if (expanded) {
        next.add(normalizedPrefix);
      } else {
        next.delete(normalizedPrefix);
      }
      return Array.from(next);
    });
  }, []);

  const expandExplorerPath = React.useCallback((prefix: string | undefined) => {
    const normalizedPrefix = normalizePrefix(prefix);
    const prefixesToReveal = [
      explorerRootPrefix,
      ...buildBreadcrumbSegments(normalizedPrefix, rootPrefix).map((segment) => segment.prefix)
    ];
    setExpandedPrefixes((current) => {
      const next = new Set(current.map((entry) => normalizePrefix(entry)));
      prefixesToReveal.forEach((entry) => {
        next.add(normalizePrefix(entry));
      });
      return Array.from(next);
    });
  }, [explorerRootPrefix, rootPrefix]);

  const ensureExplorerDirectoryLoaded = React.useCallback(
    async (prefix: string | undefined, options?: { force?: boolean }) => {
      if (!browser || mode !== "files") {
        return null;
      }

      const normalizedPrefix = constrainPrefix(prefix, rootPrefix, mode);
      const cacheKey = buildExplorerDirectoryCacheKey(browser.bucket, normalizedPrefix);
      if (!options?.force && explorerDirectoryCache[cacheKey]) {
        return explorerDirectoryCache[cacheKey];
      }
      if (loadingExplorerPrefixes[cacheKey]) {
        return explorerDirectoryCache[cacheKey] ?? null;
      }

      setLoadingExplorerPrefixes((current) => ({
        ...current,
        [cacheKey]: true
      }));

      try {
        const data = await browseObjectStore({
          bucket: browser.bucket,
          prefix: normalizedPrefix
        });
        setExplorerDirectoryCache((current) => ({
          ...current,
          [cacheKey]: data
        }));
        return data;
      } catch (requestError) {
        const message =
          requestError instanceof Error ? requestError.message : "加载目录树失败";
        setError(message);
        return null;
      } finally {
        setLoadingExplorerPrefixes((current) => {
          const next = { ...current };
          delete next[cacheKey];
          return next;
        });
      }
    },
    [browser, explorerDirectoryCache, loadingExplorerPrefixes, mode, rootPrefix]
  );

  React.useEffect(() => {
    setPage(1);
  }, [browser?.prefix, deferredSearchQuery]);

  React.useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  React.useEffect(() => {
    if (!browser || mode !== "files") {
      return;
    }

    const scopeKey = `${browser.bucket}:${normalizePrefix(rootPrefix)}`;
    if (explorerAutoExpandScopeRef.current === scopeKey) {
      return;
    }

    explorerAutoExpandScopeRef.current = scopeKey;
    if (expandedPrefixes.length > 0) {
      return;
    }

    expandExplorerPath(browser.prefix);
  }, [browser, expandExplorerPath, expandedPrefixes.length, mode, rootPrefix]);

  React.useEffect(() => {
    if (!browser || mode !== "files") {
      return;
    }

    const prefixesToWarm = [
      explorerRootPrefix,
      ...buildBreadcrumbSegments(browser.prefix, rootPrefix).map((segment) => segment.prefix)
    ];
    prefixesToWarm.forEach((prefix) => {
      void ensureExplorerDirectoryLoaded(prefix);
    });
  }, [browser, ensureExplorerDirectoryLoaded, explorerRootPrefix, mode, rootPrefix]);

  React.useEffect(() => {
    if (!activePreviewKey) {
      setPreviewError(null);
      return;
    }

    if (activePreviewEntry) {
      return;
    }

    setActivePreviewKey(null);
    setPreviewError(null);
  }, [activePreviewEntry, activePreviewKey]);

  React.useEffect(() => {
    if (!browser || !activePreviewEntry || !activePreviewKey) {
      return;
    }

    const previewCacheKey = buildObjectPreviewCacheKey(browser.bucket, activePreviewKey);
    if (previewCache[previewCacheKey]) {
      setPreviewError(null);
      return;
    }

    let cancelled = false;
    setLoadingPreviewKey(previewCacheKey);
    setPreviewError(null);

    getObjectStoreObjectPreview({
      bucket: browser.bucket,
      key: activePreviewEntry.key
    })
      .then((preview) => {
        if (cancelled) {
          return;
        }

        setPreviewCache((current) => ({
          ...current,
          [previewCacheKey]: preview
        }));
      })
      .catch((requestError) => {
        if (cancelled) {
          return;
        }

        setPreviewError(
          requestError instanceof Error ? requestError.message : "文件预览读取失败"
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingPreviewKey((current) => (current === previewCacheKey ? null : current));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activePreviewEntry, activePreviewKey, browser, previewCache]);

  React.useEffect(() => {
    if (!activePreview || activePreview.preview_kind !== "text") {
      lastTextPreviewObjectKeyRef.current = null;
      setDraftContent("");
      setFileViewMode("read");
      setCursorPosition({ line: 1, column: 1 });
      return;
    }

    const isSameObject = lastTextPreviewObjectKeyRef.current === activePreview.object_key;
    lastTextPreviewObjectKeyRef.current = activePreview.object_key;
    setDraftContent(activePreview.content ?? "");
    if (!isSameObject) {
      setFileViewMode("read");
      setCursorPosition({ line: 1, column: 1 });
    }
  }, [activePreview?.content, activePreview?.object_key, activePreview?.preview_kind]);

  React.useEffect(() => {
    const onMouseMove = (event: MouseEvent) => {
      if (!resizeStateRef.current) {
        return;
      }

      const nextWidth = resizeStateRef.current.startWidth + (event.clientX - resizeStateRef.current.startX);
      setExplorerPaneWidth(Math.max(280, Math.min(420, nextWidth)));
    };

    const onMouseUp = () => {
      resizeStateRef.current = null;
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  const updateUploadQueueItem = React.useCallback(
    (
      itemId: string,
      updater: Partial<UploadQueueItem> | ((item: UploadQueueItem) => UploadQueueItem)
    ) => {
      setUploadQueue((currentQueue) =>
        currentQueue.map((item) => {
          if (item.id !== itemId) {
            return item;
          }

          return typeof updater === "function" ? updater(item) : { ...item, ...updater };
        })
      );
    },
    []
  );

  const openDirectory = React.useCallback(
    (
      prefix: string | undefined,
      nextSelectedKey = "",
      options?: { revealTree?: boolean }
    ) => {
      if (!browser) {
        return;
      }

      if (options?.revealTree !== false && mode === "files") {
        expandExplorerPath(prefix);
      }
      setActivePreviewKey(null);
      setPreviewError(null);
      void loadBrowser(browser.bucket, prefix, nextSelectedKey);
    },
    [browser, expandExplorerPath, loadBrowser, mode]
  );

  const handleInteractExplorerDirectory = React.useCallback(
    async (prefix: string | undefined) => {
      const normalizedPrefix = normalizePrefix(prefix);
      const currentPrefix = normalizePrefix(browser?.prefix);
      const isCurrentDirectory = currentPrefix === normalizedPrefix;
      const isExpanded = expandedPrefixSet.has(normalizedPrefix);

      if (isCurrentDirectory) {
        if (activePreviewKey) {
          setSelectedKey("");
          setActivePreviewKey(null);
          setPreviewError(null);
          setFileViewMode("read");
          if (isExpanded) {
            setExplorerPrefixExpanded(normalizedPrefix, false);
            return;
          }

          setExplorerPrefixExpanded(normalizedPrefix, true);
          await ensureExplorerDirectoryLoaded(normalizedPrefix);
          return;
        }

        if (isExpanded) {
          setExplorerPrefixExpanded(normalizedPrefix, false);
          return;
        }

        setExplorerPrefixExpanded(normalizedPrefix, true);
        await ensureExplorerDirectoryLoaded(normalizedPrefix);
        return;
      }

      if (isExpanded) {
        setExplorerPrefixExpanded(normalizedPrefix, false);
        openDirectory(normalizedPrefix, "", { revealTree: false });
        return;
      }

      if (!isExpanded) {
        setExplorerPrefixExpanded(normalizedPrefix, true);
        await ensureExplorerDirectoryLoaded(normalizedPrefix);
      }

      openDirectory(normalizedPrefix);
    },
    [
      activePreviewKey,
      browser?.prefix,
      ensureExplorerDirectoryLoaded,
      expandedPrefixSet,
      openDirectory,
      setExplorerPrefixExpanded
    ]
  );

  const handleSelectObject = React.useCallback((entry: ObjectStoreObjectEntry) => {
    setSelectedKey(entry.key);
    setPreviewError(null);
    if (isPreviewableFile(entry.name)) {
      setActivePreviewKey(entry.key);
      return;
    }

    setActivePreviewKey(null);
  }, []);

  const handleSelectExplorerObject = React.useCallback(
    async (entry: ObjectStoreObjectEntry) => {
      if (!browser) {
        return;
      }

      const parentPrefix = buildObjectParentPrefix(entry.key);
      if (normalizePrefix(browser.prefix) !== parentPrefix) {
        await loadBrowser(browser.bucket, parentPrefix, entry.key);
      } else {
        setSelectedKey(entry.key);
      }

      setPreviewError(null);
      if (isPreviewableFile(entry.name)) {
        setActivePreviewKey(entry.key);
        return;
      }

      setActivePreviewKey(null);
    },
    [browser, loadBrowser]
  );

  const handlePanePathNavigate = React.useCallback(
    (segment: { kind: "directory" | "file"; prefix?: string; key?: string }) => {
      if (segment.kind === "file") {
        if (activePreviewEntry) {
          handleSelectObject(activePreviewEntry);
        }
        return;
      }

      openDirectory(segment.prefix, "", { revealTree: false });
    },
    [activePreviewEntry, handleSelectObject, openDirectory]
  );

  const startExplorerResize = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      resizeStateRef.current = {
        startX: event.clientX,
        startWidth: explorerPaneWidth
      };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [explorerPaneWidth]
  );

  const handleRefreshExplorer = React.useCallback(async () => {
    if (!browser || mode !== "files") {
      return;
    }

    const prefixesToRefresh = new Set<string>([explorerRootPrefix, browser.prefix]);
    expandedPrefixSet.forEach((prefix) => {
      prefixesToRefresh.add(normalizePrefix(prefix));
    });

    await Promise.all(
      Array.from(prefixesToRefresh).map((prefix) =>
        ensureExplorerDirectoryLoaded(prefix, { force: true })
      )
    );
    await loadBrowser(browser.bucket, browser.prefix, selectedKey);
  }, [
    browser,
    ensureExplorerDirectoryLoaded,
    expandedPrefixSet,
    explorerRootPrefix,
    loadBrowser,
    mode,
    selectedKey
  ]);

  const handleCollapseExplorerTree = React.useCallback(() => {
    setExpandedPrefixes([]);
  }, []);

  const handleSaveTextFile = React.useCallback(
    async (contentOverride?: string) => {
      if (
        savingDraft ||
        !browser ||
        !activePreviewEntry ||
        !activePreview ||
        activePreview.preview_kind !== "text" ||
        activePreview.truncated
      ) {
        return;
      }

      const nextContent = contentOverride ?? draftContent;
      if (nextContent === (activePreview.content ?? "")) {
        return;
      }

      setSavingDraft(true);
      setPreviewError(null);
      try {
        await updateObjectStoreTextFile({
          bucket: browser.bucket,
          objectKey: activePreviewEntry.key,
          content: nextContent,
          contentType: activePreview.content_type
        });
        const contentBytes = new TextEncoder().encode(nextContent).length;
        setPreviewCache((current) => ({
          ...current,
          [buildObjectPreviewCacheKey(browser.bucket, activePreviewEntry.key)]: {
            ...activePreview,
            content: nextContent,
            truncated: false,
            content_bytes: contentBytes
          }
        }));
        await loadBrowser(browser.bucket, browser.prefix, activePreviewEntry.key);
      } catch (requestError) {
        setPreviewError(requestError instanceof Error ? requestError.message : "保存文件失败");
      } finally {
        setSavingDraft(false);
      }
    },
    [activePreview, activePreviewEntry, browser, draftContent, loadBrowser, savingDraft]
  );

  const handleSwitchToReadMode = React.useCallback(() => {
    if (isActiveTextDraftDirty) {
      void handleSaveTextFile(draftContent);
    }
    setFileViewMode("read");
  }, [draftContent, handleSaveTextFile, isActiveTextDraftDirty]);

  React.useEffect(() => {
    if (
      fileViewMode !== "edit" ||
      !canEditActiveTextFile ||
      !isActiveTextDraftDirty ||
      savingDraft
    ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void handleSaveTextFile(draftContent);
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [
    canEditActiveTextFile,
    draftContent,
    fileViewMode,
    handleSaveTextFile,
    isActiveTextDraftDirty,
    savingDraft
  ]);

  async function handleCopyPreviewContent() {
    const content =
      fileViewMode === "edit" || isActiveTextDraftDirty ? draftContent : activePreviewTextContent;
    if (!content) {
      return;
    }

    await handleCopy(content, "已复制文件内容");
  }

  function handleDownloadPreviewFile() {
    if (!browser || !activePreviewEntry) {
      return;
    }

    triggerObjectDownload(
      getObjectStoreDownloadUrl({
        bucket: browser.bucket,
        key: activePreviewEntry.key
      })
    );
  }

  async function handleUpload(files: FileList | File[]) {
    if (!browser || mode !== "files") {
      return;
    }

    const uploadItems = Array.from(files);
    if (uploadItems.length === 0) {
      return;
    }

    setUploading(true);
    setNotice(null);
    setError(null);
    const nextUploadQueue = uploadItems.map((file, index) => ({
      id: buildUploadQueueItemId(file, index),
      label: buildUploadFileLabel(file),
      sizeBytes: file.size,
      uploadedBytes: 0,
      status: "queued" as const,
      error: null
    }));
    setUploadPanelCollapsed(false);
    setUploadQueue(nextUploadQueue);
    let latestKey = selectedKey;
    const targetPrefix = normalizePrefix(pendingUploadPrefix ?? browser.prefix) || browser.prefix;
    const relativePrefix = toRelativePrefix(targetPrefix, rootPrefix);
    let currentQueueItemId: string | null = null;

    try {
      for (const [index, file] of uploadItems.entries()) {
        const relativePath = getRelativeUploadPath(file);
        const queueItem = nextUploadQueue[index];
        currentQueueItemId = queueItem.id;
        updateUploadQueueItem(queueItem.id, {
          status: "preparing",
          uploadedBytes: 0,
          error: null
        });

        const response = await uploadFileToObjectStore({
          bucket: browser.bucket,
          file,
          prefix: relativePrefix || undefined,
          relativePath: relativePath ?? undefined,
          onProgress: ({ status, uploadedBytes }) => {
            updateUploadQueueItem(queueItem.id, (item) => ({
              ...item,
              status,
              uploadedBytes: Math.min(item.sizeBytes, uploadedBytes),
              error: null
            }));
          }
        });

        latestKey = response.object_key;
        updateUploadQueueItem(queueItem.id, {
          status: "completed",
          uploadedBytes: file.size,
          error: null
        });
        currentQueueItemId = null;
      }

      setNotice(buildUploadNotice(uploadItems));
      await loadBrowser(browser.bucket, targetPrefix, latestKey);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "上传文件失败";
      if (currentQueueItemId) {
        updateUploadQueueItem(currentQueueItemId, (item) => ({
          ...item,
          status: "failed",
          error: message
        }));
      }
      setError(message);
    } finally {
      setUploading(false);
      setPendingUploadPrefix(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (folderInputRef.current) {
        folderInputRef.current.value = "";
      }
    }
  }

  const normalizedFolderDraft = normalizeFolderNameInput(folderDraft);

  async function handleCreateFolder(folderNameInput = folderDraft) {
    if (!browser || mode !== "files") {
      return;
    }

    const folderName = normalizeFolderNameInput(folderNameInput);
    if (!folderName) {
      setFolderDialogError("文件夹名称不能为空");
      return;
    }
    if (folderName === "." || folderName === ".." || folderName.includes("/")) {
      setFolderDialogError("文件夹名称不合法");
      return;
    }

    setCreatingFolder(true);
    setNotice(null);
    setError(null);
    setFolderDialogError(null);

    try {
      const targetPrefix = normalizePrefix(createFolderPrefix || browser.prefix) || browser.prefix;
      await createManagedFolder({
        name: folderName,
        bucket: browser.bucket,
        prefix: toRelativePrefix(targetPrefix, rootPrefix)
      });
      setNotice(`已创建文件夹 ${folderName}`);
      setFolderDraft("");
      setCreateFolderOpen(false);
      await loadBrowser(browser.bucket, targetPrefix, "");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "创建文件夹失败";
      setFolderDialogError(message);
    } finally {
      setCreatingFolder(false);
    }
  }

  async function handleDelete(entry: ObjectStoreObjectEntry) {
    if (!browser || mode !== "files") {
      return;
    }

    const confirmed = window.confirm(`确认删除 ${entry.name} 吗？该操作会直接删除对象存储中的文件。`);
    if (!confirmed) {
      return;
    }

    setDeletingKey(entry.key);
    setNotice(null);
    setError(null);
    try {
      await deleteObjectStoreObject({
        bucket: browser.bucket,
        key: entry.key
      });
      setNotice(`已删除 ${entry.name}`);
      await loadBrowser(browser.bucket, browser.prefix, "");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "删除文件失败";
      setError(message);
    } finally {
      setDeletingKey(null);
    }
  }

  async function handleDeletePrefix(prefix: string, label: string) {
    if (!browser || mode !== "files") {
      return;
    }

    const normalizedPrefix = normalizePrefix(prefix);
    if (!normalizedPrefix || normalizedPrefix === explorerRootPrefix) {
      setError("根目录不允许删除");
      return;
    }

    const confirmed = window.confirm(
      `确认删除文件夹 ${label} 吗？该操作会删除目录下的所有文件和子目录。`
    );
    if (!confirmed) {
      return;
    }

    setDeletingKey(normalizedPrefix);
    setNotice(null);
    setError(null);

    try {
      await deleteObjectStorePrefix({
        bucket: browser.bucket,
        prefix: normalizedPrefix
      });

      const currentPrefix = normalizePrefix(browser.prefix);
      const nextPrefix = currentPrefix.startsWith(normalizedPrefix)
        ? buildDirectoryParentPrefix(normalizedPrefix, explorerRootPrefix)
        : browser.prefix;

      setExplorerDirectoryCache((current) =>
        Object.fromEntries(
          Object.entries(current).filter(([, value]) => !value.prefix.startsWith(normalizedPrefix))
        )
      );
      setExpandedPrefixes((current) =>
        current.filter((value) => !normalizePrefix(value).startsWith(normalizedPrefix))
      );
      setSelectedKey((current) => (current.startsWith(normalizedPrefix) ? "" : current));
      setActivePreviewKey((current) =>
        current && current.startsWith(normalizedPrefix) ? null : current
      );
      setPreviewError(null);

      setNotice(`已删除文件夹 ${label} 及其全部内容`);
      await loadBrowser(browser.bucket, nextPrefix, "");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "删除文件夹失败";
      setError(message);
    } finally {
      setDeletingKey(null);
    }
  }

  async function handleCopy(value: string, successMessage: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice(successMessage);
    } catch {
      setError("复制失败，请检查浏览器权限");
    }
  }

  function openCreateFolderDialog(prefix = browser?.prefix ?? rootPrefix ?? "") {
    setError(null);
    setFolderDraft("");
    setFolderDialogError(null);
    setCreateFolderPrefix(normalizePrefix(prefix));
    setCreateFolderOpen(true);
  }

  function openUploadPicker(prefix = browser?.prefix ?? rootPrefix ?? "") {
    setPendingUploadPrefix(normalizePrefix(prefix));
    fileInputRef.current?.click();
  }

  function openFolderUploadPicker(prefix = browser?.prefix ?? rootPrefix ?? "") {
    setPendingUploadPrefix(normalizePrefix(prefix));
    folderInputRef.current?.click();
  }

  function renderTreeActions(prefix: string) {
    if (!browser || mode !== "files") {
      return null;
    }

    const normalizedPrefix = normalizePrefix(prefix) || normalizePrefix(rootPrefix) || browser.prefix;
    const canDeleteDirectory = normalizedPrefix !== explorerRootPrefix;

    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            aria-label="目录操作"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
            title="目录操作"
            type="button"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[200px] rounded-xl border-zinc-800 bg-zinc-950 p-1.5 text-zinc-100">
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => openCreateFolderDialog(normalizedPrefix)}
          >
            <Plus className="h-4 w-4 text-zinc-500" />
            Create folder
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => openUploadPicker(normalizedPrefix)}
          >
            <UploadCloud className="h-4 w-4 text-zinc-500" />
            Upload files
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => openFolderUploadPicker(normalizedPrefix)}
          >
            <FolderOpen className="h-4 w-4 text-zinc-500" />
            Upload folder
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() =>
              void handleCopy(
                `${window.location.origin}${buildConsoleHref("/files", {
                  prefix: normalizedPrefix
                })}`,
                "已复制目录链接"
              )
            }
          >
            <Copy className="h-4 w-4 text-zinc-500" />
            Copy link
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => void loadBrowser(browser.bucket, normalizedPrefix, "")}
          >
            <RefreshCw className="h-4 w-4 text-zinc-500" />
            Refresh
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            disabled={!canDeleteDirectory}
            onSelect={() => void handleDeletePrefix(normalizedPrefix, labelForPrefix(normalizedPrefix))}
          >
            <Trash2 className="h-4 w-4 text-zinc-500" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  function renderExplorerTree(prefix: string, label: string, depth: number) {
    if (!browser || mode !== "files") {
      return null;
    }

    const normalizedPrefix = normalizePrefix(prefix);
    const cacheKey = buildExplorerDirectoryCacheKey(browser.bucket, normalizedPrefix);
    const cacheEntry = explorerDirectoryCache[cacheKey] ?? null;
    const expanded = expandedPrefixSet.has(normalizedPrefix);
    const loadingChildren = Boolean(loadingExplorerPrefixes[cacheKey]);
    const directoryActive =
      normalizePrefix(browser.prefix) === normalizedPrefix && !selectedExplorerKey;

    return (
      <React.Fragment key={cacheKey}>
        <ExplorerNode
          active={directoryActive}
          actions={renderTreeActions(normalizedPrefix)}
          expanded={expanded}
          icon={expanded ? <FolderOpen className="h-4 w-4" /> : <Folder className="h-4 w-4" />}
          indent={depth}
          label={label}
          loading={loadingChildren}
          onClick={() => void handleInteractExplorerDirectory(normalizedPrefix)}
        />

        {expanded ? (
          <div className="space-y-0.5">
            {cacheEntry?.prefixes.map((entry) =>
              renderExplorerTree(entry.prefix, entry.name, depth + 1)
            )}

            {cacheEntry?.objects.map((entry) => (
              <ExplorerNode
                active={entry.key === selectedExplorerKey}
                caret={false}
                icon={inferObjectType(entry.name).icon}
                indent={depth + 1}
                key={`${cacheKey}:${entry.key}`}
                label={entry.name}
                onClick={() => void handleSelectExplorerObject(entry)}
              />
            ))}

            {!loadingChildren &&
            cacheEntry &&
            cacheEntry.prefixes.length === 0 &&
            cacheEntry.objects.length === 0 ? (
              <div
                className="px-2 py-1.5 text-sm text-zinc-500"
                style={{ paddingLeft: `${43 + depth * 17}px` }}
              >
                No data
              </div>
            ) : null}
          </div>
        ) : null}
      </React.Fragment>
    );
  }

  function renderPaneActionsMenu() {
    if (!browser || mode !== "files") {
      return null;
    }

    if (showPreviewPane && activePreviewEntry) {
      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className="h-8 rounded-full border-zinc-700 bg-transparent px-3 text-xs text-zinc-200 hover:bg-zinc-800 hover:text-white"
              type="button"
              variant="outline"
            >
              Actions
              <ChevronDown className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[200px] rounded-xl border-zinc-800 bg-zinc-950 p-1.5 text-zinc-100">
            <DropdownMenuItem
              className="rounded-lg"
              onSelect={() =>
                window.open(
                  getObjectStoreDownloadUrl({
                    bucket: browser.bucket,
                    key: activePreviewEntry.key,
                    disposition: "inline"
                  }),
                  "_blank",
                  "noopener,noreferrer"
                )
              }
            >
              <ExternalLink className="h-4 w-4 text-zinc-500" />
              Open raw
            </DropdownMenuItem>
            <DropdownMenuItem
              className="rounded-lg"
              onSelect={() =>
                triggerObjectDownload(
                  getObjectStoreDownloadUrl({
                    bucket: browser.bucket,
                    key: activePreviewEntry.key
                  })
                )
              }
            >
              <Download className="h-4 w-4 text-zinc-500" />
              Download
            </DropdownMenuItem>
            <DropdownMenuItem
              className="rounded-lg"
              onSelect={() => void handleDelete(activePreviewEntry)}
            >
              <Trash2 className="h-4 w-4 text-zinc-500" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      );
    }

    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            className="h-8 rounded-full border-zinc-700 bg-transparent px-3 text-xs text-zinc-200 hover:bg-zinc-800 hover:text-white"
            type="button"
            variant="outline"
          >
            Actions
            <ChevronDown className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[220px] rounded-xl border-zinc-800 bg-zinc-950 p-1.5 text-zinc-100">
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => browser && void loadBrowser(browser.bucket, browser.prefix, selectedKey)}
          >
            <RefreshCw className="h-4 w-4 text-zinc-500" />
            Refresh
          </DropdownMenuItem>
          <DropdownMenuItem className="rounded-lg" onSelect={() => openCreateFolderDialog()}>
            <Plus className="h-4 w-4 text-zinc-500" />
            New folder
          </DropdownMenuItem>
          <DropdownMenuItem className="rounded-lg" onSelect={() => openUploadPicker()}>
            <UploadCloud className="h-4 w-4 text-zinc-500" />
            Upload file
          </DropdownMenuItem>
          <DropdownMenuItem className="rounded-lg" onSelect={() => openFolderUploadPicker()}>
            <FolderOpen className="h-4 w-4 text-zinc-500" />
            Upload folder
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            disabled={!selectedEntry}
            onSelect={() => {
              if (selectedEntry) {
                void handleDelete(selectedEntry);
              }
            }}
          >
            <Trash2 className="h-4 w-4 text-zinc-500" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  function renderDirectoryRowActions(entry: {
    kind: "prefix";
    prefix: string;
    name: string;
  }) {
    if (!browser) {
      return null;
    }

    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            aria-label={`${entry.name} 操作`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
            type="button"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="min-w-[180px] rounded-xl border-zinc-800 bg-zinc-950 p-1.5 text-zinc-100"
        >
          <DropdownMenuItem className="rounded-lg" onSelect={() => openDirectory(entry.prefix)}>
            <FolderOpen className="h-4 w-4 text-zinc-500" />
            Open
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() =>
              void handleCopy(
                `${window.location.origin}${buildConsoleHref("/files", {
                  prefix: entry.prefix
                })}`,
                "已复制目录链接"
              )
            }
          >
            <Copy className="h-4 w-4 text-zinc-500" />
            Copy link
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() => void handleDeletePrefix(entry.prefix, entry.name)}
          >
            <Trash2 className="h-4 w-4 text-zinc-500" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  function renderObjectRowActions(entry: ObjectStoreObjectEntry) {
    if (!browser) {
      return null;
    }

    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            aria-label={`${entry.name} 操作`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
            type="button"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="min-w-[200px] rounded-xl border-zinc-800 bg-zinc-950 p-1.5 text-zinc-100"
        >
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() =>
              window.open(
                getObjectStoreDownloadUrl({
                  bucket: browser.bucket,
                  key: entry.key,
                  disposition: "inline"
                }),
                "_blank",
                "noopener,noreferrer"
              )
            }
          >
            <ExternalLink className="h-4 w-4 text-zinc-500" />
            Open raw
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() =>
              triggerObjectDownload(
                getObjectStoreDownloadUrl({
                  bucket: browser.bucket,
                  key: entry.key
                })
              )
            }
          >
            <Download className="h-4 w-4 text-zinc-500" />
            Download
          </DropdownMenuItem>
          <DropdownMenuItem
            className="rounded-lg"
            onSelect={() =>
              void handleCopy(
                getObjectStoreDownloadUrl({
                  bucket: browser.bucket,
                  key: entry.key,
                  disposition: "inline"
                }),
                "已复制文件链接"
              )
            }
          >
            <Copy className="h-4 w-4 text-zinc-500" />
            Copy link
          </DropdownMenuItem>
          <DropdownMenuItem className="rounded-lg" onSelect={() => void handleDelete(entry)}>
            <Trash2 className="h-4 w-4 text-zinc-500" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  if (mode === "files") {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        {notice ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div
          className="console-workbench-split min-h-0 flex-1 border-r-0"
          style={{ borderTopRightRadius: 0 }}
        >
          <Card
            className="flex min-h-0 flex-col overflow-hidden rounded-none border-0 border-r border-slate-800/70 bg-transparent shadow-none"
            style={{ width: explorerPaneWidth }}
          >
            <CardHeader className="border-b border-slate-800/70 bg-transparent px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[13px] font-medium text-zinc-100">Files</div>
                <div className="flex gap-2">
                  <button
                    aria-label="Refresh tree"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                    disabled={loading || !browser}
                    onClick={() => void handleRefreshExplorer()}
                    title="Refresh tree"
                    type="button"
                  >
                    <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
                  </button>
                  <button
                    aria-label="Collapse tree"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                    disabled={!browser}
                    onClick={handleCollapseExplorerTree}
                    title="Collapse tree"
                    type="button"
                  >
                    <PanelLeftClose className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              <div className="min-h-0 flex-1 overflow-y-auto px-2 py-1.5">
                {browser ? renderExplorerTree(explorerRootPrefix, "Shared", 0) : null}
              </div>
            </CardContent>
          </Card>

          <div
            className="relative w-2 shrink-0 cursor-col-resize bg-transparent before:absolute before:bottom-0 before:left-1/2 before:top-0 before:w-px before:-translate-x-1/2 before:bg-slate-800/80"
            onMouseDown={startExplorerResize}
            role="presentation"
          />

          <Card
            className={cn(
              "flex min-h-0 flex-1 flex-col overflow-hidden rounded-none border-0 bg-transparent shadow-none",
              draggingFiles && "ring-2 ring-sky-500/30"
            )}
            onDragEnter={(event) => {
              event.preventDefault();
              setDraggingFiles(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              const currentTarget = event.currentTarget;
              const relatedTarget = event.relatedTarget;
              if (relatedTarget instanceof Node && currentTarget.contains(relatedTarget)) {
                return;
              }
              setDraggingFiles(false);
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              setDraggingFiles(false);
              if (event.dataTransfer.files) {
                void handleUpload(event.dataTransfer.files);
              }
            }}
          >
            <CardHeader
              className={cn(
                "bg-transparent px-3.5 pt-2.5",
                showPreviewPane ? "border-b-0 pb-2" : "border-b-0 py-2.5"
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-1 text-xs font-medium text-zinc-400">
                    {panePathSegments.map((segment, index) => (
                      <React.Fragment key={segment.kind === "file" ? `file:${segment.key}` : `dir:${segment.prefix}`}>
                        {index > 0 ? <ChevronRight className="h-3.5 w-3.5 text-zinc-600" /> : null}
                        <button
                          className="rounded-md px-1.5 py-0.5 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
                          onClick={() => handlePanePathNavigate(segment)}
                          type="button"
                        >
                          {segment.label}
                        </button>
                      </React.Fragment>
                    ))}
                  </div>
                  <CardTitle className="text-base text-zinc-100">
                    {showPreviewPane && activePreviewEntry ? activePreviewEntry.name : currentDirectoryTitle}
                  </CardTitle>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    aria-label="View details"
                    className={cn(
                      "inline-flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white",
                      showInspector && "bg-zinc-800 text-white"
                    )}
                    onClick={() => setShowInspector((value) => !value)}
                    type="button"
                  >
                    <Info className="h-4 w-4" />
                  </button>
                  <button
                    aria-label="Copy link"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                    onClick={() =>
                      void handleCopy(
                        showPreviewPane && activePreviewEntry
                          ? getObjectStoreDownloadUrl({
                              bucket: browser?.bucket ?? "",
                              key: activePreviewEntry.key,
                              disposition: "inline"
                            })
                          : `${window.location.origin}${buildConsoleHref("/files", {
                              prefix: browser?.prefix
                            })}`,
                        showPreviewPane ? "已复制文件链接" : "已复制当前目录链接"
                      )
                    }
                    type="button"
                  >
                    <Link2 className="h-4 w-4" />
                  </button>
                  {renderPaneActionsMenu()}
                  {showPreviewPane && activePreviewEntry ? (
                    <>
                      <div className="inline-flex items-center rounded-full border border-zinc-800 bg-[rgba(15,20,28,0.86)] p-1">
                        <Button
                          className={cn(
                            "h-7 rounded-full border-0 px-3 text-xs shadow-none",
                            fileViewMode === "read"
                              ? "bg-zinc-100 text-zinc-950 hover:bg-zinc-200"
                              : "bg-transparent text-zinc-300 hover:bg-zinc-800 hover:text-white"
                          )}
                          onClick={handleSwitchToReadMode}
                          type="button"
                          variant="outline"
                        >
                          Read-only
                        </Button>
                        <Button
                          className={cn(
                            "h-7 rounded-full border-0 px-3 text-xs shadow-none",
                            fileViewMode === "edit"
                              ? "bg-zinc-100 text-zinc-950 hover:bg-zinc-200"
                              : "bg-transparent text-zinc-300 hover:bg-zinc-800 hover:text-white"
                          )}
                          disabled={!canEditActiveTextFile || savingDraft}
                          onClick={() => setFileViewMode("edit")}
                          type="button"
                          variant="outline"
                        >
                          Edit
                        </Button>
                      </div>
                    </>
                  ) : null}
                </div>
              </div>

              {!showPreviewPane ? (
                <div className="mt-2.5">
                  <div className="relative min-w-[260px] max-w-full">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
                    <Input
                      className={cn(
                        consoleListSearchInputClassName,
                        "h-8 border-slate-700/80 bg-[rgba(12,18,25,0.72)] text-[13px]"
                      )}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Filter"
                      value={searchQuery}
                    />
                  </div>
                </div>
              ) : null}

              {showInspector ? (
                <div className="mt-3 grid gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-300 md:grid-cols-3">
                  {showPreviewPane && activePreviewEntry && browser ? (
                    <>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">对象路径</div>
                        <div className="break-all text-sm leading-6 text-zinc-100">
                          {`s3://${browser.bucket}/${activePreviewEntry.key}`}
                        </div>
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">文件大小</div>
                        <div className="text-sm leading-6 text-zinc-100">
                          {formatFileSize(activePreviewEntry.size_bytes)}
                        </div>
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">更新时间</div>
                        <div className="text-sm leading-6 text-zinc-100">
                          {formatTimestamp(activePreviewEntry.last_modified)}
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">当前位置</div>
                        <div className="text-sm leading-6 text-zinc-100">{filesDirectoryLocation}</div>
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">当前条目</div>
                        <div className="text-sm leading-6 text-zinc-100">{totalEntries}</div>
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs uppercase tracking-[0.14em] text-zinc-500">可见大小</div>
                        <div className="text-sm leading-6 text-zinc-100">{formatFileSize(visibleObjectSize)}</div>
                      </div>
                    </>
                  )}
                </div>
              ) : null}

              <input
                className="hidden"
                multiple
                onChange={(event) => {
                  if (event.target.files) {
                    void handleUpload(event.target.files);
                  }
                }}
                ref={fileInputRef}
                type="file"
              />
              <input
                className="hidden"
                multiple
                onChange={(event) => {
                  if (event.target.files) {
                    void handleUpload(event.target.files);
                  }
                }}
                ref={folderInputRef}
                type="file"
              />
            </CardHeader>

            <CardContent className="flex min-h-0 flex-1 flex-col p-0">
              {showPreviewPane && activePreviewEntry && browser ? (
                <FilePreviewPane
                  cursorPosition={cursorPosition}
                  draftContent={draftContent}
                  dirty={isActiveTextDraftDirty}
                  entry={activePreviewEntry}
                  onCommitDraft={() => void handleSaveTextFile(draftContent)}
                  mode={fileViewMode}
                  onCopyContent={() => void handleCopyPreviewContent()}
                  onDraftChange={setDraftContent}
                  onDownload={handleDownloadPreviewFile}
                  onSelectionChange={setCursorPosition}
                  onToggleWrapLines={() => setWrapPreviewLines((value) => !value)}
                  preview={activePreview}
                  previewUrl={getObjectStoreDownloadUrl({
                    bucket: browser.bucket,
                    key: activePreviewEntry.key,
                    disposition: "inline"
                  })}
                  loading={loadingPreviewKey === activePreviewCacheKey && !activePreview}
                  previewError={previewError}
                  saving={savingDraft}
                  wrapLines={wrapPreviewLines}
                />
              ) : (
                <>
                  <div className="grid grid-cols-[minmax(0,1.8fr)_120px_120px_180px_44px] border-b border-slate-800/70 bg-transparent px-5 py-2.5 text-xs font-medium text-zinc-500">
                    <div className="flex items-center gap-1">
                      Name
                      <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />
                    </div>
                    <div>Type</div>
                    <div>Size</div>
                    <div>Last updated (UTC+08:00)</div>
                    <div />
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto">
                    {pagedEntries.map((entry) =>
                      entry.kind === "prefix" ? (
                        <FileTableRow
                          actions={renderDirectoryRowActions(entry)}
                          icon={<Folder className="h-4 w-4 text-zinc-600" />}
                          key={entry.id}
                          name={entry.name}
                          onClick={() => openDirectory(entry.prefix)}
                          typeLabel="Folder"
                        />
                      ) : (
                        <FileTableRow
                          active={entry.object.key === selectedKey}
                          actions={renderObjectRowActions(entry.object)}
                          icon={inferObjectType(entry.object.name).icon}
                          key={entry.id}
                          name={entry.object.name}
                          onClick={() => handleSelectObject(entry.object)}
                          typeLabel={inferObjectType(entry.object.name).label}
                          sizeLabel={formatFileSize(entry.object.size_bytes)}
                          updatedAt={formatTimestamp(entry.object.last_modified)}
                        />
                      )
                    )}

                    {!loading && !error && totalEntries === 0 ? (
                      <div className="flex min-h-full min-h-[240px] flex-col items-center justify-center px-6 py-10 text-center">
                        <div className="text-sm font-medium text-zinc-100">
                          {deferredSearchQuery ? "No matching objects" : "No objects"}
                        </div>
                        <p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">
                          {deferredSearchQuery
                            ? "Try another filter."
                            : "Use Actions to upload files or create folders."}
                        </p>
                      </div>
                    ) : null}

                    {loading ? (
                      <div className="flex min-h-full min-h-[320px] items-center justify-center gap-2 px-6 py-10 text-sm text-zinc-500">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        正在加载对象列表...
                      </div>
                    ) : null}
                  </div>

                  {totalEntries > 0 ? (
                    <div className="flex flex-wrap items-center justify-end gap-5 bg-transparent px-5 pb-3 pt-2 text-xs text-zinc-500">
                      <div className="flex items-center gap-3">
                        <span>Rows per page:</span>
                        <span className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-zinc-200">
                          {pageSize}
                          <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
                        </span>
                        <span>
                          {pageStart}–{pageEnd} of {totalEntries}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          aria-label="Go to previous page"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={currentPage <= 1}
                          onClick={() => setPage((value) => Math.max(1, value - 1))}
                          type="button"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </button>
                        <button
                          aria-label="Go to next page"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={currentPage >= totalPages}
                          onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                          type="button"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {uploadQueueSummary ? (
          <div className="pointer-events-none fixed bottom-4 right-4 z-50 w-[min(28rem,calc(100vw-1.5rem))] sm:bottom-6 sm:right-6 sm:w-[24rem]">
            <Card className="pointer-events-auto overflow-hidden border-zinc-200 bg-white/96 shadow-[0_24px_80px_rgba(24,24,27,0.18)] backdrop-blur">
              <CardHeader className="space-y-0 border-b border-zinc-200 bg-zinc-50/80 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="text-sm font-semibold text-zinc-950">上传</CardTitle>
                    <CardDescription className="mt-1 text-xs leading-5 text-zinc-600">
                      {buildUploadQueueSummaryLabel(uploadQueueSummary)}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      className="h-7 w-7 rounded-md p-0 text-zinc-500"
                      onClick={() => setUploadPanelCollapsed((value) => !value)}
                      type="button"
                      variant="ghost"
                    >
                      <ChevronDown className={cn("h-4 w-4 transition-transform", uploadPanelCollapsed && "-rotate-90")} />
                    </Button>
                    {!uploading ? (
                      <Button
                        className="h-7 w-7 rounded-md p-0 text-zinc-500"
                        onClick={() => setUploadQueue([])}
                        type="button"
                        variant="ghost"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    ) : null}
                  </div>
                </div>

                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between gap-3 text-xs text-zinc-600">
                    <span className="truncate">
                      {uploadQueueSummary.activeItem
                        ? `${renderUploadQueueStatusLabel(uploadQueueSummary.activeItem.status)} · ${uploadQueueSummary.activeItem.label}`
                        : "等待上传"}
                    </span>
                    <span className="shrink-0 font-medium text-zinc-900">
                      {formatUploadPercent(uploadQueueSummary.uploadedBytes, uploadQueueSummary.totalBytes)}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
                    <div
                      className="h-full rounded-full bg-sky-600 transition-[width] duration-150"
                      style={{ width: `${calculateUploadPercent(uploadQueueSummary.uploadedBytes, uploadQueueSummary.totalBytes)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3 text-xs text-zinc-500">
                    <span>
                      {uploadQueueSummary.completedFiles}/{uploadQueueSummary.totalFiles} 个文件
                    </span>
                    <span>
                      {formatFileSize(uploadQueueSummary.uploadedBytes)} / {formatFileSize(uploadQueueSummary.totalBytes)}
                    </span>
                  </div>
                </div>
              </CardHeader>

              {!uploadPanelCollapsed ? (
                <CardContent className="max-h-80 space-y-2 overflow-y-auto px-4 py-3">
                  {uploadQueue.map((item) => (
                    <UploadQueueRow item={item} key={item.id} />
                  ))}
                </CardContent>
              ) : null}
            </Card>
          </div>
        ) : null}

        <Dialog
          onOpenChange={(open) => {
            setCreateFolderOpen(open);
            if (!open) {
              setFolderDraft("");
              setFolderDialogError(null);
            }
          }}
          open={createFolderOpen}
        >
          <DialogContent className="max-w-[460px] gap-0 overflow-hidden p-0">
            <div className="border-b border-zinc-200 bg-[linear-gradient(180deg,rgba(244,244,245,0.95),rgba(255,255,255,1))] px-5 py-4">
              <div className="mb-2 inline-flex items-center rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-500">
                Files
              </div>
              <DialogHeader className="space-y-1">
                <DialogTitle>New folder</DialogTitle>
                <DialogDescription>
                  在 {createFolderLocation} 下创建一个新目录。
                </DialogDescription>
              </DialogHeader>
            </div>

            <form
              className="space-y-5 px-5 py-5"
              onSubmit={(event) => {
                event.preventDefault();
                void handleCreateFolder();
              }}
            >
              <div className="space-y-2">
                <Label className="text-[13px] font-medium text-zinc-700" htmlFor="new-folder-name">
                  Folder name
                </Label>
                <Input
                  autoFocus
                  className="h-11 rounded-lg border-zinc-200 bg-white text-sm"
                  id="new-folder-name"
                  onChange={(event) => setFolderDraft(event.target.value)}
                  placeholder="例如：raw-html、reports、2026-03"
                  value={folderDraft}
                />
                <div className="flex items-center justify-between gap-3 text-xs text-zinc-500">
                  <span>仅支持单层目录名称，不支持 `/`。</span>
                  <span className="rounded-md bg-zinc-100 px-2 py-1 text-zinc-600">
                    {normalizedFolderDraft || "未命名"}
                  </span>
                </div>
                {folderDialogError ? (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {folderDialogError}
                  </div>
                ) : null}
              </div>

              <DialogFooter className="border-t border-zinc-100 pt-4">
                <Button
                  onClick={() => {
                    setCreateFolderOpen(false);
                    setFolderDraft("");
                    setFolderDialogError(null);
                  }}
                  type="button"
                  variant="outline"
                >
                  取消
                </Button>
                <Button
                  className="rounded-md bg-zinc-950 text-white hover:bg-zinc-800"
                  disabled={creatingFolder || !normalizedFolderDraft}
                  type="submit"
                >
                  {creatingFolder ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  创建文件夹
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b border-zinc-200 bg-zinc-50/50">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <CardTitle className="text-base">Data 对象存储浏览器</CardTitle>
                <CardDescription className="max-w-3xl leading-6">
                  直接查看 bucket / prefix / key 结构，用于确认 Files、数据集和其他任务产物在对象存储中的真实落点。
                </CardDescription>
              </div>

              {browser ? (
                <div className="flex flex-wrap gap-2">
                  {rootPrefix ? (
                    <Link
                      className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 text-sm text-zinc-700 transition-colors hover:bg-zinc-50"
                      href={buildConsoleHref("/files", {
                        bucket: browser.bucket,
                        prefix: browser.prefix
                      })}
                    >
                      <HardDrive className="h-4 w-4" />
                      尝试在 Files 打开
                      <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  ) : null}
                  <Button
                    className="rounded-md"
                    disabled={loading}
                    onClick={() => void loadBrowser(browser.bucket, browser.prefix, selectedKey)}
                    type="button"
                    variant="outline"
                  >
                    <RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />
                    刷新
                  </Button>
                </div>
              ) : null}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Select
                onValueChange={(value) => {
                  setNotice(null);
                  void loadBrowser(value, "", "");
                }}
                value={browser?.bucket ?? initialBucket ?? undefined}
              >
                <SelectTrigger className={cn(consoleListFilterTriggerClassName, "min-w-[220px]")}>
                  <SelectValue placeholder="选择 bucket" />
                </SelectTrigger>
                <SelectContent>
                  {(browser?.buckets ?? []).map((bucket) => (
                    <SelectItem key={bucket} value={bucket}>
                      {bucket}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="relative min-w-[220px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
                <Input
                  className={cn(consoleListSearchInputClassName, "h-8 pl-9")}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="搜索对象名、key 或目录"
                  value={searchQuery}
                />
              </div>

              {rootPrefix ? (
                <Badge className="rounded-sm" variant="outline">
                  Root · {trimTrailingSlash(rootPrefix)}
                </Badge>
              ) : null}
            </div>

            {browser ? (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                <BreadcrumbButton
                  label={browser.bucket}
                  onClick={() => void loadBrowser(browser.bucket, "", "")}
                />
                {buildBreadcrumbSegments(browser.prefix, rootPrefix).map((segment) => (
                  <React.Fragment key={segment.prefix}>
                    <span>/</span>
                    <BreadcrumbButton
                      label={segment.label}
                      onClick={() => void loadBrowser(browser.bucket, segment.prefix, "")}
                    />
                  </React.Fragment>
                ))}
              </div>
            ) : null}
          </CardHeader>

          <CardContent className="p-0">
            {notice ? (
              <div className="border-b border-emerald-200 bg-emerald-50 px-5 py-3 text-sm text-emerald-700">
                {notice}
              </div>
            ) : null}

            {error ? (
              <div className="border-b border-rose-200 bg-rose-50 px-5 py-3 text-sm text-rose-700">
                {error}
              </div>
            ) : null}

            <div className="grid grid-cols-[minmax(0,1.6fr)_110px_120px_150px_148px] border-b border-zinc-200 bg-zinc-50 px-5 py-3 text-xs font-medium text-zinc-500">
              <div>名称</div>
              <div>类型</div>
              <div>大小</div>
              <div>更新时间</div>
              <div>操作</div>
            </div>

            <div className="max-h-[720px] overflow-y-auto">
              {browser?.parent_prefix ? (
                <ObjectRow
                  actions={<span className="text-xs text-zinc-400">导航</span>}
                  icon={<ArrowUp className="h-4 w-4 text-zinc-500" />}
                  name="返回上一级"
                  onClick={() => void loadBrowser(browser.bucket, browser.parent_prefix ?? "", "")}
                  typeLabel="目录"
                />
              ) : null}

              {filteredPrefixes.map((entry) => (
                <ObjectRow
                  actions={<span className="text-xs text-zinc-400">打开</span>}
                  icon={<Folder className="h-4 w-4 text-zinc-700" />}
                  key={entry.prefix}
                  name={entry.name}
                  onClick={() => void loadBrowser(browser!.bucket, entry.prefix, "")}
                  sizeLabel="--"
                  typeLabel="目录"
                  updatedAt="--"
                />
              ))}

              {filteredObjects.map((entry) => {
                const selected = entry.key === selectedKey;
                const typeInfo = inferObjectType(entry.name);
                return (
                  <ObjectRow
                    actions={
                      <div className="flex items-center justify-end gap-1">
                        <IconActionButton
                          ariaLabel="复制对象路径"
                          icon={<Copy className="h-3.5 w-3.5" />}
                          onClick={() =>
                            void handleCopy(
                              `s3://${browser!.bucket}/${entry.key}`,
                              `已复制 ${entry.name} 的对象路径`
                            )
                          }
                        />
                        <IconActionButton
                          ariaLabel="下载对象"
                          icon={<Download className="h-3.5 w-3.5" />}
                          onClick={() =>
                            triggerObjectDownload(
                              getObjectStoreDownloadUrl({
                                bucket: browser!.bucket,
                                key: entry.key
                              })
                            )
                          }
                        />
                      </div>
                    }
                    icon={typeInfo.icon}
                    key={entry.key}
                    name={entry.name}
                    onClick={() => setSelectedKey(entry.key)}
                    selected={selected}
                    sizeLabel={formatFileSize(entry.size_bytes)}
                    subtitle={entry.key}
                    typeLabel={typeInfo.label}
                    updatedAt={formatTimestamp(entry.last_modified)}
                  />
                );
              })}

              {!loading && !error && filteredPrefixes.length === 0 && filteredObjects.length === 0 ? (
                <div className="flex min-h-[260px] flex-col items-center justify-center px-6 text-center">
                  <div className="text-sm font-medium text-zinc-950">
                    {deferredSearchQuery ? "没有匹配的目录或对象" : "当前目录为空"}
                  </div>
                  <p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">
                    当前 prefix 下没有对象，可以切换 bucket、修改路径，或前往 Files 页面上传业务文件。
                  </p>
                </div>
              ) : null}

              {loading ? (
                <div className="flex min-h-[260px] items-center justify-center gap-2 text-sm text-zinc-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在加载对象列表...
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">选中对象</CardTitle>
              <CardDescription>
                {selectedEntry
                  ? "可复制对象路径、直接下载，或在业务视图与底层 S3 视图之间来回切换。"
                  : "选择左侧对象后可查看完整 key、大小与更新时间。"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedEntry && browser ? (
                <>
                  <SelectionItem label="文件名" value={selectedEntry.name} />
                  <SelectionItem
                    label="对象路径"
                    value={`s3://${browser.bucket}/${selectedEntry.key}`}
                  />
                  <SelectionItem
                    label="文件大小"
                    value={formatFileSize(selectedEntry.size_bytes)}
                  />
                  <SelectionItem
                    label="更新时间"
                    value={formatTimestamp(selectedEntry.last_modified)}
                  />

                  <div className="flex flex-wrap gap-2">
                    <Button
                      className="rounded-md"
                      onClick={() =>
                        void handleCopy(
                          `s3://${browser.bucket}/${selectedEntry.key}`,
                          `已复制 ${selectedEntry.name} 的对象路径`
                        )
                      }
                      type="button"
                      variant="outline"
                    >
                      <Copy className="mr-2 h-4 w-4" />
                      复制 S3 路径
                    </Button>
                    <Button
                      className="rounded-md"
                      onClick={() =>
                        triggerObjectDownload(
                          getObjectStoreDownloadUrl({
                            bucket: browser.bucket,
                            key: selectedEntry.key
                          })
                        )
                      }
                      type="button"
                      variant="outline"
                    >
                      <Download className="mr-2 h-4 w-4" />
                      下载对象
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-md border border-dashed border-zinc-200 bg-zinc-50 px-4 py-5 text-sm leading-6 text-zinc-500">
                  暂未选中对象。左侧点击任意文件后，这里会显示完整 S3 URI 和快捷操作。
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function ExplorerNode({
  label,
  icon,
  indent,
  onClick,
  active,
  expanded = false,
  actions,
  caret = true,
  loading = false
}: {
  label: string;
  icon: React.ReactNode;
  indent: number;
  onClick: () => void;
  active?: boolean;
  expanded?: boolean;
  actions?: React.ReactNode;
  caret?: boolean;
  loading?: boolean;
}) {
  return (
    <div
      className={cn(
        "group flex w-full items-center gap-1 rounded-md pr-1 text-sm transition-colors",
        active
          ? "bg-zinc-800 text-white"
          : expanded
            ? "text-zinc-100 hover:bg-zinc-900 hover:text-white"
            : "text-zinc-300 hover:bg-zinc-900 hover:text-white"
      )}
    >
      <button
        className="flex min-w-0 flex-1 items-center gap-1 rounded-md pr-1 text-left"
        onClick={onClick}
        type="button"
        style={{ paddingLeft: `${8 + indent * 17}px` }}
      >
        {caret ? (
          <span
            aria-hidden="true"
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center text-zinc-500"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : expanded ? (
              <ChevronDown className={cn("h-3.5 w-3.5", active && "text-zinc-300")} />
            ) : (
              <ChevronRight className={cn("h-3.5 w-3.5", active && "text-zinc-300")} />
            )}
          </span>
        ) : (
          <span aria-hidden className="h-7 w-7 shrink-0" />
        )}
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1.5">
        <span className={cn("shrink-0 text-zinc-400", (active || expanded) && "text-zinc-300")}>{icon}</span>
        <span className="min-w-0 flex-1 truncate">{label}</span>
        </div>
      </button>
      {actions ? (
        <div className={cn("shrink-0 opacity-0 transition-opacity group-hover:opacity-100", active && "opacity-100")}>
          {actions}
        </div>
      ) : null}
    </div>
  );
}

function FilePreviewPane({
  cursorPosition,
  draftContent,
  dirty,
  entry,
  onCommitDraft,
  mode,
  onCopyContent,
  onDraftChange,
  onDownload,
  onSelectionChange,
  onToggleWrapLines,
  preview,
  previewUrl,
  loading,
  previewError,
  saving,
  wrapLines
}: {
  cursorPosition: { line: number; column: number };
  draftContent: string;
  dirty: boolean;
  entry: ObjectStoreObjectEntry;
  onCommitDraft: () => void;
  mode: FileViewMode;
  onCopyContent: () => void;
  onDraftChange: (value: string) => void;
  onDownload: () => void;
  onSelectionChange: (value: { line: number; column: number }) => void;
  onToggleWrapLines: () => void;
  preview: ObjectStoreObjectPreviewResponse | null;
  previewUrl: string;
  loading: boolean;
  previewError: string | null;
  saving: boolean;
  wrapLines: boolean;
}) {
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

  const handleTextareaCommand = React.useCallback(
    (command: "undo" | "redo") => {
      if (mode !== "edit" || !textareaRef.current) {
        return;
      }

      textareaRef.current.focus();
      document.execCommand(command);

      const nextValue = textareaRef.current.value;
      onDraftChange(nextValue);
      const selectionStart = textareaRef.current.selectionStart ?? 0;
      onSelectionChange(calculateTextCursorPosition(nextValue, selectionStart));
    },
    [mode, onDraftChange, onSelectionChange]
  );

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center gap-2 px-6 py-10 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在加载文件预览...
      </div>
    );
  }

  if (previewError) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-10">
        <div className="max-w-lg rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm leading-6 text-rose-700">
          {previewError}
        </div>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-10">
        <div className="rounded-xl border border-dashed border-zinc-200 bg-zinc-50 px-5 py-4 text-sm text-zinc-500">
          预览信息尚未准备完成。
        </div>
      </div>
    );
  }

  if (preview.preview_kind === "text") {
    const readOnly = mode !== "edit";
    const content = preview.content ?? "";
    const visibleContent = dirty ? draftContent : content;
    const lineNumbers = buildLineNumbers(readOnly ? visibleContent : draftContent);
    const canvasMinHeight = `${Math.max(320, lineNumbers.length * 24 + 32)}px`;
    const footerLabel = buildPreviewFooterLabel(entry.name);

    return (
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-transparent">
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="grid min-h-full grid-cols-[56px_minmax(0,1fr)]" style={{ minHeight: canvasMinHeight }}>
            <div className="select-none bg-transparent px-3 py-4 text-right font-mono text-xs leading-6 text-zinc-500">
              {lineNumbers.map((line) => (
                <div key={line}>{line}</div>
              ))}
            </div>
            {mode === "edit" ? (
              <textarea
                className={cn(
                  "min-h-full w-full resize-none rounded-none border-0 bg-transparent px-5 py-4 font-mono text-[13px] leading-6 text-zinc-100 outline-none",
                  wrapLines ? "overflow-hidden whitespace-pre-wrap" : "overflow-x-auto whitespace-pre"
                )}
                onChange={(event) => {
                  onDraftChange(event.target.value);
                  const selectionStart = event.currentTarget.selectionStart ?? 0;
                  onSelectionChange(
                    calculateTextCursorPosition(event.currentTarget.value, selectionStart)
                  );
                }}
                onClick={(event) => {
                  const selectionStart = event.currentTarget.selectionStart ?? 0;
                  onSelectionChange(
                    calculateTextCursorPosition(event.currentTarget.value, selectionStart)
                  );
                }}
                onBlur={() => {
                  if (dirty && !saving) {
                    onCommitDraft();
                  }
                }}
                onKeyUp={(event) => {
                  const selectionStart = event.currentTarget.selectionStart ?? 0;
                  onSelectionChange(
                    calculateTextCursorPosition(event.currentTarget.value, selectionStart)
                  );
                }}
                onSelect={(event) => {
                  const selectionStart = event.currentTarget.selectionStart ?? 0;
                  onSelectionChange(
                    calculateTextCursorPosition(event.currentTarget.value, selectionStart)
                  );
                }}
                ref={textareaRef}
                spellCheck={false}
                style={{ minHeight: canvasMinHeight }}
                value={draftContent}
                wrap={wrapLines ? "soft" : "off"}
              />
            ) : (
              <pre
                className={cn(
                  "min-h-full bg-transparent px-5 py-4 font-mono text-[13px] leading-6 text-zinc-100",
                  wrapLines ? "whitespace-pre-wrap break-words" : "overflow-x-auto whitespace-pre"
                )}
                style={{ minHeight: canvasMinHeight }}
              >
                {visibleContent}
              </pre>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 bg-transparent px-4 py-2 text-[11px] text-zinc-400">
          <div className="flex items-center gap-3">
            <span className="font-medium text-zinc-200">{footerLabel}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-zinc-400">
              Ln {cursorPosition.line}, Col {cursorPosition.column}
            </span>
            <button
              className="inline-flex h-6 items-center rounded-md border border-zinc-700 px-2 text-[11px] text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-white"
              disabled
              type="button"
            >
              Errors: 0
            </button>
            <div className="mx-1 h-4 w-px bg-zinc-800" />
            <button
              aria-label="Undo"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              disabled={mode !== "edit" || saving}
              onClick={() => handleTextareaCommand("undo")}
              type="button"
              title="Undo"
            >
              <Undo2 className="h-3.5 w-3.5" />
            </button>
            <button
              aria-label="Redo"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              disabled={mode !== "edit" || saving}
              onClick={() => handleTextareaCommand("redo")}
              type="button"
              title="Redo"
            >
              <Redo2 className="h-3.5 w-3.5" />
            </button>
            <button
              aria-label="Copy content"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
              onClick={onCopyContent}
              type="button"
              title="Copy content"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button
              aria-label="Download file"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
              onClick={onDownload}
              type="button"
              title="Download file"
            >
              <Download className="h-3.5 w-3.5" />
            </button>
            <button
              aria-label={wrapLines ? "Disable line wrap" : "Enable line wrap"}
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white",
                wrapLines && "bg-zinc-800 text-zinc-200"
              )}
              onClick={onToggleWrapLines}
              type="button"
              title={wrapLines ? "Disable line wrap" : "Enable line wrap"}
            >
              <Settings2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (preview.preview_kind === "image") {
    return (
      <div className="min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_top,#f4f4f5,transparent_48%),linear-gradient(180deg,#fafafa,#f4f4f5)] p-6">
        <div className="mx-auto flex max-w-6xl justify-center rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt={entry.name}
            className="h-auto max-h-[72vh] w-auto max-w-full rounded-lg object-contain"
            src={previewUrl}
          />
        </div>
      </div>
    );
  }

  if (preview.preview_kind === "pdf") {
    return (
      <div className="min-h-0 flex-1 bg-zinc-100 p-3">
        <iframe
          className="h-full min-h-[720px] w-full rounded-xl border border-zinc-200 bg-white"
          src={previewUrl}
          title={entry.name}
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-10">
      <div className="max-w-lg rounded-xl border border-dashed border-zinc-200 bg-zinc-50 px-5 py-4 text-sm leading-6 text-zinc-500">
        当前文件暂不支持在线预览，可以直接下载或使用 Open raw 查看原始内容。
      </div>
    </div>
  );
}

function FileTableRow({
  actions,
  icon,
  name,
  onClick,
  typeLabel,
  sizeLabel = "--",
  updatedAt = "--",
  active = false
}: {
  actions?: React.ReactNode;
  icon: React.ReactNode;
  name: string;
  onClick: () => void;
  typeLabel: string;
  sizeLabel?: string;
  updatedAt?: string;
  active?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid w-full grid-cols-[minmax(0,1.8fr)_120px_120px_180px_44px] items-center gap-4 border-b border-zinc-800 px-5 py-2.5 text-sm transition-colors",
        active ? "bg-zinc-900/80" : "hover:bg-zinc-900/50"
      )}
    >
      <button
        className="col-span-4 grid grid-cols-[minmax(0,1.8fr)_120px_120px_180px] items-center gap-4 text-left"
        onClick={onClick}
        type="button"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="shrink-0">{icon}</div>
          <div className="truncate font-medium text-zinc-100">{name}</div>
        </div>
        <div className="text-xs text-zinc-400">{typeLabel}</div>
        <div className="text-xs text-zinc-400">{sizeLabel}</div>
        <div className="text-xs text-zinc-400">{updatedAt}</div>
      </button>
      <div className="flex justify-end">
        {actions}
      </div>
    </div>
  );
}

function BreadcrumbButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="rounded-md px-2 py-1 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function ObjectRow({
  icon,
  name,
  subtitle,
  typeLabel,
  sizeLabel = "--",
  updatedAt = "--",
  actions,
  onClick,
  selected = false
}: {
  icon: React.ReactNode;
  name: string;
  subtitle?: string;
  typeLabel: string;
  sizeLabel?: string;
  updatedAt?: string;
  actions: React.ReactNode;
  onClick: () => void;
  selected?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-[minmax(0,1.6fr)_110px_120px_150px_148px] items-center gap-4 border-b border-zinc-100 px-5 py-3 text-sm transition-colors",
        selected ? "bg-zinc-100/80" : "hover:bg-zinc-50"
      )}
    >
      <button className="min-w-0 text-left" onClick={onClick} type="button">
        <div className="flex min-w-0 items-center gap-3">
          <div className="shrink-0">{icon}</div>
          <div className="min-w-0">
            <div className="truncate font-medium text-zinc-950">{name}</div>
            {subtitle ? (
              <div className="mt-0.5 truncate text-xs text-zinc-400">{subtitle}</div>
            ) : null}
          </div>
        </div>
      </button>
      <div className="text-xs text-zinc-500">{typeLabel}</div>
      <div className="text-xs text-zinc-500">{sizeLabel}</div>
      <div className="text-xs text-zinc-500">{updatedAt}</div>
      <div>{actions}</div>
    </div>
  );
}

function IconActionButton({
  ariaLabel,
  icon,
  onClick,
  disabled = false,
  tone = "default"
}: {
  ariaLabel: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
}) {
  return (
    <button
      aria-label={ariaLabel}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors",
        tone === "danger"
          ? "border-rose-200 text-rose-600 hover:bg-rose-50"
          : "border-zinc-200 text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700",
        disabled && "cursor-not-allowed opacity-60"
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {icon}
    </button>
  );
}

function SelectionItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <div className="text-xs uppercase tracking-[0.14em] text-zinc-400">{label}</div>
      <div className="break-all text-sm leading-6 text-zinc-900">{value}</div>
    </div>
  );
}

function UploadQueueRow({ item }: { item: UploadQueueItem }) {
  const progress = calculateUploadPercent(item.uploadedBytes, item.sizeBytes);
  const progressTone =
    item.status === "failed"
      ? "bg-rose-500"
      : item.status === "completed"
        ? "bg-emerald-500"
        : item.status === "queued"
          ? "bg-zinc-300"
          : "bg-sky-600";
  const metaTone = item.status === "failed" ? "text-rose-700" : "text-sky-700";

  return (
    <div className="rounded-md border border-sky-100 bg-white/70 px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-zinc-950">{item.label}</div>
          <div className={cn("mt-1 flex flex-wrap items-center gap-2 text-xs", metaTone)}>
            <span>{renderUploadQueueStatusLabel(item.status)}</span>
            <span>
              {formatFileSize(item.uploadedBytes)} / {formatFileSize(item.sizeBytes)}
            </span>
          </div>
          {item.error ? (
            <div className="mt-1 text-xs text-rose-600">{item.error}</div>
          ) : null}
        </div>
        <div className="shrink-0 text-xs font-medium text-zinc-500">{progress}%</div>
      </div>

      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100">
        <div
          className={cn("h-full rounded-full transition-[width] duration-150", progressTone)}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function constrainPrefix(
  prefix: string | undefined,
  rootPrefix: string | undefined,
  _mode: ObjectStoreConsoleMode
) {
  const normalized = normalizePrefix(prefix);
  if (!rootPrefix) {
    return normalized;
  }

  const root = normalizePrefix(rootPrefix);
  if (!normalized) {
    return root;
  }
  return normalized.startsWith(root) ? normalized : root;
}

function normalizePrefix(value?: string | null) {
  if (!value) {
    return "";
  }

  const normalized = value.trim().replace(/^\/+/, "");
  if (!normalized) {
    return "";
  }
  return normalized.endsWith("/") ? normalized : `${normalized}/`;
}

function toRelativePrefix(prefix: string, rootPrefix?: string) {
  const normalizedPrefix = normalizePrefix(prefix);
  const normalizedRoot = normalizePrefix(rootPrefix);
  if (!normalizedRoot || !normalizedPrefix.startsWith(normalizedRoot)) {
    return "";
  }
  return normalizedPrefix.slice(normalizedRoot.length);
}

function buildCurrentPathLabel({
  prefix,
  rootPrefix,
  mode
}: {
  prefix: string;
  rootPrefix?: string;
  mode: ObjectStoreConsoleMode;
}) {
  if (rootPrefix) {
    const relativePrefix = toRelativePrefix(prefix, rootPrefix);
    return relativePrefix ? `/${trimTrailingSlash(relativePrefix)}` : "/";
  }

  if (mode === "files") {
    const relativePrefix = toRelativePrefix(prefix, rootPrefix);
    return relativePrefix ? `/${trimTrailingSlash(relativePrefix)}` : "/";
  }

  return prefix ? `/${trimTrailingSlash(prefix)}` : "/";
}

function buildFilesLocationLabel(prefix: string, rootPrefix?: string) {
  const relativePrefix = toRelativePrefix(prefix, rootPrefix);
  const segments = relativePrefix.split("/").filter(Boolean);
  return segments.length > 0 ? `Files / ${segments.join(" / ")}` : "Files";
}

function buildBreadcrumbSegments(prefix: string, rootPrefix?: string) {
  const normalizedPrefix = normalizePrefix(prefix);
  const relativePrefix = rootPrefix ? toRelativePrefix(normalizedPrefix, rootPrefix) : normalizedPrefix;
  const segments = relativePrefix.split("/").filter(Boolean);
  let current = rootPrefix ? normalizePrefix(rootPrefix) : "";
  return segments.map((segment) => {
    current = `${current}${segment}/`;
    return { label: segment, prefix: current };
  });
}

function buildDirectoryParentPrefix(prefix: string, rootPrefix?: string) {
  const normalizedPrefix = normalizePrefix(prefix);
  const root = normalizePrefix(rootPrefix);
  if (!normalizedPrefix || normalizedPrefix === root) {
    return root;
  }

  const relativePrefix = toRelativePrefix(normalizedPrefix, root);
  const segments = relativePrefix.split("/").filter(Boolean);
  if (segments.length <= 1) {
    return root;
  }

  const parentRelativePrefix = `${segments.slice(0, -1).join("/")}/`;
  return `${root}${parentRelativePrefix}`;
}

function labelForPrefix(prefix: string) {
  const normalizedPrefix = normalizePrefix(prefix);
  const trimmed = trimTrailingSlash(normalizedPrefix);
  const segments = trimmed.split("/").filter(Boolean);
  return segments.at(-1) || "Files";
}

function buildObjectParentPrefix(objectKey: string) {
  const normalizedKey = objectKey.trim().replace(/^\/+/, "");
  const lastSlashIndex = normalizedKey.lastIndexOf("/");
  if (lastSlashIndex < 0) {
    return "";
  }

  return normalizePrefix(normalizedKey.slice(0, lastSlashIndex + 1));
}

function buildPreviewFooterLabel(fileName: string) {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";

  switch (extension) {
    case "md":
      return "Markdown";
    case "json":
    case "jsonl":
      return "JSON";
    case "yaml":
    case "yml":
      return "YAML";
    case "txt":
      return "Plain text";
    case "html":
    case "htm":
      return "HTML";
    case "xml":
      return "XML";
    default:
      return extension ? extension.toUpperCase() : "Plain text";
  }
}

function trimTrailingSlash(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function normalizeFolderNameInput(value: string) {
  return value.trim().replace(/^\/+|\/+$/g, "");
}

function buildLineNumbers(content: string) {
  const totalLines = Math.max(1, content.split("\n").length);
  return Array.from({ length: totalLines }, (_, index) => index + 1);
}

function calculateTextCursorPosition(content: string, selectionStart: number) {
  const boundedSelection = Math.max(0, Math.min(selectionStart, content.length));
  const beforeCursor = content.slice(0, boundedSelection);
  const lines = beforeCursor.split("\n");
  return {
    line: Math.max(1, lines.length),
    column: (lines.at(-1)?.length ?? 0) + 1
  };
}

function getRelativeUploadPath(file: File) {
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath?.trim();
  return relativePath ? relativePath.replace(/^\/+/, "") : null;
}

function buildUploadNotice(files: File[]) {
  const rootFolders = new Set(
    files
      .map((file) => getRelativeUploadPath(file)?.split("/").filter(Boolean)[0] ?? null)
      .filter((value): value is string => Boolean(value))
  );

  if (rootFolders.size === 0) {
    return files.length === 1 ? `已上传 ${files[0].name}` : `已上传 ${files.length} 个文件`;
  }

  if (rootFolders.size === 1) {
    return `已上传文件夹 ${Array.from(rootFolders)[0]}（${files.length} 个文件）`;
  }

  return `已上传 ${rootFolders.size} 个文件夹，共 ${files.length} 个文件`;
}

function buildUploadFileLabel(file: File) {
  return getRelativeUploadPath(file) ?? file.name;
}

function buildUploadQueueSummaryLabel(summary: {
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
}) {
  if (summary.failedFiles > 0) {
    return `已完成 ${summary.completedFiles}/${summary.totalFiles}，失败 ${summary.failedFiles} 个`;
  }
  if (summary.completedFiles >= summary.totalFiles) {
    return `已完成 ${summary.completedFiles}/${summary.totalFiles}`;
  }
  return `正在上传 ${summary.completedFiles}/${summary.totalFiles}`;
}

function buildUploadQueueItemId(file: File, index: number) {
  return [
    buildUploadFileLabel(file),
    file.size,
    file.lastModified,
    index
  ].join(":");
}

function renderUploadQueueStatusLabel(status: UploadQueueItemStatus) {
  if (status === "queued") {
    return "等待上传";
  }
  if (status === "preparing") {
    return "准备上传";
  }
  if (status === "finalizing") {
    return "确认上传";
  }
  if (status === "completed") {
    return "上传完成";
  }
  if (status === "failed") {
    return "上传失败";
  }
  return "上传中";
}

function calculateUploadPercent(uploadedBytes: number, totalBytes: number) {
  if (totalBytes <= 0) {
    return 0;
  }

  return Math.max(0, Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)));
}

function formatUploadPercent(uploadedBytes: number, totalBytes: number) {
  return `${calculateUploadPercent(uploadedBytes, totalBytes)}%`;
}

async function uploadFileToObjectStore(params: {
  bucket: string;
  file: File;
  prefix?: string;
  relativePath?: string;
  onProgress: (payload: {
    status: UploadLifecycleStatus;
    uploadedBytes: number;
    totalBytes: number;
  }) => void;
}): Promise<ObjectStoreUploadResponse> {
  const initResponse = await initiateDirectUpload({
    bucket: params.bucket,
    prefix: params.prefix,
    fileName: params.file.name,
    fileSize: params.file.size,
    contentType: params.file.type || null,
    relativePath: params.relativePath ?? null
  });

  params.onProgress({
    status: "preparing",
    uploadedBytes: 0,
    totalBytes: params.file.size
  });

  await uploadBlobWithProgress({
    file: params.file,
    headers: initResponse.headers,
    onProgress: (uploadedBytes, totalBytes) =>
      params.onProgress({
        status: "uploading",
        uploadedBytes,
        totalBytes
      }),
    url: initResponse.url
  });

  params.onProgress({
    status: "finalizing",
    uploadedBytes: params.file.size,
    totalBytes: params.file.size
  });

  return {
    bucket: initResponse.bucket,
    object_key: initResponse.object_key,
    uri: initResponse.uri,
    file_name: initResponse.file_name,
    size_bytes: params.file.size,
    content_type: initResponse.content_type ?? params.file.type ?? null,
    last_modified: new Date().toISOString()
  };
}

function uploadBlobWithProgress(params: {
  url: string;
  file: Blob;
  headers?: Record<string, string>;
  onProgress?: (uploadedBytes: number, totalBytes: number) => void;
}) {
  return new Promise<void>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", params.url);

    for (const [key, value] of Object.entries(params.headers ?? {})) {
      request.setRequestHeader(key, value);
    }

    request.upload.onprogress = (event) => {
      if (!params.onProgress) {
        return;
      }

      const totalBytes = event.lengthComputable ? event.total : params.file.size;
      params.onProgress(event.loaded, totalBytes);
    };

    request.onerror = () => {
      reject(new Error("对象存储上传失败，请检查直传地址和本地 RustFS 配置"));
    };
    request.onabort = () => {
      reject(new Error("对象存储上传已中止"));
    };
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`对象存储上传失败: ${request.status} ${request.statusText}`));
        return;
      }

      params.onProgress?.(params.file.size, params.file.size);
      resolve();
    };

    request.send(params.file);
  });
}

function buildExplorerDirectoryCacheKey(bucket: string, prefix: string) {
  return `${bucket}:${normalizePrefix(prefix)}`;
}

function buildObjectPreviewCacheKey(bucket: string, objectKey: string) {
  return `${bucket}:${objectKey}`;
}

function inferPreviewKind(fileName: string): ObjectPreviewKind {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";

  if (
    [
      "css",
      "csv",
      "html",
      "htm",
      "js",
      "json",
      "jsonl",
      "jsx",
      "log",
      "md",
      "py",
      "sh",
      "sql",
      "ts",
      "tsx",
      "txt",
      "xml",
      "yaml",
      "yml"
    ].includes(extension)
  ) {
    return "text";
  }

  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(extension)) {
    return "image";
  }

  if (extension === "pdf") {
    return "pdf";
  }

  return "unsupported";
}

function isPreviewableFile(fileName: string) {
  return inferPreviewKind(fileName) !== "unsupported";
}

function matchesSearch(value: string, query: string) {
  if (!query) {
    return true;
  }
  return value.toLowerCase().includes(query);
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false
  });
}

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function inferObjectType(fileName: string) {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";

  if (["html", "htm", "xml", "json", "jsonl", "md", "txt", "yaml", "yml"].includes(extension)) {
    return {
      label: extension ? extension.toUpperCase() : "文本",
      icon: <FileCode2 className="h-4 w-4 text-sky-600" />
    };
  }
  if (["pdf", "doc", "docx", "ppt", "pptx"].includes(extension)) {
    return {
      label: extension ? extension.toUpperCase() : "文档",
      icon: <FileText className="h-4 w-4 text-rose-600" />
    };
  }
  if (["xls", "xlsx", "csv"].includes(extension)) {
    return {
      label: extension ? extension.toUpperCase() : "表格",
      icon: <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
    };
  }
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(extension)) {
    return {
      label: extension ? extension.toUpperCase() : "图片",
      icon: <FileImage className="h-4 w-4 text-amber-600" />
    };
  }
  if (["zip", "rar", "7z", "tar", "gz"].includes(extension)) {
    return {
      label: extension ? extension.toUpperCase() : "压缩包",
      icon: <FileArchive className="h-4 w-4 text-violet-600" />
    };
  }

  return {
    label: extension ? extension.toUpperCase() : "文件",
    icon: <FileText className="h-4 w-4 text-zinc-500" />
  };
}

function buildConsoleHref(
  pathname: string,
  params: Record<string, string | null | undefined>
) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      query.set(key, value);
    }
  }

  const suffix = query.size ? `?${query.toString()}` : "";
  return `${pathname}${suffix}`;
}

function triggerObjectDownload(url: string) {
  const link = document.createElement("a");
  link.href = url;
  link.rel = "noreferrer";
  document.body.append(link);
  link.click();
  link.remove();
}
