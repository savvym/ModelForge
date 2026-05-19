import Link from "next/link";
import { notFound } from "next/navigation";

import { ConsoleListHeader } from "@/components/console/list-surface";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Download } from "lucide-react";

import {
  buildTrainingCosDownloadUrl,
  previewTrainingCosObject
} from "@/features/training-cos/api";
import { TrainingCosBreadcrumb } from "@/features/training-cos/components/breadcrumb";
import { TrainingCosFileViewer } from "@/features/training-cos/components/file-viewer";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export default async function TrainingCosBlobPage({
  params
}: {
  params: Promise<{ key: string[] }>;
}) {
  const { key } = await params;
  const decoded = key.map((segment) => decodeURIComponent(segment)).join("/");
  if (!decoded) {
    notFound();
  }

  let preview;
  try {
    preview = await previewTrainingCosObject(decoded);
  } catch (error) {
    return (
      <div className="flex flex-col gap-4">
        <ConsoleListHeader title={decoded} description="无法读取该对象。" />
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "读取失败"}
        </p>
        <Link
          href={
            "/training-cos/" +
            decoded
              .split("/")
              .slice(0, -1)
              .map((segment) => encodeURIComponent(segment))
              .join("/")
          }
          className="text-sm text-foreground underline-offset-4 hover:underline"
        >
          返回上一层
        </Link>
      </div>
    );
  }

  const parentPrefix = preview.key.includes("/")
    ? preview.key.slice(0, preview.key.lastIndexOf("/") + 1)
    : "";

  return (
    <div className="flex flex-col gap-4">
      <ConsoleListHeader
        title={preview.name}
        description={`${humanSize(preview.size)} · ${preview.mime_type || "未知 MIME"}${preview.last_modified ? ` · ${new Date(preview.last_modified).toLocaleString("zh-CN")}` : ""}`}
        actions={
          <a
            href={buildTrainingCosDownloadUrl(preview.key)}
            download={preview.name}
            className={buttonVariants({ size: "sm" })}
          >
            <Download className="mr-2 size-4" /> 下载
          </a>
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <TrainingCosBreadcrumb prefix={parentPrefix} bucket={null} />
        {preview.truncated ? (
          <Badge variant="outline" className="text-xs">已截断预览</Badge>
        ) : null}
      </div>
      <TrainingCosFileViewer file={preview} />
    </div>
  );
}
