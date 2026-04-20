import { Boxes, CheckCircle2, HardDrive, ShieldCheck } from "lucide-react";
import { ConsolePage } from "@/components/console/console-page";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getProjects } from "@/features/project/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";

export default async function OverviewPage() {
  const [projects, currentProjectId] = await Promise.all([
    getProjects().catch(() => []),
    getCurrentProjectIdFromCookie()
  ]);
  const currentProject =
    projects.find((project) => project.id === currentProjectId) ??
    projects.find((project) => project.is_default) ??
    projects[0];
  const summaryItems = [
    { label: "项目数", value: projects.length.toString(), note: "当前可切换项目" },
    {
      label: "数据集",
      value: String(currentProject?.dataset_count ?? "--"),
      note: "当前项目数据资产"
    },
    {
      label: "评测任务",
      value: String(currentProject?.evaluation_run_count ?? "--"),
      note: "当前项目任务总量"
    }
  ];
  const healthItems = [
    {
      label: "API / Gateway",
      description: "接口服务链路正常",
      status: "健康",
      icon: CheckCircle2,
      healthy: true
    },
    {
      label: "对象存储",
      description: "Bucket 与文件挂载正常",
      status: "健康",
      icon: HardDrive,
      healthy: true
    },
    {
      label: "任务执行器",
      description: "Temporal workers 已就绪",
      status: "健康",
      icon: Boxes,
      healthy: true
    },
    {
      label: "项目隔离",
      description: currentProject ? "已绑定当前项目上下文" : "等待项目数据接入",
      status: currentProject ? "健康" : "待连接",
      icon: ShieldCheck,
      healthy: Boolean(currentProject)
    }
  ];

  return (
    <ConsolePage pageKey="overview" showScaffold={false}>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_340px]">
        <Card className="overflow-hidden border-border/70 bg-card/80 shadow-sm">
          <CardHeader className="border-b border-border/70 px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex flex-col gap-1.5">
                <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  当前项目
                </div>
                <CardTitle className="text-[22px]">
                  {currentProject ? currentProject.name : "当前还没有可用项目"}
                </CardTitle>
              </div>
              {currentProject ? <Badge variant="secondary">{currentProject.status}</Badge> : null}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 pt-4">
            <div className="grid gap-3 md:grid-cols-3">
              {summaryItems.map((item) => (
                <div
                  className="rounded-lg border border-border/60 bg-background/30 px-4 py-3"
                  key={item.label}
                >
                  <div className="text-[11px] tracking-[0.12em] text-muted-foreground">{item.label}</div>
                  <div className="mt-2 text-[28px] font-semibold text-foreground">{item.value}</div>
                  <div className="mt-1.5 text-[13px] leading-5 text-muted-foreground">{item.note}</div>
                </div>
              ))}
            </div>

            {currentProject ? (
              <div className="rounded-lg border border-border/60 bg-background/30 p-5">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="text-lg font-semibold text-foreground">{currentProject.name}</div>
                  <Badge className="uppercase tracking-[0.14em]" variant="outline">
                    {currentProject.code}
                  </Badge>
                </div>
                <p className="mt-2.5 max-w-3xl text-[13px] leading-6 text-muted-foreground">
                  {currentProject.description || "系统默认项目。未显式切换项目时，资源默认归属到该项目。"}
                </p>
                <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
                  <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">创建时间</div>
                    <div className="mt-2 font-medium text-foreground">
                      {new Date(currentProject.created_at).toLocaleString("zh-CN")}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">资源范围</div>
                    <div className="mt-2 font-medium text-foreground">数据集 / 模型 / 评测</div>
                  </div>
                  <div className="rounded-lg border border-border/60 bg-muted/20 px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">连接状态</div>
                    <div className="mt-2 font-medium text-foreground">服务已连接</div>
                  </div>
                </div>
              </div>
            ) : (
              <Alert className="border-dashed border-border/70 bg-background/40">
                <AlertTitle>暂无项目数据</AlertTitle>
                <AlertDescription className="text-[13px] leading-6">
                  请先连接后端服务，然后刷新当前页面。
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden border-border/70 bg-card/80 shadow-sm">
          <CardHeader className="border-b border-border/70 px-5 py-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <span className="size-2 rounded-full bg-emerald-400" />
              服务健康
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 pt-4">
            {healthItems.map((item) => (
              <div
                className={cn(
                  "flex items-start gap-3 rounded-lg border px-4 py-3",
                  item.healthy
                    ? "border-emerald-500/30 bg-emerald-500/10"
                    : "border-amber-500/30 bg-amber-500/10"
                )}
                key={item.label}
              >
                <div
                  className={cn(
                    "mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full",
                    item.healthy ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-200"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium text-foreground">{item.label}</div>
                  <div className="mt-1 text-[12px] leading-5 text-muted-foreground">{item.description}</div>
                </div>
                <Badge
                  className={cn(
                    "mt-0.5 gap-1",
                    item.healthy
                      ? "border-emerald-500/25 bg-emerald-500/12 text-emerald-200"
                      : "border-amber-500/25 bg-amber-500/12 text-amber-100"
                  )}
                  variant="outline"
                >
                  {item.healthy ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <span className="h-2 w-2 rounded-full bg-amber-100" />
                  )}
                  {item.status}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </ConsolePage>
  );
}
