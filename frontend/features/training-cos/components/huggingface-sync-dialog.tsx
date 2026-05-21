"use client";

import * as React from "react";
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  RefreshCw,
  Search,
  UploadCloud,
  XCircle
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
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
import { Spinner } from "@/components/ui/spinner";
import {
  createTrainingCosHuggingFaceSyncJob,
  getTrainingCosHuggingFaceSyncJob,
  listTrainingCosHuggingFaceFolderFiles,
  listTrainingCosHuggingFaceSyncJobs,
  retryTrainingCosHuggingFaceSyncJob,
  searchTrainingCosHuggingFaceRepos
} from "@/features/training-cos/api";
import type {
  TrainingCosEntry,
  TrainingCosHuggingFaceFolderFile,
  TrainingCosHuggingFaceRepoSummary,
  TrainingCosHuggingFaceRepoType,
  TrainingCosHuggingFaceSyncJob
} from "@/types/api";

const REPO_TYPE_LABEL: Record<TrainingCosHuggingFaceRepoType, string> = {
  model: "Model",
  dataset: "Dataset",
  space: "Space"
};

function normalizeFolderPrefix(entry: TrainingCosEntry) {
  const cleaned = entry.key.replace(/^\/+/, "");
  return cleaned.endsWith("/") ? cleaned : `${cleaned}/`;
}

function humanSize(bytes: number | null | undefined): string {
  if (bytes == null) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "--";
  try {
    return new Date(value).toLocaleString("zh-CN");
  } catch {
    return value;
  }
}

function splitTags(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function statusMeta(status: TrainingCosHuggingFaceSyncJob["status"]) {
  if (status === "succeeded") {
    return { label: "已完成", icon: CheckCircle2, className: "text-emerald-600" };
  }
  if (status === "failed") {
    return { label: "失败", icon: XCircle, className: "text-destructive" };
  }
  if (status === "running") {
    return { label: "同步中", icon: RefreshCw, className: "text-primary" };
  }
  return { label: "排队中", icon: Clock3, className: "text-muted-foreground" };
}

export function TrainingCosHuggingFaceSyncDialog({ entry }: { entry: TrainingCosEntry }) {
  const prefix = React.useMemo(() => normalizeFolderPrefix(entry), [entry]);
  const [open, setOpen] = React.useState(false);
  const [repoType, setRepoType] = React.useState<TrainingCosHuggingFaceRepoType>("model");
  const [repoQuery, setRepoQuery] = React.useState(entry.name);
  const [repoId, setRepoId] = React.useState(entry.name);
  const [repoResults, setRepoResults] = React.useState<TrainingCosHuggingFaceRepoSummary[]>([]);
  const [searching, setSearching] = React.useState(false);
  const [createIfMissing, setCreateIfMissing] = React.useState(true);
  const [privateRepo, setPrivateRepo] = React.useState(false);
  const [createReadme, setCreateReadme] = React.useState(true);
  const [license, setLicense] = React.useState("");
  const [baseModel, setBaseModel] = React.useState("");
  const [tags, setTags] = React.useState("text-generation");
  const [files, setFiles] = React.useState<TrainingCosHuggingFaceFolderFile[]>([]);
  const [filesLoading, setFilesLoading] = React.useState(false);
  const [filesTruncated, setFilesTruncated] = React.useState(false);
  const [excludedKeys, setExcludedKeys] = React.useState<Set<string>>(() => new Set());
  const [jobs, setJobs] = React.useState<TrainingCosHuggingFaceSyncJob[]>([]);
  const [lastSyncAt, setLastSyncAt] = React.useState<string | null>(null);
  const [activeJob, setActiveJob] = React.useState<TrainingCosHuggingFaceSyncJob | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [retrying, setRetrying] = React.useState(false);

  const latestJob = activeJob ?? jobs[0] ?? null;
  const selectedFiles = files.length - excludedKeys.size;
  const selectedBytes = files.reduce(
    (total, file) => total + (excludedKeys.has(file.key) ? 0 : file.size),
    0
  );

  const loadFiles = React.useCallback(async () => {
    setFilesLoading(true);
    try {
      const response = await listTrainingCosHuggingFaceFolderFiles({ prefix });
      setFiles(response.files);
      setFilesTruncated(response.truncated);
      setExcludedKeys((current) => {
        const next = new Set<string>();
        for (const key of current) {
          if (response.files.some((file) => file.key === key)) next.add(key);
        }
        return next;
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文件列表加载失败");
    } finally {
      setFilesLoading(false);
    }
  }, [prefix]);

  const loadJobs = React.useCallback(async () => {
    try {
      const response = await listTrainingCosHuggingFaceSyncJobs({ prefix, limit: 10 });
      setJobs(response.jobs);
      setLastSyncAt(response.last_sync_at ?? null);
    } catch {
      setJobs([]);
      setLastSyncAt(null);
    }
  }, [prefix]);

  const runSearch = React.useCallback(async () => {
    setSearching(true);
    try {
      const response = await searchTrainingCosHuggingFaceRepos({
        query: repoQuery,
        repoType,
        limit: 12
      });
      setRepoResults(response.repos);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Repo 搜索失败");
    } finally {
      setSearching(false);
    }
  }, [repoQuery, repoType]);

  React.useEffect(() => {
    if (!open) return;
    setRepoQuery((value) => value || entry.name);
    setRepoId((value) => value || entry.name);
    void loadFiles();
    void loadJobs();
  }, [entry.name, loadFiles, loadJobs, open]);

  React.useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => {
      void runSearch();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [open, runSearch]);

  React.useEffect(() => {
    if (!open || !latestJob || !["pending", "running"].includes(latestJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getTrainingCosHuggingFaceSyncJob(latestJob.id);
        setActiveJob(next);
        if (!["pending", "running"].includes(next.status)) {
          await loadJobs();
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [latestJob, loadJobs, open]);

  const toggleFile = (key: string, checked: boolean) => {
    setExcludedKeys((current) => {
      const next = new Set(current);
      if (checked) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    const cleanedRepoId = repoId.trim();
    if (!cleanedRepoId) {
      toast.error("请填写 Hugging Face Repo ID");
      return;
    }
    if (!selectedFiles) {
      toast.error("至少保留一个要上传的文件");
      return;
    }

    setSubmitting(true);
    try {
      const job = await createTrainingCosHuggingFaceSyncJob({
        prefix,
        repo_id: cleanedRepoId,
        repo_type: repoType,
        create_if_missing: createIfMissing,
        private: privateRepo,
        create_readme: createReadme,
        license: license.trim() || null,
        base_model: baseModel.trim() || null,
        tags: splitTags(tags),
        exclude_keys: Array.from(excludedKeys)
      });
      setActiveJob(job);
      toast.success("同步任务已提交");
      await loadJobs();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "同步任务提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async () => {
    if (!latestJob) return;
    setRetrying(true);
    try {
      const job = await retryTrainingCosHuggingFaceSyncJob(latestJob.id);
      setActiveJob(job);
      toast.success("已重新提交同步任务");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重试失败");
    } finally {
      setRetrying(false);
    }
  };

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <UploadCloud className="size-3.5" />
          同步 HF
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-hidden p-0">
        <DialogHeader className="px-5 pb-1 pr-12 pt-5">
          <DialogTitle>同步到 Hugging Face</DialogTitle>
          <DialogDescription className="break-all">
            {prefix}
            {lastSyncAt ? ` · 最后同步 ${formatTime(lastSyncAt)}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="grid min-h-0 gap-4 px-5 pb-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <ScrollArea className="max-h-[72vh] pr-3">
            <div className="space-y-5 pb-1">
              <section className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
                  <div className="space-y-1.5">
                    <Label>Repo 类型</Label>
                    <Select
                      onValueChange={(value) =>
                        setRepoType(value as TrainingCosHuggingFaceRepoType)
                      }
                      value={repoType}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="model">Model</SelectItem>
                        <SelectItem value="dataset">Dataset</SelectItem>
                        <SelectItem value="space">Space</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Repo ID</Label>
                    <div className="flex gap-2">
                      <Input
                        onChange={(event) => {
                          setRepoId(event.target.value);
                          setRepoQuery(event.target.value);
                        }}
                        placeholder="namespace/repo-name"
                        value={repoId}
                      />
                      <Button onClick={runSearch} type="button" variant="outline">
                        {searching ? <Spinner /> : <Search className="size-4" />}
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-border/70">
                  <div className="flex items-center justify-between border-b border-border/70 px-3 py-2">
                    <span className="text-sm font-medium">搜索结果</span>
                    <Badge variant="outline">{REPO_TYPE_LABEL[repoType]}</Badge>
                  </div>
                  <ScrollArea className="h-40">
                    {searching ? (
                      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                        <Spinner className="mr-2" />
                        搜索中
                      </div>
                    ) : repoResults.length ? (
                      <div className="divide-y divide-border/70">
                        {repoResults.map((repo) => (
                          <button
                            className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-muted/40"
                            key={repo.repo_id}
                            onClick={() => {
                              setRepoId(repo.repo_id);
                              setRepoQuery(repo.repo_id);
                            }}
                            type="button"
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium">{repo.repo_id}</span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {repo.private ? "private" : "public"}
                                {repo.last_modified ? ` · ${formatTime(repo.last_modified)}` : ""}
                              </span>
                            </span>
                            <span className="text-xs text-muted-foreground">选择</span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                        没有匹配的 Repo
                      </div>
                    )}
                  </ScrollArea>
                </div>
              </section>

              <section className="grid gap-3 sm:grid-cols-3">
                <label className="flex items-center gap-2 rounded-md border border-border/70 px-3 py-2 text-sm">
                  <input
                    checked={createIfMissing}
                    className="size-4 accent-primary"
                    onChange={(event) => setCreateIfMissing(event.target.checked)}
                    type="checkbox"
                  />
                  不存在时创建
                </label>
                <label className="flex items-center gap-2 rounded-md border border-border/70 px-3 py-2 text-sm">
                  <input
                    checked={privateRepo}
                    className="size-4 accent-primary"
                    onChange={(event) => setPrivateRepo(event.target.checked)}
                    type="checkbox"
                  />
                  创建为私有
                </label>
                <label className="flex items-center gap-2 rounded-md border border-border/70 px-3 py-2 text-sm">
                  <input
                    checked={createReadme}
                    className="size-4 accent-primary"
                    onChange={(event) => setCreateReadme(event.target.checked)}
                    type="checkbox"
                  />
                  生成 README
                </label>
              </section>

              <section className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label>License</Label>
                  <Input
                    onChange={(event) => setLicense(event.target.value)}
                    placeholder="apache-2.0"
                    value={license}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Base model</Label>
                  <Input
                    onChange={(event) => setBaseModel(event.target.value)}
                    placeholder="Qwen/Qwen2.5-7B"
                    value={baseModel}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Tags</Label>
                  <Input
                    onChange={(event) => setTags(event.target.value)}
                    placeholder="text-generation, qwen"
                    value={tags}
                  />
                </div>
              </section>

              <section className="rounded-md border border-border/70">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 px-3 py-2">
                  <div className="space-y-0.5">
                    <div className="text-sm font-medium">文件过滤</div>
                    <div className="text-xs text-muted-foreground">
                      {selectedFiles}/{files.length} 个文件 · {humanSize(selectedBytes)}
                      {filesTruncated ? " · 列表已截断" : ""}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => setExcludedKeys(new Set())}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      全部上传
                    </Button>
                    <Button
                      onClick={() => setExcludedKeys(new Set(files.map((file) => file.key)))}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      全部排除
                    </Button>
                  </div>
                </div>
                <ScrollArea className="h-56">
                  {filesLoading ? (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      <Spinner className="mr-2" />
                      加载文件
                    </div>
                  ) : files.length ? (
                    <div className="divide-y divide-border/70">
                      {files.map((file) => {
                        const checked = !excludedKeys.has(file.key);
                        return (
                          <label
                            className="grid cursor-pointer grid-cols-[20px_minmax(0,1fr)_88px] items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-muted/40"
                            key={file.key}
                          >
                            <input
                              checked={checked}
                              className="size-4 accent-primary"
                              onChange={(event) => toggleFile(file.key, event.target.checked)}
                              type="checkbox"
                            />
                            <span className="min-w-0">
                              <span className="block truncate">{file.relative_path}</span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {file.key}
                              </span>
                            </span>
                            <span className="text-right text-xs text-muted-foreground">
                              {humanSize(file.size)}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                      没有可同步的文件
                    </div>
                  )}
                </ScrollArea>
              </section>

              <div className="flex justify-end">
                <Button disabled={submitting || !selectedFiles} onClick={handleSubmit} type="button">
                  {submitting ? <Spinner /> : <UploadCloud className="size-4" />}
                  开始同步
                </Button>
              </div>
            </div>
          </ScrollArea>

          <SyncJobPanel
            job={latestJob}
            lastSyncAt={lastSyncAt}
            onRetry={handleRetry}
            retrying={retrying}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SyncJobPanel({
  job,
  lastSyncAt,
  onRetry,
  retrying
}: {
  job: TrainingCosHuggingFaceSyncJob | null;
  lastSyncAt: string | null;
  onRetry: () => void;
  retrying: boolean;
}) {
  if (!job) {
    return (
      <aside className="min-h-0 rounded-md border border-border/70 px-4 py-3">
        <div className="text-sm font-medium">同步状态</div>
        <div className="mt-2 text-sm text-muted-foreground">
          {lastSyncAt ? `最后同步 ${formatTime(lastSyncAt)}` : "暂无同步记录"}
        </div>
      </aside>
    );
  }

  const meta = statusMeta(job.status);
  const Icon = meta.icon;
  return (
    <aside className="min-h-0 rounded-md border border-border/70 px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">同步状态</div>
        <div className={`inline-flex items-center gap-1.5 text-sm ${meta.className}`}>
          <Icon className={job.status === "running" ? "size-4 animate-spin" : "size-4"} />
          {meta.label}
        </div>
      </div>
      <div className="mt-3 space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">进度</span>
          <span>{job.progress_percent}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${job.progress_percent}%` }}
          />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <span>文件 {job.downloaded_files}/{job.total_files}</span>
          <span className="text-right">{humanSize(job.downloaded_bytes)}</span>
          <span>排除 {job.skipped_files}</span>
          <span className="text-right">{formatTime(job.updated_at)}</span>
        </div>
      </div>

      {job.error_message ? (
        <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {job.error_message}
        </div>
      ) : null}

      {job.repo_url ? (
        <a
          className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          href={job.repo_url}
          rel="noreferrer"
          target="_blank"
        >
          打开 Repo
          <ExternalLink className="size-3.5" />
        </a>
      ) : null}

      <div className="mt-4">
        <div className="mb-2 text-sm font-medium">日志</div>
        <ScrollArea className="h-64 rounded-md border border-border/70 bg-muted/20">
          {job.logs.length ? (
            <div className="space-y-2 p-3">
              {job.logs.map((item, index) => (
                <div className="text-xs" key={`${item.logged_at}-${index}`}>
                  <div className="text-muted-foreground">{formatTime(item.logged_at)}</div>
                  <div className={item.level === "error" ? "text-destructive" : "text-foreground"}>
                    {item.message}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
              暂无日志
            </div>
          )}
        </ScrollArea>
      </div>

      {job.status === "failed" ? (
        <Button className="mt-3 w-full" disabled={retrying} onClick={onRetry} variant="outline">
          {retrying ? <Spinner /> : <RefreshCw className="size-4" />}
          重试
        </Button>
      ) : null}
    </aside>
  );
}
