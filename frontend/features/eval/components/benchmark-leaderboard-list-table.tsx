"use client";

import * as React from "react";
import Link from "next/link";
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
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { deleteBenchmarkLeaderboard } from "@/features/eval/api";
import { formatLeaderboardMetricName } from "@/features/eval/status";
import type { BenchmarkLeaderboardSummary } from "@/types/api";

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

export function BenchmarkLeaderboardListTable({
  leaderboards
}: {
  leaderboards: BenchmarkLeaderboardSummary[];
}) {
  const router = useRouter();
  const [items, setItems] = React.useState(leaderboards);
  const [pendingDelete, setPendingDelete] = React.useState<BenchmarkLeaderboardSummary | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setItems(leaderboards);
  }, [leaderboards]);

  async function handleDelete() {
    if (!pendingDelete) {
      return;
    }

    setDeleting(true);
    setError(null);
    try {
      await deleteBenchmarkLeaderboard(pendingDelete.id);
      setItems((current) => current.filter((item) => item.id !== pendingDelete.id));
      setPendingDelete(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除排行榜失败");
    } finally {
      setDeleting(false);
    }
  }

  if (items.length === 0) {
    return (
      <ConsoleListTableSurface>
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-sm text-slate-500">
          <p>当前还没有排行榜。先选一个 Benchmark Version，再把已完成的评测任务纳入排行榜。</p>
          <Link href="/model/eval-leaderboards/create">
            <Button size="sm" variant="outline">
              创建第一个排行榜
            </Button>
          </Link>
        </div>
      </ConsoleListTableSurface>
    );
  }

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <ConsoleListTableSurface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>排行榜</TableHead>
              <TableHead>Benchmark</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>评分指标</TableHead>
              <TableHead>任务数</TableHead>
              <TableHead>最近评测</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead className="w-[176px]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((leaderboard) => (
              <TableRow key={leaderboard.id}>
                <TableCell className="min-w-[240px] align-top">
                  <Link href={`/model/eval-leaderboards/${leaderboard.id}`}>
                    <div className="font-medium text-slate-100 transition-colors hover:text-sky-300">
                      {leaderboard.name}
                    </div>
                  </Link>
                </TableCell>
                <TableCell className="align-top">
                  <div className="text-slate-200">{leaderboard.benchmark_display_name}</div>
                  <div className="mt-1 font-mono text-xs text-slate-500">
                    {leaderboard.benchmark_name}
                  </div>
                </TableCell>
                <TableCell className="align-top">
                  <div className="text-slate-200">{leaderboard.benchmark_version_display_name}</div>
                  <div className="mt-1 font-mono text-xs text-slate-500">
                    {leaderboard.benchmark_version_id}
                  </div>
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {formatLeaderboardMetricName(leaderboard.score_metric_name)}
                </TableCell>
                <TableCell className="align-top text-slate-300">
                  {leaderboard.job_count.toLocaleString()}
                </TableCell>
                <TableCell className="align-top text-slate-400">
                  {formatDateTime(leaderboard.latest_eval_at)}
                </TableCell>
                <TableCell className="align-top text-slate-400">
                  {formatDateTime(leaderboard.created_at)}
                </TableCell>
                <TableCell className="align-top">
                  <div className="flex flex-wrap gap-2">
                    <Link href="/model/eval?tab=jobs&create=1">
                      <Button size="sm" variant="outline">
                        创建评测任务
                      </Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setError(null);
                        setPendingDelete(leaderboard);
                      }}
                    >
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ConsoleListTableSurface>

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) {
            setPendingDelete(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除排行榜</AlertDialogTitle>
            <AlertDialogDescription>
              删除后排行榜对象和已关联的任务关系会一起移除，但原始评测任务不会受影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={() => void handleDelete()}
            >
              {deleting ? "删除中..." : "删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
