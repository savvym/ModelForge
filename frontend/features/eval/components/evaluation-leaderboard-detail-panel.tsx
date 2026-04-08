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
  addEvaluationLeaderboardRuns,
  deleteEvaluationLeaderboard,
  getAvailableEvaluationLeaderboardRuns,
  getEvaluationLeaderboard,
  removeEvaluationLeaderboardRun
} from "@/features/eval/api";
import type {
  EvaluationLeaderboardDetailV2,
  EvaluationLeaderboardRunCandidateV2
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

export function EvaluationLeaderboardDetailPanel({
  initialLeaderboard
}: {
  initialLeaderboard: EvaluationLeaderboardDetailV2;
}) {
  const router = useRouter();
  const [leaderboard, setLeaderboard] = React.useState(initialLeaderboard);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);
  const [availableRuns, setAvailableRuns] = React.useState<EvaluationLeaderboardRunCandidateV2[]>([]);
  const [loadingAvailableRuns, setLoadingAvailableRuns] = React.useState(false);
  const [runQuery, setRunQuery] = React.useState("");
  const [selectedRunIds, setSelectedRunIds] = React.useState<string[]>([]);
  const [addingRuns, setAddingRuns] = React.useState(false);
  const [removingRunId, setRemovingRunId] = React.useState<string | null>(null);
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
    setLoadingAvailableRuns(true);
    setActionError(null);

    getAvailableEvaluationLeaderboardRuns({
      kind: leaderboard.target_kind,
      name: leaderboard.target_name,
      version: leaderboard.target_version,
      excludeLeaderboardId: leaderboard.id
    })
      .then((runs) => {
        if (!cancelled) {
          setAvailableRuns(runs);
          setSelectedRunIds([]);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setAvailableRuns([]);
          setActionError(err instanceof Error ? err.message : "读取可选运行失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAvailableRuns(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [addDialogOpen, leaderboard.id, leaderboard.target_kind, leaderboard.target_name, leaderboard.target_version]);

  const filteredAvailableRuns = React.useMemo(() => {
    const normalizedQuery = runQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableRuns;
    }
    return availableRuns.filter((run) =>
      [run.run_name, run.run_id, run.model_name].join(" ").toLowerCase().includes(normalizedQuery)
    );
  }, [availableRuns, runQuery]);

  const allVisibleSelected =
    filteredAvailableRuns.length > 0 &&
    filteredAvailableRuns.every((run) => selectedRunIds.includes(run.run_id));

  async function reloadLeaderboard() {
    const refreshed = await getEvaluationLeaderboard(leaderboard.id);
    setLeaderboard(refreshed);
    return refreshed;
  }

  async function handleAddRuns() {
    if (selectedRunIds.length === 0) {
      setAddDialogOpen(false);
      return;
    }

    setAddingRuns(true);
    setActionError(null);
    try {
      const updated = await addEvaluationLeaderboardRuns(leaderboard.id, {
        run_ids: selectedRunIds
      });
      setLeaderboard(updated);
      setAddDialogOpen(false);
      setSelectedRunIds([]);
      setRunQuery("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "添加运行失败");
    } finally {
      setAddingRuns(false);
    }
  }

  async function handleRemoveRun(runId: string) {
    setRemovingRunId(runId);
    setActionError(null);
    try {
      await removeEvaluationLeaderboardRun(leaderboard.id, runId);
      await reloadLeaderboard();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "移除运行失败");
    } finally {
      setRemovingRunId(null);
    }
  }

  async function handleDeleteLeaderboard() {
    setDeleting(true);
    setActionError(null);
    try {
      await deleteEvaluationLeaderboard(leaderboard.id);
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
        <SummaryCard label="目标" value={leaderboard.target_display_name} />
        <SummaryCard label="版本" value={leaderboard.target_version_display_name} />
        <SummaryCard label="评分指标" value={leaderboard.score_metric_name} />
        <SummaryCard
          label="运行数"
          value={`${leaderboard.run_count} · 最近评测 ${formatDateTime(leaderboard.latest_run_at)}`}
        />
      </div>

      <div className="rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)]">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800/80 px-4 py-3">
          <div>
            <div className="text-sm font-medium text-slate-100">排行榜明细</div>
            <div className="mt-1 text-xs text-slate-500">
              当前按得分从高到低排序。同分时，最近完成的运行排在前面。
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setAddDialogOpen(true)} size="sm" variant="outline">
              添加运行
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
              <TableHead>运行名称</TableHead>
              <TableHead>评测模型</TableHead>
              <TableHead>排行榜得分</TableHead>
              <TableHead>评分指标</TableHead>
              <TableHead>完成时间</TableHead>
              <TableHead className="w-[96px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leaderboard.entries.length === 0 ? (
              <TableRow>
                <TableCell className="py-8 text-center text-sm text-muted-foreground" colSpan={7}>
                  当前排行榜还没有关联任何评测运行。
                </TableCell>
              </TableRow>
            ) : (
              leaderboard.entries.map((entry) => (
                <TableRow key={entry.run_id}>
                  <TableCell className="align-top text-slate-200">{entry.rank}</TableCell>
                  <TableCell className="align-top">
                    <Link href={`/model/eval-detail/${entry.run_id}`}>
                      <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                        {entry.run_name}
                      </div>
                    </Link>
                    <div className="mt-1 text-xs text-slate-500">{entry.run_id}</div>
                  </TableCell>
                  <TableCell className="align-top text-slate-300">{entry.model_name}</TableCell>
                  <TableCell className="align-top text-slate-100">{entry.score.toFixed(4)}</TableCell>
                  <TableCell className="align-top text-slate-400">{entry.metric_name}</TableCell>
                  <TableCell className="align-top text-slate-400">{formatDateTime(entry.finished_at)}</TableCell>
                  <TableCell className="align-top">
                    <Button
                      disabled={removingRunId === entry.run_id}
                      onClick={() => void handleRemoveRun(entry.run_id)}
                      size="sm"
                      variant="ghost"
                    >
                      {removingRunId === entry.run_id ? "处理中..." : "移除"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>添加运行</DialogTitle>
            <DialogDescription>
              只显示与当前 leaderboard target 匹配、已经完成并产出 overall score 的运行。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Input
                className="w-[280px]"
                placeholder="搜索运行名称、ID 或模型"
                value={runQuery}
                onChange={(event) => setRunQuery(event.target.value)}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  setSelectedRunIds((current) =>
                    allVisibleSelected
                      ? current.filter((runId) => !filteredAvailableRuns.some((run) => run.run_id === runId))
                      : Array.from(new Set([...current, ...filteredAvailableRuns.map((run) => run.run_id)]))
                  )
                }
              >
                {allVisibleSelected ? "取消全选可见项" : "全选可见项"}
              </Button>
            </div>

            <div className="rounded-xl border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[56px]">选择</TableHead>
                    <TableHead>运行</TableHead>
                    <TableHead>模型</TableHead>
                    <TableHead>得分</TableHead>
                    <TableHead>指标</TableHead>
                    <TableHead>完成时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingAvailableRuns ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-sm text-muted-foreground" colSpan={6}>
                        正在读取可选运行...
                      </TableCell>
                    </TableRow>
                  ) : filteredAvailableRuns.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-sm text-muted-foreground" colSpan={6}>
                        当前没有可加入排行榜的新运行。
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredAvailableRuns.map((run) => {
                      const checked = selectedRunIds.includes(run.run_id);
                      return (
                        <TableRow key={run.run_id}>
                          <TableCell>
                            <input
                              checked={checked}
                              className="h-4 w-4 rounded border-slate-700 bg-transparent text-sky-500"
                              onChange={(event) => {
                                setSelectedRunIds((current) => {
                                  if (event.target.checked) {
                                    return current.includes(run.run_id)
                                      ? current
                                      : [...current, run.run_id];
                                  }
                                  return current.filter((id) => id !== run.run_id);
                                });
                              }}
                              type="checkbox"
                            />
                          </TableCell>
                          <TableCell className="align-top">
                            <div className="font-medium text-slate-100">{run.run_name}</div>
                            <div className="mt-1 text-xs text-slate-500">{run.run_id}</div>
                          </TableCell>
                          <TableCell className="align-top text-slate-300">{run.model_name}</TableCell>
                          <TableCell className="align-top text-slate-300">{run.score.toFixed(4)}</TableCell>
                          <TableCell className="align-top text-slate-400">{run.metric_name}</TableCell>
                          <TableCell className="align-top text-slate-400">{formatDateTime(run.finished_at)}</TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => setAddDialogOpen(false)} type="button" variant="ghost">
              取消
            </Button>
            <Button disabled={addingRuns} onClick={() => void handleAddRuns()} type="button">
              {addingRuns ? "添加中..." : `添加 ${selectedRunIds.length} 条运行`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除排行榜</AlertDialogTitle>
            <AlertDialogDescription>
              删除后排行榜对象会被移除，但原始评测运行和 catalog 数据不会被删除。
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
