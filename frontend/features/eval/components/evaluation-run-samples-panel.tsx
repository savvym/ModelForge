"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { getEvaluationRunSamples } from "@/features/eval/api";
import type { EvaluationRunSamplePageV2 } from "@/types/api";

const SAMPLE_PAGE_SIZE = 20;

export function EvaluationRunSamplesPanel({ runId }: { runId: string }) {
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [data, setData] = useState<EvaluationRunSamplePageV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    setLoading(true);
    setError(null);
    void getEvaluationRunSamples(runId, {
      page,
      pageSize: SAMPLE_PAGE_SIZE
    })
      .then((result) => {
        if (!stale) {
          setData(result);
        }
      })
      .catch((requestError: unknown) => {
        if (!stale) {
          setError(requestError instanceof Error ? requestError.message : "加载样本级结果失败。");
        }
      })
      .finally(() => {
        if (!stale) {
          setLoading(false);
        }
      });
    return () => {
      stale = true;
    };
  }, [page, reloadKey, runId]);

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / SAMPLE_PAGE_SIZE));
  const rows = data?.samples ?? [];

  return (
    <Card className="border-border bg-card/80 shadow-none">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <CardTitle className="text-base text-foreground">样本级结果</CardTitle>
            <p className="text-sm text-muted-foreground">
              Canonical sample report，每页 20 条。
            </p>
          </div>
          {total > 0 ? (
            <div className="rounded-lg border border-border bg-card/80 px-3 py-2 text-right text-xs text-muted-foreground">
              第 {page} / {pageCount} 页 · 共 {total} 条
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {loading && !data ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-10 text-sm text-muted-foreground">
            正在加载前 20 条样本级结果...
          </div>
        ) : null}

        {error ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <span>{error}</span>
            <Button onClick={() => setReloadKey((current) => current + 1)} size="sm" type="button" variant="outline">
              重试
            </Button>
          </div>
        ) : null}

        {!loading && !error && total === 0 ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-10 text-sm text-muted-foreground">
            当前任务还没有样本级结果。
          </div>
        ) : null}

        {rows.length ? (
          <div className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>运行项</TableHead>
                  <TableHead>样本 ID</TableHead>
                  <TableHead>子集</TableHead>
                  <TableHead>分数</TableHead>
                  <TableHead>通过</TableHead>
                  <TableHead>原因</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={`${row.run_item_id}-${row.sample.sample_id}`}>
                    <TableCell className="align-top text-foreground">{row.item_display_name}</TableCell>
                    <TableCell className="align-top font-mono text-xs text-foreground">
                      {row.sample.sample_id}
                    </TableCell>
                    <TableCell className="align-top text-foreground">
                      {row.sample.subset_name ?? "--"}
                    </TableCell>
                    <TableCell className="align-top text-foreground">
                      {typeof row.sample.score === "number" ? row.sample.score.toFixed(4) : "--"}
                    </TableCell>
                    <TableCell className="align-top text-foreground">
                      {row.sample.passed ? "是" : "否"}
                    </TableCell>
                    <TableCell className="max-w-[720px] whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {row.sample.reason || row.sample.error || "--"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {pageCount > 1 ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
                <div className="text-xs text-muted-foreground">
                  {formatSampleRange(page, total)}
                </div>
                <div className="flex items-center gap-1.5">
                  <Button
                    disabled={loading || page <= 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    上一页
                  </Button>
                  <div className="min-w-[56px] text-center text-xs text-muted-foreground">
                    {page} / {pageCount}
                  </div>
                  <Button
                    disabled={loading || page >= pageCount}
                    onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    下一页
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function formatSampleRange(page: number, total: number) {
  const start = total ? (page - 1) * SAMPLE_PAGE_SIZE + 1 : 0;
  const end = Math.min(page * SAMPLE_PAGE_SIZE, total);
  return `${start} - ${end} / 共 ${total} 条`;
}
