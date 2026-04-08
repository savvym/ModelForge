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
import { cancelEvaluationRun, deleteEvaluationRun } from "@/features/eval/api";
import {
  canCancelEvaluationRun,
  canDeleteEvaluationRun,
  getEvaluationRunCancelBlockedReason,
  getEvaluationRunDeleteBlockedReason
} from "@/features/eval/status";

type EvaluationRunDetailActionsProps = {
  runId: string;
  runName: string;
  status: string;
};

export function EvaluationRunDetailActions({
  runId,
  runName,
  status
}: EvaluationRunDetailActionsProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [pendingDelete, setPendingDelete] = React.useState(false);
  const [pendingCancel, setPendingCancel] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const deleteBlockedReason = getEvaluationRunDeleteBlockedReason(status);
  const cancelBlockedReason = getEvaluationRunCancelBlockedReason(status);

  async function handleDelete() {
    setPendingDelete(true);
    setActionError(null);
    try {
      await deleteEvaluationRun(runId);
      router.push("/model/eval");
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "删除评测任务失败");
      setPendingDelete(false);
      setConfirmOpen(false);
    }
  }

  async function handleCancel() {
    setPendingCancel(true);
    setActionError(null);
    try {
      await cancelEvaluationRun(runId);
      router.refresh();
    } catch (error: unknown) {
      setActionError(error instanceof Error ? error.message : "取消评测任务失败");
    } finally {
      setPendingCancel(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <Link href="/model/eval">
          <Button variant="outline">返回评测列表</Button>
        </Link>
        <Link href="/model/eval?tab=runs&create=1">
          <Button>创建新任务</Button>
        </Link>
        <Button
          disabled={!canCancelEvaluationRun(status) || pendingCancel}
          onClick={() => void handleCancel()}
          title={cancelBlockedReason ?? undefined}
          variant="outline"
        >
          {pendingCancel ? "取消中..." : "取消任务"}
        </Button>
        <Button
          className="border border-red-500/40 bg-red-950/20 text-red-100 hover:bg-red-950/40"
          disabled={!canDeleteEvaluationRun(status) || pendingDelete}
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
          if (!pendingDelete) {
            setConfirmOpen(open);
          }
        }}
        open={confirmOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除评测任务</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将移除评测任务「{runName}」及其结果记录，当前操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingDelete}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-500/90 text-white hover:bg-red-500"
              disabled={pendingDelete}
              onClick={() => void handleDelete()}
            >
              {pendingDelete ? "处理中..." : "删除任务"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
