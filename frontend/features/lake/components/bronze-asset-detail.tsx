"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import {
  Archive,
  Clipboard,
  ExternalLink,
  FolderOpen,
  Loader2,
  RefreshCw
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  archiveBronzeAsset,
  getBronzeArtifactSignedUrl,
  refreshBronzeAsset
} from "@/features/lake/api";
import { getApiRootUrl } from "@/lib/api-client/http";
import type { BronzeArtifactSummary, BronzeAssetDetail } from "@/types/api";

export function BronzeAssetDetailPanel({ asset }: { asset: BronzeAssetDetail }) {
  const router = useRouter();
  const [detail, setDetail] = React.useState(asset);
  const [pendingAction, setPendingAction] = React.useState<string | null>(null);

  async function handleRefresh() {
    setPendingAction("refresh");
    try {
      await refreshBronzeAsset(detail.id);
      setDetail((current) => ({
        ...current,
        status: "capturing",
        hash_status: "pending",
        updated_at: new Date().toISOString()
      }));
      toast.success("已提交刷新抓取");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "刷新抓取失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleArchive() {
    setPendingAction("archive");
    try {
      const archived = await archiveBronzeAsset(detail.id);
      setDetail(archived);
      toast.success("已归档 Bronze 资产");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "归档失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleOpenArtifact(artifact: BronzeArtifactSummary) {
    setPendingAction(`artifact:${artifact.id}`);
    try {
      const signed = await getBronzeArtifactSignedUrl(artifact.id);
      const targetUrl = signed.url.startsWith("/")
        ? `${getApiRootUrl()}${signed.url}`
        : signed.url;
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "打开 artifact 失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleCopy(value: string | null | undefined) {
    if (!value) {
      return;
    }
    await navigator.clipboard.writeText(value);
    toast.success("已复制 object key");
  }

  const statusMeta = getBronzeStatusMeta(detail.status);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-2">
            <Link className="text-sm text-muted-foreground hover:text-foreground" href="/lake-assets">
              数据湖 / {detail.id}
            </Link>
          </div>
          <h1 className="truncate text-3xl font-semibold tracking-tight text-foreground">{detail.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
            <span>{formatSourceTypeLabel(detail.source_type)}</span>
            <span>{detail.product || detail.provider || "未归类"}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={pendingAction === "refresh"} onClick={() => void handleRefresh()} size="sm" type="button" variant="outline">
            {pendingAction === "refresh" ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
            刷新抓取
          </Button>
          <Button disabled type="button" size="sm" variant="outline">
            生成 Silver
          </Button>
          <Button disabled={pendingAction === "archive"} onClick={() => void handleArchive()} size="sm" type="button" variant="outline">
            {pendingAction === "archive" ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <Archive data-icon="inline-start" />}
            归档
          </Button>
          {detail.object_key ? (
            <Link href={buildObjectHref(detail)}>
              <Button size="sm" type="button" variant="outline">
                <FolderOpen data-icon="inline-start" />
                打开对象
              </Button>
            </Link>
          ) : null}
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="h-auto w-full justify-start gap-1 rounded-lg border border-border/60 bg-card/60 p-1">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="snapshots">快照</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
          <TabsTrigger value="logs">抓取日志</TabsTrigger>
          <TabsTrigger value="lineage">下游血缘</TabsTrigger>
        </TabsList>

        <TabsContent className="mt-4" value="overview">
          <div className="grid gap-3 lg:grid-cols-3">
            <Card className="border-border bg-card/80 lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">SourceAsset</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                <DetailRow label="source locator" value={detail.source_uri || "-"} wide />
                <DetailRow label="source_doc_id" value={detail.id} />
                <DetailRow label="provider" value={detail.provider || "-"} />
                <DetailRow label="product" value={detail.product || "-"} />
                <DetailRow label="latest snapshot" value={detail.latest_snapshot_id || "无 snapshot"} />
                <DetailRow label="content_hash / text_hash" value={detail.snapshots[0]?.content_hash || detail.snapshots[0]?.text_hash || "-"} />
                <DetailRow label="artifact count" value={`${detail.artifact_count} files / ${detail.image_count} images`} />
                <DetailRow label="ingestion job" value={detail.ingestion_job_id} />
              </CardContent>
            </Card>
            <Card className="border-border bg-card/80">
              <CardHeader>
                <CardTitle className="text-base">Pipeline</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <DetailRow label="Silver" value={detail.lineage.silver_ready ? "已进入 Silver" : "未进入 Silver"} />
                <DetailRow label="Gold 产物" value={detail.lineage.gold_outputs.length ? `${detail.lineage.gold_outputs.length} 个` : "无"} />
                <DetailRow label="Hash 状态" value={detail.hash_status} />
                <DetailRow label="更新时间" value={formatDateTime(detail.updated_at)} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent className="mt-4" value="snapshots">
          <Card className="border-border bg-card/80">
            <CardContent className="pt-5">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>snapshot_time</TableHead>
                    <TableHead>status</TableHead>
                    <TableHead>raw_hash</TableHead>
                    <TableHead>rendered_hash</TableHead>
                    <TableHead>text_hash</TableHead>
                    <TableHead>artifact count</TableHead>
                    <TableHead>diff</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.snapshots.length === 0 ? (
                    <EmptyRow colSpan={7} message="当前资产尚未生成 snapshot" />
                  ) : (
                    detail.snapshots.map((snapshot) => (
                      <TableRow key={snapshot.id}>
                        <TableCell>{formatDateTime(snapshot.snapshot_time)}</TableCell>
                        <TableCell>{snapshot.status}</TableCell>
                        <TableCell className="max-w-[180px] truncate">{snapshot.raw_hash || "-"}</TableCell>
                        <TableCell className="max-w-[180px] truncate">{snapshot.rendered_hash || "-"}</TableCell>
                        <TableCell className="max-w-[180px] truncate">{snapshot.text_hash || "-"}</TableCell>
                        <TableCell>{snapshot.artifact_count}</TableCell>
                        <TableCell>{snapshot.diff_status}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent className="mt-4" value="artifacts">
          <Card className="border-border bg-card/80">
            <CardContent className="pt-5">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>artifact</TableHead>
                    <TableHead>type</TableHead>
                    <TableHead>object key</TableHead>
                    <TableHead>size</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.artifacts.length === 0 ? (
                    <EmptyRow colSpan={5} message="当前资产尚未写入 artifacts" />
                  ) : (
                    detail.artifacts.map((artifact) => (
                      <TableRow key={artifact.id}>
                        <TableCell>
                          <div className="font-medium text-foreground">{artifact.name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{artifact.id}</div>
                        </TableCell>
                        <TableCell>{artifact.artifact_type}</TableCell>
                        <TableCell className="max-w-[420px] truncate">{artifact.object_key || "-"}</TableCell>
                        <TableCell>{formatFileSize(artifact.size_bytes ?? 0)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              disabled={!artifact.object_key}
                              onClick={() => void handleCopy(artifact.object_key)}
                              size="sm"
                              type="button"
                              variant="ghost"
                            >
                              <Clipboard data-icon="inline-start" />
                              复制 key
                            </Button>
                            <Button
                              disabled={!artifact.object_key || pendingAction === `artifact:${artifact.id}`}
                              onClick={() => void handleOpenArtifact(artifact)}
                              size="sm"
                              type="button"
                              variant="outline"
                            >
                              {pendingAction === `artifact:${artifact.id}` ? (
                                <Loader2 className="animate-spin" data-icon="inline-start" />
                              ) : (
                                <ExternalLink data-icon="inline-start" />
                              )}
                              预览
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent className="mt-4" value="logs">
          <Card className="border-border bg-card/80">
            <CardContent className="pt-5">
              {detail.logs.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">暂无抓取日志</div>
              ) : (
                <div className="flex flex-col gap-2">
                  {detail.logs.map((line, index) => (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-2 text-sm text-foreground" key={`${line}-${index}`}>
                      {line}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent className="mt-4" value="lineage">
          <Card className="border-border bg-card/80">
            <CardContent className="grid gap-4 pt-5 md:grid-cols-3">
              <DetailRow label="是否已进入 Silver" value={detail.lineage.silver_ready ? "是" : "否"} />
              <DetailRow label="Gold 产物" value={detail.lineage.gold_outputs.length ? detail.lineage.gold_outputs.join(", ") : "无"} />
              <DetailRow label="下游任务" value={detail.lineage.downstream_jobs.length ? detail.lineage.downstream_jobs.join(", ") : "无"} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function DetailRow({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "md:col-span-2" : undefined}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 break-words text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <TableRow>
      <TableCell className="py-10 text-center text-sm text-muted-foreground" colSpan={colSpan}>
        {message}
      </TableCell>
    </TableRow>
  );
}

function buildObjectHref(asset: BronzeAssetDetail) {
  if (!asset.object_key) {
    return "/data";
  }
  const params = new URLSearchParams();
  if (asset.object_bucket) {
    params.set("bucket", asset.object_bucket);
  }
  const parentPrefix = asset.object_key.includes("/")
    ? `${asset.object_key.slice(0, asset.object_key.lastIndexOf("/"))}/`
    : asset.object_key;
  params.set("prefix", parentPrefix);
  return `/data?${params.toString()}`;
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

function formatFileSize(sizeBytes: number) {
  if (sizeBytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = sizeBytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

function formatSourceTypeLabel(value: string) {
  const labelByType: Record<string, string> = {
    directory: "对象目录",
    document: "文档",
    image: "图片",
    markdown: "Markdown",
    markdown_package: "Markdown + Images",
    object_key: "对象文件",
    object_prefix: "对象目录",
    object_storage: "对象存储",
    pdf: "PDF",
    sitemap: "Sitemap",
    upload: "上传",
    uploaded_package: "上传包",
    url: "URL",
    url_list: "URL 列表",
    web_page: "网页",
    website_batch: "批量网页"
  };
  return labelByType[value] ?? value;
}

function getBronzeStatusMeta(status: string) {
  const metaByStatus: Record<string, { label: string; className: string }> = {
    archived: {
      label: "归档",
      className: "border-border bg-muted/50 text-muted-foreground"
    },
    captured: {
      label: "已保存",
      className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
    },
    capturing: {
      label: "抓取中",
      className: "border-amber-500/25 bg-amber-500/10 text-amber-200"
    },
    changed: {
      label: "已变化",
      className: "border-sky-500/25 bg-sky-500/10 text-sky-200"
    },
    failed: {
      label: "失败",
      className: "border-rose-500/25 bg-rose-500/10 text-rose-200"
    },
    registered: {
      label: "已登记",
      className: "border-violet-500/25 bg-violet-500/10 text-violet-200"
    },
    unchanged: {
      label: "未变化",
      className: "border-border bg-secondary text-secondary-foreground"
    }
  };
  return (
    metaByStatus[status] ?? {
      label: status,
      className: "border-border bg-muted/40 text-foreground"
    }
  );
}
