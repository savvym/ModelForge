"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  addBenchmarkLeaderboardJobs,
  deleteBenchmarkLeaderboard,
  getAvailableBenchmarkLeaderboardJobs,
  getBenchmarkLeaderboard,
  removeBenchmarkLeaderboardJob
} from "@/features/eval/api";
import { formatLeaderboardMetricName } from "@/features/eval/status";
import type {
  BenchmarkLeaderboardDetail,
  BenchmarkLeaderboardJobCandidate
} from "@/types/api";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.68)] px-4 py-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-sm text-slate-100">{value}</div>
    </div>
  );
}

export function BenchmarkLeaderboardDetailPanel({
  initialLeaderboard
}: {
  initialLeaderboard: BenchmarkLeaderboardDetail;
}) {
  const router = useRouter();
  const [leaderboard, setLeaderboard] = React.useState(initialLeaderboard);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);
  const [availableJobs, setAvailableJobs] = React.useState<BenchmarkLeaderboardJobCandidate[]>([]);
  const [loadingAvailableJobs, setLoadingAvailableJobs] = React.useState(false);
  const [jobQuery, setJobQuery] = React.useState("");
  const [selectedJobIds, setSelectedJobIds] = React.useState<string[]>([]);
  const [addingJobs, setAddingJobs] = React.useState(false);
  const [removingJobId, setRemovingJobId] = React.useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);

  React.useEffect(() => {
    setLeaderboard(initialLeaderboard);
  }, [initialLeaderboard]);

  React.useEffect(() => {
    if (!addDialogOpen) {
      return;
    }

    let cancelled = false;
    setLoadingAvailableJobs(true);
    setActionError(null);

    getAvailableBenchmarkLeaderboardJobs({
      benchmarkName: leaderboard.benchmark_name,
      benchmarkVersionId: leaderboard.benchmark_version_id,
      excludeLeaderboardId: leaderboard.id
    })
      .then((jobs) => {
        if (!cancelled) {
          setAvailableJobs(jobs);
          setSelectedJobIds([]);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setAvailableJobs([]);
          setActionError(err instanceof Error ? err.message : "读取可选评测任务失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAvailableJobs(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [addDialogOpen, leaderboard.benchmark_name, leaderboard.benchmark_version_id, leaderboard.id]);

  const filteredAvailableJobs = React.useMemo(() => {
    const normalizedQuery = jobQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableJobs;
    }
    return availableJobs.filter((job) =>
      [job.eval_job_name, job.eval_job_id, job.model_name].join(" ").toLowerCase().includes(normalizedQuery)
    );
  }, [availableJobs, jobQuery]);

  const allVisibleSelected =
    filteredAvailableJobs.length > 0 &&
    filteredAvailableJobs.every((job) => selectedJobIds.includes(job.eval_job_id));

  async function reloadLeaderboard() {
    const refreshed = await getBenchmarkLeaderboard(leaderboard.id);
    setLeaderboard(refreshed);
    return refreshed;
  }

  async function handleAddJobs() {
    if (selectedJobIds.length === 0) {
      setAddDialogOpen(false);
      return;
    }

    setAddingJobs(true);
    setActionError(null);
    try {
      const updated = await addBenchmarkLeaderboardJobs(leaderboard.id, {
        eval_job_ids: selectedJobIds
      });
      setLeaderboard(updated);
      setAddDialogOpen(false);
      setSelectedJobIds([]);
      setJobQuery("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "添加评测任务失败");
    } finally {
      setAddingJobs(false);
    }
  }

  async function handleRemoveJob(evalJobId: string) {
    setRemovingJobId(evalJobId);
    setActionError(null);
    try {
      await removeBenchmarkLeaderboardJob(leaderboard.id, evalJobId);
      await reloadLeaderboard();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "移除评测任务失败");
    } finally {
      setRemovingJobId(null);
    }
  }

  async function handleDeleteLeaderboard() {
    setDeleting(true);
    setActionError(null);
    try {
      await deleteBenchmarkLeaderboard(leaderboard.id);
      router.push("/model/eval?tab=leaderboards");
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "删除排行榜失败");
    } finally {
      setDeleting(false);
      setDeleteConfirmOpen(false);
    }
  }

  return (
    <div className="space-y-4">
      {actionError ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-4 py-3 text-sm text-rose-300">
          {actionError}
        </div>
      ) : null}

      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Link className="transition-colors hover:text-slate-200" href="/model/eval?tab=leaderboards">
          排行榜
        </Link>
        <span className="text-slate-600">&gt;</span>
        <span className="text-slate-100">{leaderboard.name}</span>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Benchmark" value={leaderboard.benchmark_display_name} />
        <SummaryCard label="Version" value={leaderboard.benchmark_version_display_name} />
        <SummaryCard
          label="评分指标"
          value={formatLeaderboardMetricName(leaderboard.score_metric_name)}
        />
        <SummaryCard
          label="任务数"
          value={`${leaderboard.job_count} · 最近评测 ${formatDateTime(leaderboard.latest_eval_at)}`}
        />
      </div>

      <div className="rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)]">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800/80 px-4 py-3">
          <div>
            <div className="text-sm font-medium text-slate-100">排行榜明细</div>
            <div className="mt-1 text-xs text-slate-500">
              当前按得分从高到低排序。同分时，最近完成的任务排在前面。
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setAddDialogOpen(true)} size="sm" variant="outline">
              添加评测任务
            </Button>
            <Button
              className="border-red-500/40 bg-red-950/20 text-red-100 hover:bg-red-950/40"
              onClick={() => setDeleteConfirmOpen(true)}
              size="sm"
              variant="outline"
            >
              删除排行榜
            </Button>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[72px]">排名</TableHead>
              <TableHead>任务名称</TableHead>
              <TableHead>评测模型</TableHead>
              <TableHead>排行榜得分</TableHead>
              <TableHead>评分指标</TableHead>
              <TableHead>完成时间</TableHead>
              <TableHead className="w-[100px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leaderboard.entries.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={7}>
                  当前排行榜还没有关联任何评测任务。
                </TableCell>
              </TableRow>
            ) : (
              leaderboard.entries.map((entry) => (
                <TableRow key={entry.eval_job_id}>
                  <TableCell className="font-medium text-slate-100">{entry.rank}</TableCell>
                  <TableCell className="align-top">
                    <Link href={`/model/eval-detail/${entry.eval_job_id}`}>
                      <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                        {entry.eval_job_name}
                      </div>
                    </Link>
                    <div className="mt-1 text-xs text-slate-500">{entry.eval_job_id}</div>
                  </TableCell>
                  <TableCell className="align-top text-slate-300">{entry.model_name}</TableCell>
                  <TableCell className="align-top text-slate-100">
                    {entry.score.toFixed(4)}
                  </TableCell>
                  <TableCell className="align-top text-slate-400">
                    {formatLeaderboardMetricName(entry.metric_name)}
                  </TableCell>
                  <TableCell className="align-top text-slate-400">
                    {formatDateTime(entry.finished_at ?? entry.created_at)}
                  </TableCell>
                  <TableCell className="align-top">
                    <Button
                      disabled={removingJobId === entry.eval_job_id}
                      onClick={() => void handleRemoveJob(entry.eval_job_id)}
                      size="sm"
                      variant="ghost"
                    >
                      {removingJobId === entry.eval_job_id ? "处理中..." : "移除"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog
        open={addDialogOpen}
        onOpenChange={(open) => {
          if (!addingJobs) {
            setAddDialogOpen(open);
          }
        }}
      >
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>添加评测任务</DialogTitle>
            <DialogDescription>
              只展示使用当前 Benchmark Version 且已经完成并产出得分的评测任务。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="text-sm text-muted-foreground">
                可选任务 {availableJobs.length} 条，已选 {selectedJobIds.length} 条
              </div>
              <div className="w-full max-w-sm">
                <Input
                  value={jobQuery}
                  onChange={(event) => setJobQuery(event.target.value)}
                  placeholder="搜索任务名称、ID 或模型"
                />
              </div>
            </div>

            <div className="max-h-[420px] overflow-auto rounded-xl border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[72px] text-center">
                      <input
                        aria-label="全选当前列表"
                        checked={allVisibleSelected}
                        className="h-4 w-4 accent-slate-100"
                        disabled={filteredAvailableJobs.length === 0}
                        onChange={(event) => {
                          if (event.target.checked) {
                            setSelectedJobIds((current) => [
                              ...new Set([
                                ...current,
                                ...filteredAvailableJobs.map((job) => job.eval_job_id)
                              ])
                            ]);
                          } else {
                            const visibleIds = new Set(
                              filteredAvailableJobs.map((job) => job.eval_job_id)
                            );
                            setSelectedJobIds((current) =>
                              current.filter((id) => !visibleIds.has(id))
                            );
                          }
                        }}
                        type="checkbox"
                      />
                    </TableHead>
                    <TableHead>任务名称</TableHead>
                    <TableHead>评测模型</TableHead>
                    <TableHead>排行榜得分</TableHead>
                    <TableHead>评分指标</TableHead>
                    <TableHead>完成时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingAvailableJobs ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={6}>
                        可选评测任务加载中...
                      </TableCell>
                    </TableRow>
                  ) : filteredAvailableJobs.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={6}>
                        当前没有可加入排行榜的新任务。
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredAvailableJobs.map((job) => {
                      const checked = selectedJobIds.includes(job.eval_job_id);
                      return (
                        <TableRow key={job.eval_job_id}>
                          <TableCell className="text-center">
                            <input
                              aria-label={`选择 ${job.eval_job_name}`}
                              checked={checked}
                              className="h-4 w-4 accent-slate-100"
                              onChange={(event) => {
                                const nextChecked = event.target.checked;
                                setSelectedJobIds((current) => {
                                  if (nextChecked) {
                                    return current.includes(job.eval_job_id)
                                      ? current
                                      : [...current, job.eval_job_id];
                                  }
                                  return current.filter((id) => id !== job.eval_job_id);
                                });
                              }}
                              type="checkbox"
                            />
                          </TableCell>
                          <TableCell>
                            <div className="font-medium text-slate-100">{job.eval_job_name}</div>
                            <div className="mt-1 text-xs text-slate-500">{job.eval_job_id}</div>
                          </TableCell>
                          <TableCell className="text-slate-300">{job.model_name}</TableCell>
                          <TableCell className="text-slate-100">{job.score.toFixed(4)}</TableCell>
                          <TableCell className="text-slate-400">
                            {formatLeaderboardMetricName(job.metric_name)}
                          </TableCell>
                          <TableCell className="text-slate-400">
                            {formatDateTime(job.finished_at ?? job.created_at)}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <DialogFooter>
            <Button disabled={addingJobs} onClick={() => setAddDialogOpen(false)} variant="outline">
              取消
            </Button>
            <Button disabled={addingJobs} onClick={() => void handleAddJobs()}>
              {addingJobs ? "添加中..." : "确认添加"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteConfirmOpen}
        onOpenChange={(open) => {
          if (!deleting) {
            setDeleteConfirmOpen(open);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除排行榜</AlertDialogTitle>
            <AlertDialogDescription>
              删除后排行榜对象会被移除，但原始评测任务和 Benchmark 数据不会被删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={() => void handleDeleteLeaderboard()}
            >
              {deleting ? "删除中..." : "删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
