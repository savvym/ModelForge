"use client";

import Link from "next/link";
import { Download, File, FileText, Folder, Image as ImageIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { buildTrainingCosDownloadUrl } from "@/features/training-cos/api";
import { TrainingCosHuggingFaceSyncDialog } from "@/features/training-cos/components/huggingface-sync-dialog";
import type { TrainingCosEntry } from "@/types/api";

const TEXT_EXT = new Set([
  "md",
  "mdx",
  "txt",
  "json",
  "jsonl",
  "yaml",
  "yml",
  "csv",
  "tsv",
  "log"
]);
const IMAGE_EXT = new Set(["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"]);

function pickIcon(entry: TrainingCosEntry) {
  if (entry.type === "dir") return Folder;
  const ext = entry.name.split(".").pop()?.toLowerCase() ?? "";
  if (IMAGE_EXT.has(ext)) return ImageIcon;
  if (TEXT_EXT.has(ext)) return FileText;
  return File;
}

function humanSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function entryHref(entry: TrainingCosEntry): string {
  const cleaned = entry.key.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = cleaned.split("/").map((segment) => encodeURIComponent(segment));
  return entry.type === "dir"
    ? `/training-cos/${segments.join("/")}`
    : `/training-cos/blob/${segments.join("/")}`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("zh-CN");
  } catch {
    return value;
  }
}

export function TrainingCosBrowserTable({
  prefix,
  parentPrefix,
  entries,
  truncated,
  nextHref
}: {
  prefix: string;
  parentPrefix: string | null;
  entries: TrainingCosEntry[];
  truncated: boolean;
  nextHref?: string | null;
}) {
  if (entries.length === 0 && !parentPrefix) {
    return (
      <Empty className="border border-dashed border-border/60 bg-card/60">
        <EmptyHeader>
          <EmptyTitle>这个 bucket 没有内容</EmptyTitle>
          <EmptyDescription>
            可以在系统配置里确认 endpoint / bucket / 凭据是否正确，或先通过其他方式向训练 COS 写入数据。
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
              <TableHead className="w-[48%]">名称</TableHead>
              <TableHead className="w-[140px]">大小</TableHead>
              <TableHead className="w-[200px]">最近修改</TableHead>
              <TableHead className="w-[160px] text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {parentPrefix !== null ? (
              <TableRow className="hover:bg-muted/30">
                <TableCell colSpan={4}>
                  <Link
                    href={
                      parentPrefix
                        ? `/training-cos/${parentPrefix
                            .split("/")
                            .filter(Boolean)
                            .map((segment) => encodeURIComponent(segment))
                            .join("/")}`
                        : "/training-cos"
                    }
                    className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground"
                  >
                    <Folder className="size-4" />
                    ..
                  </Link>
                </TableCell>
              </TableRow>
            ) : null}
            {entries.map((entry) => {
              const Icon = pickIcon(entry);
              return (
                <TableRow key={entry.key} className="hover:bg-muted/30">
                  <TableCell>
                    <Link
                      href={entryHref(entry)}
                      className="inline-flex items-center gap-2 text-foreground hover:underline"
                    >
                      <Icon
                        className={entry.type === "dir" ? "size-4 text-amber-500" : "size-4 text-muted-foreground"}
                      />
                      {entry.name || entry.key}
                    </Link>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {entry.type === "file" ? humanSize(entry.size) : ""}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {entry.type === "file" ? formatTime(entry.last_modified) : ""}
                  </TableCell>
                  <TableCell className="text-right">
                    {entry.type === "file" ? (
                      <a
                        href={buildTrainingCosDownloadUrl(entry.key)}
                        download={entry.name}
                        className={buttonVariants({ size: "sm", variant: "outline" })}
                      >
                        <Download className="mr-1.5 size-3.5" />
                        下载
                      </a>
                    ) : (
                      <TrainingCosHuggingFaceSyncDialog entry={entry} />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      {truncated ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <Badge variant="outline">仍有更多对象未列出</Badge>
          {nextHref ? (
            <Link href={nextHref} className="text-foreground hover:underline">
              加载下一页 →
            </Link>
          ) : (
            <span>缩小 prefix 或在 URL 中追加路径以继续浏览。</span>
          )}
        </div>
      ) : null}
    </>
  );
}
