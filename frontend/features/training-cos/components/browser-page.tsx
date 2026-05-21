import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ConsoleListHeader } from "@/components/console/list-surface";
import { getTrainingCosStatus, listTrainingCosEntries } from "@/features/training-cos/api";
import { TrainingCosBreadcrumb } from "@/features/training-cos/components/breadcrumb";
import { TrainingCosBrowserTable } from "@/features/training-cos/components/browser-table";

export async function renderTrainingCosBrowser(prefix: string) {
  const status = await getTrainingCosStatus().catch(() => null);
  if (!status?.enabled || !status.configured) {
    return (
      <div className="flex flex-col gap-4">
        <ConsoleListHeader
          title="训练环境对象存储"
          description="服务器中转浏览训练 COS 的目录与文件。"
        />
        <Alert>
          <AlertTitle>未启用或配置不完整</AlertTitle>
          <AlertDescription>
            请先在「系统配置 → 训练环境 COS」中启用并填写 endpoint / bucket / SecretId /
            SecretKey。
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const data = await listTrainingCosEntries({ prefix, pageSize: 500 }).catch((error) => ({
    prefix,
    parent_prefix: prefix ? prefix.replace(/[^/]+\/?$/, "") : null,
    entries: [],
    next_token: null,
    truncated: false,
    error: error instanceof Error ? error.message : String(error)
  }));

  return (
    <div className="flex flex-col gap-4">
      <ConsoleListHeader
        title="训练环境对象存储"
        description={
          status.endpoint
            ? `当前 bucket：${status.bucket} · endpoint：${status.endpoint}`
            : "通过服务器中转浏览训练 COS。"
        }
        actions={
          status.target_prefix ? (
            <Badge variant="outline" className="font-mono text-xs">
              建议起点：{status.target_prefix.replace(/\/$/, "")}
            </Badge>
          ) : null
        }
      />
      <TrainingCosBreadcrumb prefix={data.prefix} bucket={status.bucket ?? null} />
      {"error" in data && data.error ? (
        <Alert variant="destructive">
          <AlertTitle>读取失败</AlertTitle>
          <AlertDescription>{data.error}</AlertDescription>
        </Alert>
      ) : null}
      <TrainingCosBrowserTable
        prefix={data.prefix}
        parentPrefix={data.parent_prefix ?? null}
        entries={data.entries}
        truncated={data.truncated}
      />
    </div>
  );
}
