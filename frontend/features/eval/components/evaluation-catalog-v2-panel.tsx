"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { deleteEvalSpec, deleteEvalSuite } from "@/features/eval/api";
import type { EvaluationCatalogResponseV2 } from "@/types/api";

export function EvaluationCatalogV2Panel({ catalog }: { catalog: EvaluationCatalogResponseV2 }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">评测套件</h2>
          <p className="text-sm text-slate-400">
            套件是一等公民，负责承接百炼式基线评测和多基准组合评测。
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {catalog.suites.map((suite) => {
            const activeVersion = suite.versions.find((version) => version.enabled) ?? suite.versions[0] ?? null;
            return (
              <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none" key={suite.id}>
                <CardHeader className="space-y-2">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle className="text-base text-slate-50">{suite.display_name}</CardTitle>
                        <Badge variant="outline">{suite.name}</Badge>
                      </div>
                      <p className="text-sm leading-6 text-slate-400">
                        {suite.description || "当前套件没有额外描述。"}
                      </p>
                    </div>
                    <CatalogActions
                      deleteAction={() => deleteEvalSuite(suite.name)}
                      deleteDescription={`删除后将移除 ${suite.display_name} 及其版本编排。若它仍被运行任务或排行榜引用，系统会拒绝删除。`}
                      deleteLabel="删除套件"
                      editHref={`/model/eval-suites/${encodeURIComponent(suite.name)}/edit`}
                      title={suite.display_name}
                    />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <MetaCard label="激活版本" value={activeVersion?.display_name ?? "--"} />
                    <MetaCard
                      label="评测项数量"
                      value={String(activeVersion?.items.filter((item) => item.enabled).length ?? 0)}
                    />
                  </div>
                  {activeVersion?.items.length ? (
                    <div className="flex flex-wrap gap-2">
                      {activeVersion.items
                        .filter((item) => item.enabled)
                        .map((item) => (
                          <span
                            className="rounded-full border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-3 py-1 text-xs text-slate-300"
                            key={item.id}
                          >
                            {item.group_name ? `${item.group_name} · ` : ""}
                            {item.display_name}
                          </span>
                        ))}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
                      当前套件还没有启用的评测项。
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">评测类型与版本</h2>
          <p className="text-sm text-slate-400">
            每个评测类型可以挂多个不可变版本，运行时只消费冻结后的版本快照。
          </p>
        </div>
        <div className="overflow-hidden rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>评测类型</TableHead>
                <TableHead>能力分类</TableHead>
                <TableHead>推荐版本</TableHead>
                <TableHead>执行引擎</TableHead>
                <TableHead>样本量</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {catalog.specs.map((spec) => {
                const recommendedVersion =
                  spec.versions.find((version) => version.is_recommended && version.enabled) ??
                  spec.versions.find((version) => version.enabled) ??
                  null;
                return (
                  <TableRow key={spec.id}>
                    <TableCell className="min-w-[240px] align-top">
                      <div className="font-medium text-slate-100">{spec.display_name}</div>
                      <div className="mt-1 text-xs text-slate-500">{spec.name}</div>
                      {spec.description ? (
                        <div className="mt-2 max-w-[440px] text-sm leading-6 text-slate-400">
                          {spec.description}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {[spec.capability_group, spec.capability_category].filter(Boolean).join(" / ") || "--"}
                    </TableCell>
                    <TableCell>
                      {recommendedVersion ? (
                        <div className="space-y-1">
                          <div className="text-sm text-slate-200">{recommendedVersion.display_name}</div>
                          <div className="text-xs text-slate-500">{recommendedVersion.version}</div>
                        </div>
                      ) : (
                        "--"
                      )}
                    </TableCell>
                    <TableCell>
                      {recommendedVersion
                        ? `${recommendedVersion.engine} / ${recommendedVersion.execution_mode}`
                        : "--"}
                    </TableCell>
                    <TableCell>{recommendedVersion?.sample_count ?? "--"}</TableCell>
                    <TableCell className="text-right">
                      <CatalogActions
                        deleteAction={() => deleteEvalSpec(spec.name)}
                        deleteDescription={`删除后将移除 ${spec.display_name} 及其版本。若它仍被套件、运行任务或排行榜引用，系统会拒绝删除。`}
                        deleteLabel="删除类型"
                        editHref={`/model/eval-specs/${encodeURIComponent(spec.name)}/edit`}
                        title={spec.display_name}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}

function CatalogActions({
  editHref,
  deleteAction,
  deleteLabel,
  deleteDescription,
  title
}: {
  editHref: string;
  deleteAction: () => Promise<void>;
  deleteLabel: string;
  deleteDescription: string;
  title: string;
}) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleDelete() {
    try {
      setPending(true);
      setError(null);
      await deleteAction();
      setOpen(false);
      router.refresh();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : `${deleteLabel}失败`);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <Link className={buttonVariants({ size: "sm", variant: "outline" })} href={editHref}>
        编辑
      </Link>
      <AlertDialog
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) {
            setError(null);
          }
        }}
        open={open}
      >
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="ghost">
            删除
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除 {title}</AlertDialogTitle>
            <AlertDialogDescription>{deleteDescription}</AlertDialogDescription>
            {error ? (
              <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
                {error}
              </div>
            ) : null}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-rose-500 text-white hover:bg-rose-400"
              disabled={pending}
              onClick={(event) => {
                event.preventDefault();
                void handleDelete();
              }}
            >
              {pending ? "删除中..." : deleteLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-200">{value}</div>
    </div>
  );
}
