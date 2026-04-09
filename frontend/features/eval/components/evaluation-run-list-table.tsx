"use client";

import * as React from "react";
import Link from "next/link";
import { MoreHorizontal, Square, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { cancelEvaluationRun, deleteEvaluationRun } from "@/features/eval/api";
import {
  canCancelEvaluationRun,
  canDeleteEvaluationRun,
  formatEvaluationRunKind,
  getEvaluationRunCancelBlockedReason,
  getEvaluationRunDeleteBlockedReason,
  getEvalStatusMeta
} from "@/features/eval/status";
import type { EvaluationRunSummaryV2 } from "@/types/api";

export function EvaluationRunListTable({ initialRuns }: { initialRuns: EvaluationRunSummaryV2[] }) {
  const router = useRouter();
  const [items, setItems] = React.useState(initialRuns);
  const [confirmTarget, setConfirmTarget] = React.useState<EvaluationRunSummaryV2 | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
  const [pendingCancelId, setPendingCancelId] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setItems(initialRuns);
  }, [initialRuns]);

  async function handleConfirmDelete() {
    if (!confirmTarget) {
      return;
    }
    setPendingDeleteId(confirmTarget.id);
    setActionError(null);

    try {
      await deleteEvaluationRun(confirmTarget.id);
      setItems((current) => current.filter((run) => run.id !== confirmTarget.id));
      setConfirmTarget(null);
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除评测任务失败");
    } finally {
      setPendingDeleteId(null);
    }
  }

  async function handleCancel(run: EvaluationRunSummaryV2) {
    setPendingCancelId(run.id);
    setActionError(null);

    try {
      await cancelEvaluationRun(run.id);
      setItems((current) =>
        current.map((item) => (item.id === run.id ? { ...item, status: "cancelling" } : item))
      );
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "取消评测任务失败");
    } finally {
      setPendingCancelId(null);
    }
  }

  const empty = items.length === 0;

  return (
    <div className="space-y-3">
      {actionError ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {actionError}
        </div>
      ) : null}

      <ConsoleListTableSurface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>任务名称/ID</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>评测模型</TableHead>
              <TableHead>执行进度</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead className="w-[96px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {empty ? (
              <TableRow className="hover:bg-transparent">
                <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={7}>
                  当前筛选条件下没有评测任务。
                </TableCell>
              </TableRow>
            ) : (
              items.map((run) => {
                const statusMeta = getEvalStatusMeta(run.status);
                const deleteBlockedReason = getEvaluationRunDeleteBlockedReason(run.status);
                const cancelBlockedReason = getEvaluationRunCancelBlockedReason(run.status);
                const isDeleting = pendingDeleteId === run.id;
                const isCancelling = pendingCancelId === run.id;
                const progress = getRunDisplayProgress(run);
                const progressPercent = getProgressPercent(progress.done, progress.total);

                return (
                  <TableRow key={run.id}>
                    <TableCell className="min-w-[260px] align-top">
                      <Link className="block" href={`/model/eval-detail/${run.id}`}>
                        <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                          {run.name}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{run.id}</div>
                        {run.error_message ? (
                          <div className="mt-2 line-clamp-2 text-xs text-rose-300">
                            {run.error_message}
                          </div>
                        ) : null}
                      </Link>
                    </TableCell>
                    <TableCell>{formatEvaluationRunKind(run.kind)}</TableCell>
                    <TableCell>
                      <Badge className={statusMeta.className} variant={statusMeta.variant}>
                        {statusMeta.label}
                      </Badge>
                    </TableCell>
                    <TableCell>{run.model_name ?? "--"}</TableCell>
                    <TableCell className="min-w-[180px]">
                      <div className="space-y-2">
                        <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)]">
                          <div
                            className="h-2 rounded-full bg-[#8fffcf]"
                            style={{ width: `${progressPercent}%` }}
                          />
                        </div>
                        <div className="text-xs text-slate-500">
                          {progressPercent}%
                          {typeof progress.done === "number" &&
                          typeof progress.total === "number" &&
                          progress.total > 0
                            ? ` · ${progress.done}/${progress.total}`
                            : ""}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>{formatDateTime(run.created_at)}</TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            aria-label="更多操作"
                            className="h-7 w-7 px-0"
                            disabled={isDeleting}
                            size="sm"
                            variant="ghost"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          <DropdownMenuItem asChild>
                            <Link href={`/model/eval-detail/${run.id}`}>查看详情</Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={!canCancelEvaluationRun(run.status) || isCancelling}
                            onSelect={() => {
                              if (!canCancelEvaluationRun(run.status) || isCancelling) {
                                return;
                              }
                              void handleCancel(run);
                            }}
                            title={cancelBlockedReason ?? undefined}
                          >
                            <Square className="h-4 w-4" />
                            {isCancelling ? "取消中..." : "取消任务"}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={!canDeleteEvaluationRun(run.status)}
                            onSelect={() => {
                              if (!canDeleteEvaluationRun(run.status)) {
                                return;
                              }
                              setActionError(null);
                              setConfirmTarget(run);
                            }}
                            title={deleteBlockedReason ?? undefined}
                          >
                            <Trash2 className="h-4 w-4" />
                            {deleteBlockedReason ? "删除（运行中不可用）" : "删除任务"}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </ConsoleListTableSurface>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open && !pendingDeleteId) {
            setConfirmTarget(null);
          }
        }}
        open={confirmTarget !== null}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除评测任务</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除评测任务「{confirmTarget?.name ?? ""}」及其结果记录，当前操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingDeleteId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500/90 text-white hover:bg-red-500"
              disabled={pendingDeleteId !== null}
              onClick={() => void handleConfirmDelete()}
            >
              {pendingDeleteId ? "处理中..." : "删除任务"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function getProgressPercent(done?: number | null, total?: number | null) {
  if (!total || total <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((Math.max(done ?? 0, 0) / total) * 100)));
}

function getRunDisplayProgress(
  run: Pick<
    EvaluationRunSummaryV2,
    "progress_done" | "progress_total" | "execution_progress_done" | "execution_progress_total"
  >
) {
  if (
    typeof run.execution_progress_total === "number" &&
    run.execution_progress_total > 0
  ) {
    return {
      done: run.execution_progress_done ?? 0,
      total: run.execution_progress_total
    };
  }
  return {
    done: run.progress_done ?? 0,
    total: run.progress_total ?? 0
  };
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}
