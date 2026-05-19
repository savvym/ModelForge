"use client";

import { Download, FileWarning } from "lucide-react";
import { Streamdown } from "streamdown";

import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { buildRawDownloadUrl } from "@/features/data-lake/api";
import type { LakeFileResponse } from "@/types/api";

function isImage(mime: string | null | undefined, name: string): boolean {
  if (mime?.startsWith("image/")) return true;
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  return ["png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"].includes(ext);
}

function isMarkdown(mime: string | null | undefined, name: string): boolean {
  if (mime === "text/markdown") return true;
  return /\.(md|mdx|markdown)$/i.test(name);
}

function isPdf(mime: string | null | undefined, name: string): boolean {
  return mime === "application/pdf" || /\.pdf$/i.test(name);
}

function isHtml(mime: string | null | undefined, name: string): boolean {
  return mime === "text/html" || /\.(html?|xhtml)$/i.test(name);
}

function isVideo(mime: string | null | undefined, name: string): boolean {
  if (mime?.startsWith("video/")) return true;
  return /\.(mp4|webm|mov|m4v)$/i.test(name);
}

function isAudio(mime: string | null | undefined, name: string): boolean {
  if (mime?.startsWith("audio/")) return true;
  return /\.(mp3|wav|ogg|m4a|flac)$/i.test(name);
}

export function RepoFileViewer({
  repoId,
  file
}: {
  repoId: string;
  file: LakeFileResponse;
}) {
  // Always build an absolute URL pointing at the backend; `file.download_url`
  // from the server is relative (`/api/v1/...`) and would resolve to the
  // Next.js host in the browser.
  const downloadUrl = buildRawDownloadUrl(repoId, file.ref, file.path);

  if (file.is_lfs) {
    return (
      <Card className="border-border/70 bg-card/60 p-6">
        <div className="flex flex-col items-start gap-3">
          <FileWarning className="size-6 text-muted-foreground" />
          <h2 className="text-base font-semibold">LFS 大文件</h2>
          <p className="text-sm text-muted-foreground">
            该文件托管在 Git LFS 后端，预览不可用，请下载查看。
          </p>
          <a href={downloadUrl} download={file.name} className={buttonVariants({ size: "sm" })}>
            <Download className="mr-2 size-4" /> 下载 {file.name}
          </a>
        </div>
      </Card>
    );
  }

  if (isImage(file.mime_type, file.name)) {
    return (
      <Card className="border-border/70 bg-card/60 p-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={downloadUrl}
          alt={file.name}
          className="mx-auto max-h-[640px] w-auto rounded"
        />
      </Card>
    );
  }

  if (isPdf(file.mime_type, file.name)) {
    return (
      <Card className="overflow-hidden border-border/70 bg-card/60">
        <iframe
          src={downloadUrl}
          title={file.name}
          className="h-[80vh] w-full"
        />
      </Card>
    );
  }

  if (isVideo(file.mime_type, file.name)) {
    return (
      <Card className="border-border/70 bg-card/60 p-4">
        <video src={downloadUrl} controls className="mx-auto max-h-[640px] w-full rounded" />
      </Card>
    );
  }

  if (isAudio(file.mime_type, file.name)) {
    return (
      <Card className="border-border/70 bg-card/60 p-6">
        <div className="mb-3 text-sm font-medium">{file.name}</div>
        <audio src={downloadUrl} controls className="w-full" />
      </Card>
    );
  }

  if (isHtml(file.mime_type, file.name)) {
    return (
      <Card className="overflow-hidden border-border/70 bg-card/60">
        <iframe
          src={downloadUrl}
          title={file.name}
          sandbox=""
          className="h-[80vh] w-full bg-white"
        />
      </Card>
    );
  }

  if (file.encoding === "utf8" && file.content != null) {
    if (isMarkdown(file.mime_type, file.name)) {
      return (
        <Card className="border-border/70 bg-card/60 px-6 py-5">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Streamdown>{file.content}</Streamdown>
          </div>
        </Card>
      );
    }
    return (
      <Card className="border-border/70 bg-card/60">
        <pre className="overflow-x-auto rounded-lg p-4 text-xs leading-relaxed">
          <code>{file.content}</code>
        </pre>
      </Card>
    );
  }

  return (
    <Card className="border-border/70 bg-card/60 p-6">
      <div className="flex flex-col items-start gap-3">
        <h2 className="text-base font-semibold">{file.name}</h2>
        <p className="text-sm text-muted-foreground">
          该文件较大或为二进制，未在浏览器中预览。
        </p>
        <a href={downloadUrl} download={file.name} className={buttonVariants({ size: "sm" })}>
          <Download className="mr-2 size-4" /> 下载文件
        </a>
      </div>
    </Card>
  );
}
