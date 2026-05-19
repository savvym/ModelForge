"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderUp, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { uploadFiles } from "@/features/data-lake/api";

const MAX_TOTAL_BYTES = 25 * 1024 * 1024;

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  if (typeof window !== "undefined") {
    return window.btoa(binary);
  }
  return Buffer.from(buffer).toString("base64");
}

type PreparedFile = { path: string; content_b64: string };

async function prepareFiles(files: FileList | null, prefix: string): Promise<{ files: PreparedFile[]; totalBytes: number }> {
  if (!files || files.length === 0) return { files: [], totalBytes: 0 };
  const cleanedPrefix = prefix.trim().replace(/^\/+|\/+$/g, "");
  const prepared: PreparedFile[] = [];
  let totalBytes = 0;
  for (const file of Array.from(files)) {
    totalBytes += file.size;
    const rel = ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name)
      .replace(/\\/g, "/")
      .replace(/^\/+/, "");
    const path = cleanedPrefix ? `${cleanedPrefix}/${rel}` : rel;
    const buffer = await file.arrayBuffer();
    prepared.push({ path, content_b64: arrayBufferToBase64(buffer) });
  }
  return { files: prepared, totalBytes };
}

export function RepoUploadDialog({
  repoId,
  branch,
  currentPath
}: {
  repoId: string;
  branch: string;
  currentPath: string;
}) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("Add files");
  const [pickedFiles, setPickedFiles] = useState<FileList | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setMessage("Add files");
    setPickedFiles(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (folderInputRef.current) folderInputRef.current.value = "";
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pickedFiles || pickedFiles.length === 0) {
      toast.error("请先选择要上传的文件或文件夹");
      return;
    }
    setSubmitting(true);
    try {
      const { files, totalBytes } = await prepareFiles(pickedFiles, currentPath);
      if (totalBytes > MAX_TOTAL_BYTES) {
        throw new Error(
          `单次提交不能超过 ${(MAX_TOTAL_BYTES / (1024 * 1024)).toFixed(0)} MiB（当前 ${(totalBytes / (1024 * 1024)).toFixed(1)} MiB），请拆分提交或上传到 LFS。`
        );
      }
      const response = await uploadFiles(repoId, {
        branch,
        message: message.trim() || "Add files",
        files
      });
      toast.success(`已提交 ${files.length} 个文件，commit ${response.commit_sha.slice(0, 7)}`);
      reset();
      setOpen(false);
      router.refresh();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "上传失败";
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Upload className="mr-2 size-4" /> 上传文件
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>上传到 {branch}</DialogTitle>
            <DialogDescription>
              将选中的文件作为一次 commit 提交，目标分支 <span className="font-mono">{branch}</span>
              {currentPath ? <>，路径 <span className="font-mono">{currentPath}/</span></> : null}。
              单次提交不超过 {(MAX_TOTAL_BYTES / (1024 * 1024)).toFixed(0)} MiB。
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="mr-2 size-4" /> 选择文件
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => folderInputRef.current?.click()}
              >
                <FolderUp className="mr-2 size-4" /> 选择文件夹
              </Button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(event) => setPickedFiles(event.target.files)}
            />
            <input
              ref={folderInputRef}
              type="file"
              multiple
              hidden
              // @ts-expect-error webkitdirectory is non-standard
              webkitdirectory=""
              directory=""
              onChange={(event) => setPickedFiles(event.target.files)}
            />
            {pickedFiles && pickedFiles.length > 0 ? (
              <div className="rounded-md border border-border/60 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                已选 {pickedFiles.length} 个文件 ·
                总计 {(Array.from(pickedFiles).reduce((sum, file) => sum + file.size, 0) / 1024).toFixed(1)} KB
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-border/60 px-3 py-4 text-center text-xs text-muted-foreground">
                还没有选择文件
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="commit-message">Commit message</Label>
              <Input
                id="commit-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={submitting}>
              取消
            </Button>
            <Button type="submit" disabled={submitting || !pickedFiles?.length}>
              {submitting ? "提交中…" : "提交"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
