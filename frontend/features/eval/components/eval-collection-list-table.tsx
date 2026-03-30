"use client";

import * as React from "react";
import Link from "next/link";
import { MoreHorizontal, Play, Trash2 } from "lucide-react";
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
import { deleteEvalCollection } from "@/features/eval/api";
import type { EvalCollectionSummary } from "@/types/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function EvalCollectionListTable({
  collections
}: {
  collections: EvalCollectionSummary[];
}) {
  const router = useRouter();
  const [items, setItems] = React.useState(collections);
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);

  async function handleDelete(id: string) {
    try {
      await deleteEvalCollection(id);
      setItems((prev) => prev.filter((c) => c.id !== id));
    } finally {
      setPendingDeleteId(null);
    }
  }

  if (items.length === 0) {
    return (
      <ConsoleListTableSurface>
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <p>暂无评测套件</p>
          <Link href="/model/eval-collections/create">
            <Button variant="outline" size="sm">
              创建第一个评测套件
            </Button>
          </Link>
        </div>
      </ConsoleListTableSurface>
    );
  }

  return (
    <>
      <ConsoleListTableSurface>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[240px]">名称</TableHead>
              <TableHead>描述</TableHead>
              <TableHead className="w-[100px] text-center">Benchmark 数</TableHead>
              <TableHead className="w-[100px] text-center">已运行</TableHead>
              <TableHead className="w-[140px]">创建时间</TableHead>
              <TableHead className="w-[80px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((collection) => (
              <TableRow key={collection.id}>
                <TableCell className="font-medium">{collection.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {collection.description || "—"}
                </TableCell>
                <TableCell className="text-center">{collection.dataset_count}</TableCell>
                <TableCell className="text-center">{collection.job_count}</TableCell>
                <TableCell>{formatDate(collection.created_at)}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() =>
                          router.push(`/model/eval-collections/${collection.id}/run`)
                        }
                      >
                        <Play className="mr-2 h-4 w-4" />
                        运行评测
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => setPendingDeleteId(collection.id)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ConsoleListTableSurface>

      <AlertDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDeleteId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除评测套件？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后评测套件定义将不可恢复，已运行的评测任务不会受影响。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => pendingDeleteId && handleDelete(pendingDeleteId)}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
