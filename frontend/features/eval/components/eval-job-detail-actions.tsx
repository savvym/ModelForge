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
import { deleteEvalJob, stopEvalJob } from "@/features/eval/api";
import {
  canDeleteEvalJob,
  canStopEvalJob,
  getEvalDeleteBlockedReason,
  getEvalStopBlockedReason
} from "@/features/eval/status";

type EvalJobDetailActionsProps = {
  jobId: string;
  jobName: string;
  status: string;
};

export function EvalJobDetailActions({
  jobId,
  jobName,
  status
}: EvalJobDetailActionsProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const [stopPending, setStopPending] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const deleteBlockedReason = getEvalDeleteBlockedReason(status);
  const stopBlockedReason = getEvalStopBlockedReason(status);

  async function handleDelete() {
    setPending(true);
    setActionError(null);

    try {
      await deleteEvalJob(jobId);
      router.push("/model/eval");
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除评测任务失败");
      setPending(false);
      setConfirmOpen(false);
    }
  }

  async function handleStop() {
    setStopPending(true);
    setActionError(null);

    try {
      await stopEvalJob(jobId);
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "停止评测任务失败");
    } finally {
      setStopPending(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <Link href="/model/eval">
          <Button variant="outline">返回评测列表</Button>
        </Link>
        <Link href="/model/eval?tab=jobs&create=1">
          <Button>创建新任务</Button>
        </Link>
        <Button
          disabled={!canStopEvalJob(status) || stopPending}
          onClick={() => void handleStop()}
          title={stopBlockedReason ?? undefined}
          variant="outline"
        >
          {stopPending ? "停止中..." : "停止任务"}
        </Button>
        <Button
          className="border border-red-500/40 bg-red-950/20 text-red-100 hover:bg-red-950/40"
          disabled={!canDeleteEvalJob(status) || pending}
          onClick={() => {
            setActionError(null);
            setConfirmOpen(true);
          }}
          title={deleteBlockedReason ?? undefined}
          variant="outline"
        >
          删除任务
        </Button>
      </div>

      {actionError ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {actionError}
        </div>
      ) : null}

      <AlertDialog
        onOpenChange={(open) => {
          if (!pending) {
            setConfirmOpen(open);
          }
        }}
        open={confirmOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除评测任务</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除评测任务「{jobName}」及其结果记录，当前操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500/90 text-white hover:bg-red-500"
              disabled={pending}
              onClick={() => void handleDelete()}
            >
              {pending ? "处理中..." : "删除任务"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
