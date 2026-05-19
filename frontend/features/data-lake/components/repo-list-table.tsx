"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MoreVertical, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deleteRepo } from "@/features/data-lake/api";
import type { LakeRepoSummary } from "@/types/api";

const RELATIVE = new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" });

function formatRelative(iso: string): string {
  const date = new Date(iso);
  const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
  const abs = Math.abs(diffSec);
  const table: Array<[number, Intl.RelativeTimeFormatUnit]> = [
    [60, "second"],
    [3600, "minute"],
    [86400, "hour"],
    [86400 * 7, "day"],
    [86400 * 30, "week"],
    [86400 * 365, "month"]
  ];
  let unit: Intl.RelativeTimeFormatUnit = "year";
  let divisor = 86400 * 365;
  for (const [boundary, candidate] of table) {
    if (abs < boundary) {
      unit = candidate;
      divisor = boundary === 60 ? 1 : table[table.findIndex(([b]) => b === boundary) - 1]?.[0] ?? 1;
      break;
    }
  }
  return RELATIVE.format(Math.round(diffSec / divisor), unit);
}

export function RepoListTable({ repos: initial }: { repos: LakeRepoSummary[] }) {
  const router = useRouter();
  const [repos, setRepos] = useState(initial);
  const [pending, setPending] = useState<LakeRepoSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!pending) return;
    setDeleting(true);
    try {
      await deleteRepo(pending.id);
      setRepos((current) => current.filter((repo) => repo.id !== pending.id));
      toast.success(`仓库「${pending.display_name}」已删除`);
      router.refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除失败";
      toast.error(message);
    } finally {
      setDeleting(false);
      setPending(null);
    }
  }

  if (repos.length === 0) {
    return (
      <Empty className="border border-dashed border-border/60 bg-card/60">
        <EmptyHeader>
          <EmptyTitle>还没有仓库</EmptyTitle>
          <EmptyDescription>
            点击右上角「新建仓库」开始管理你的原始资产 —— md、图片、HTML 都可以放进同一个仓库。
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent />
      </Empty>
    );
  }

  return (
    <>
      <div className="overflow-hidden rounded-lg border border-border/70 bg-card/60">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40">
              <TableHead className="w-[36%]">仓库</TableHead>
              <TableHead>描述</TableHead>
              <TableHead className="w-[120px]">默认分支</TableHead>
              <TableHead className="w-[120px]">状态</TableHead>
              <TableHead className="w-[160px]">最近更新</TableHead>
              <TableHead className="w-[60px] text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {repos.map((repo) => (
              <TableRow key={repo.id} className="hover:bg-muted/30">
                <TableCell>
                  <Link
                    href={`/data-lake/${repo.id}`}
                    className="flex flex-col gap-0.5 text-foreground hover:underline"
                  >
                    <span className="font-medium">
                      {repo.gitea_org}/<span className="font-semibold">{repo.name}</span>
                    </span>
                    <span className="text-xs text-muted-foreground">{repo.display_name}</span>
                  </Link>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {repo.description || <span className="text-muted-foreground/60">—</span>}
                </TableCell>
                <TableCell className="font-mono text-xs">{repo.default_branch}</TableCell>
                <TableCell>
                  <Badge variant={repo.status === "active" ? "secondary" : "outline"}>
                    {repo.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {formatRelative(repo.updated_at)}
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="icon" variant="ghost">
                        <MoreVertical className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onSelect={(event) => {
                          event.preventDefault();
                          setPending(repo);
                        }}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="mr-2 size-4" /> 删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <AlertDialog open={pending !== null} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除仓库</AlertDialogTitle>
            <AlertDialogDescription>
              这会同时删除 Gitea 上的对应仓库及其所有文件，无法恢复。
              {pending ? `仓库：${pending.gitea_org}/${pending.name}` : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                handleDelete();
              }}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? "删除中…" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
