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
import { deleteEvalJob, stopEvalJob } from "@/features/eval/api";
import {
  canDeleteEvalJob,
  canStopEvalJob,
  formatInferenceMode,
  formatModelSource,
  getEvalDeleteBlockedReason,
  getEvalStopBlockedReason,
  getEvalStatusMeta
} from "@/features/eval/status";
import type { EvalJobSummary } from "@/types/api";

export function EvalJobListTable({ initialJobs }: { initialJobs: EvalJobSummary[] }) {
  const router = useRouter();
  const [items, setItems] = React.useState(initialJobs);
  const [confirmTarget, setConfirmTarget] = React.useState<EvalJobSummary | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
  const [pendingStopId, setPendingStopId] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setItems(initialJobs);
  }, [initialJobs]);

  async function handleConfirmDelete() {
    if (!confirmTarget) {
      return;
    }

    setPendingDeleteId(confirmTarget.id);
    setActionError(null);

    try {
      await deleteEvalJob(confirmTarget.id);
      setItems((current) => current.filter((job) => job.id !== confirmTarget.id));
      setConfirmTarget(null);
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除评测任务失败");
    } finally {
      setPendingDeleteId(null);
    }
  }

  async function handleStop(job: EvalJobSummary) {
    setPendingStopId(job.id);
    setActionError(null);

    try {
      const updated = await stopEvalJob(job.id);
      setItems((current) => current.map((item) => (item.id === job.id ? updated : item)));
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "停止评测任务失败");
    } finally {
      setPendingStopId(null);
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
              <TableHead>描述</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>模型服务</TableHead>
              <TableHead>推理方式</TableHead>
              <TableHead>评测进度</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead>创建人</TableHead>
              <TableHead className="w-[96px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {empty ? (
              <TableRow className="hover:bg-transparent">
                <TableCell className="py-16 text-center text-sm text-slate-500" colSpan={9}>
                  当前筛选条件下没有评测任务。
                </TableCell>
              </TableRow>
            ) : (
              items.map((job) => {
                const statusMeta = getEvalStatusMeta(job.status);
                const deleteBlockedReason = getEvalDeleteBlockedReason(job.status);
                const stopBlockedReason = getEvalStopBlockedReason(job.status);
                const isDeleting = pendingDeleteId === job.id;
                const isStopping = pendingStopId === job.id;

                return (
                  <TableRow key={job.id}>
                    <TableCell className="min-w-[220px] align-top">
                      <Link className="block" href={`/model/eval-detail/${job.id}`}>
                        <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                          {job.name}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{job.id}</div>
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[220px] text-sm text-slate-400">
                      <div>{job.description || "-"}</div>
                      {job.error_message ? (
                        <div className="mt-1 line-clamp-2 text-xs text-rose-300">
                          {job.error_message}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Badge className={statusMeta.className} variant={statusMeta.variant}>
                        {statusMeta.label}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatModelSource(job.model_source)}</TableCell>
                    <TableCell>{formatInferenceMode(job.inference_mode)}</TableCell>
                    <TableCell className="min-w-[180px]">
                      <div className="space-y-2">
                        <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)]">
                          <div
                            className="h-2 rounded-full bg-[#8fffcf]"
                            style={{ width: `${job.progress_percent}%` }}
                          />
                        </div>
                        <div className="text-xs text-slate-500">
                          {job.progress_percent}%
                          {typeof job.progress_done === "number" &&
                          typeof job.progress_total === "number" &&
                          job.progress_total > 0
                            ? ` · ${job.progress_done}/${job.progress_total}`
                            : ""}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>{formatDateTime(job.created_at)}</TableCell>
                    <TableCell>{job.created_by ?? "--"}</TableCell>
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
                            <Link href={`/model/eval-detail/${job.id}`}>查看详情</Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={!canStopEvalJob(job.status) || isStopping}
                            onSelect={() => {
                              if (!canStopEvalJob(job.status) || isStopping) {
                                return;
                              }
                              void handleStop(job);
                            }}
                            title={stopBlockedReason ?? undefined}
                          >
                            <Square className="h-4 w-4" />
                            {isStopping ? "停止中..." : "停止任务"}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={!canDeleteEvalJob(job.status)}
                            onSelect={() => {
                              if (!canDeleteEvalJob(job.status)) {
                                return;
                              }
                              setActionError(null);
                              setConfirmTarget(job);
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

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
