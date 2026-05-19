"use client";

import Link from "next/link";
import { File, FileText, Folder, FolderOpen, Image as ImageIcon } from "lucide-react";
import type { LakeTreeEntry } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";

const TEXT_EXT = new Set([
  "md",
  "mdx",
  "txt",
  "json",
  "yaml",
  "yml",
  "csv",
  "tsv",
  "html",
  "js",
  "ts",
  "tsx",
  "py",
  "sh",
  "log"
]);
const IMAGE_EXT = new Set(["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"]);

function pickIcon(entry: LakeTreeEntry) {
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

function entryHref(repoId: string, branch: string, entry: LakeTreeEntry): string {
  const base = `/data-lake/${repoId}`;
  const encodedPath = entry.path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  if (entry.type === "dir") {
    return `${base}/tree/${encodeURIComponent(branch)}/${encodedPath}`;
  }
  return `${base}/blob/${encodeURIComponent(branch)}/${encodedPath}`;
}

export function RepoFileTree({
  repoId,
  branch,
  path,
  entries
}: {
  repoId: string;
  branch: string;
  path: string;
  entries: LakeTreeEntry[];
}) {
  const sorted = [...entries].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  if (sorted.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/60 bg-card/40 px-4 py-12 text-center text-sm text-muted-foreground">
        <FolderOpen className="mx-auto mb-3 size-8 opacity-60" />
        当前目录为空。从右上角「上传文件」开始放入内容。
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-lg border border-border/70 bg-card/60">
      <Table>
        <TableBody>
          {path ? (
            <TableRow className="hover:bg-muted/30">
              <TableCell className="w-[36px]">
                <Folder className="size-4 text-muted-foreground" />
              </TableCell>
              <TableCell colSpan={3}>
                <Link
                  href={`/data-lake/${repoId}/tree/${encodeURIComponent(branch)}/${path
                    .split("/")
                    .slice(0, -1)
                    .map((segment) => encodeURIComponent(segment))
                    .join("/")}`}
                  className="text-muted-foreground hover:underline"
                >
                  ..
                </Link>
              </TableCell>
            </TableRow>
          ) : null}
          {sorted.map((entry) => {
            const Icon = pickIcon(entry);
            return (
              <TableRow key={entry.path} className="hover:bg-muted/30">
                <TableCell className="w-[36px]">
                  <Icon
                    className={
                      entry.type === "dir"
                        ? "size-4 text-amber-500"
                        : "size-4 text-muted-foreground"
                    }
                  />
                </TableCell>
                <TableCell>
                  <Link href={entryHref(repoId, branch, entry)} className="text-foreground hover:underline">
                    {entry.name}
                  </Link>
                  {entry.is_lfs ? (
                    <Badge variant="outline" className="ml-2 text-[10px]">
                      LFS
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell className="w-[120px] text-right text-xs text-muted-foreground">
                  {entry.type === "file" ? humanSize(entry.size) : ""}
                </TableCell>
                <TableCell className="w-[80px] text-right text-xs text-muted-foreground">
                  {entry.type}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
