import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { consolePageMeta } from "@/lib/console-navigation";

const groupLabelMap = {
  overview: "Overview",
  workspace: "Workspace",
  system: "System"
} as const;

const scaffoldCards = [
  {
    title: "Workspace Surface",
    description: "承接列表、详情、状态和操作流，统一在控制台壳层下运行。"
  },
  {
    title: "Service Contract",
    description: "页面已经对齐前后端接口边界，后续直接接 REST / SSE / workflow 状态。"
  },
  {
    title: "Operational Rhythm",
    description: "把创建、同步、发布、回滚和审计动作压进同一条操作链。"
  }
] as const;

const workflowStatusItems = [
  { label: "Layout shell", status: "Ready", variant: "secondary" as const },
  { label: "Data surfaces", status: "In progress", variant: "outline" as const },
  { label: "Workflow actions", status: "Pending", variant: "outline" as const }
] as const;

export function ConsolePage({
  pageKey,
  highlight,
  showHeader = true,
  showScaffold = true,
  children
}: {
  pageKey: keyof typeof consolePageMeta;
  highlight?: string;
  showHeader?: boolean;
  showScaffold?: boolean;
  children?: React.ReactNode;
}) {
  const meta = consolePageMeta[pageKey];
  const groupLabel = groupLabelMap[meta.group];

  return (
    <div className="flex flex-col gap-4">
      {showHeader ? (
        <section className="flex flex-col gap-1.5 pb-2">
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {groupLabel}
          </div>
          <div className="flex flex-col gap-1">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">{meta.title}</h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{meta.description}</p>
          </div>
        </section>
      ) : null}

      {showScaffold ? (
        <>
          {highlight ? (
            <Alert className="border-border/70 bg-card/70">
              <AlertDescription className="text-sm leading-6">{highlight}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_340px]">
            <Card className="overflow-hidden border-border/70 bg-card/80 shadow-sm">
              <CardHeader className="border-b border-border/70 px-5 py-4">
                <CardTitle className="text-base">Console Surface</CardTitle>
                <CardDescription>
                  当前页面已经并入统一控制台布局，后续把真实业务数据和操作流接进来即可。
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 pt-4 md:grid-cols-3">
                {scaffoldCards.map((item) => (
                  <div
                    className="flex flex-col gap-3 rounded-lg border border-border/60 bg-background/30 p-4"
                    key={item.title}
                  >
                    <Badge className="w-fit" variant="outline">
                      Ready
                    </Badge>
                    <div className="text-base font-semibold text-foreground">{item.title}</div>
                    <div className="text-sm leading-6 text-muted-foreground">{item.description}</div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="overflow-hidden border-border/70 bg-card/80 shadow-sm">
              <CardHeader className="border-b border-border/70 px-5 py-4">
                <CardTitle className="text-base">Next Step</CardTitle>
                <CardDescription>保持控制台壳层一致，再逐页接入真实工作流。</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4 pt-4">
                <div className="rounded-lg border border-border/60 bg-background/30 px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Focus</div>
                  <div className="mt-2 text-sm leading-6 text-foreground/90">
                    优先把列表页、详情页和创建流统一成同一套 header、table、drawer 和 dialog 语言。
                  </div>
                </div>
                <div className="flex flex-col gap-3 text-sm text-muted-foreground">
                  {workflowStatusItems.map((item) => (
                    <div className="flex items-start justify-between gap-3" key={item.label}>
                      <span>{item.label}</span>
                      <Badge
                        className={item.status === "In progress" ? "border-primary/30 bg-primary/10 text-primary" : ""}
                        variant={item.variant}
                      >
                        {item.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {children ? <div className="flex flex-col gap-4">{children}</div> : null}
        </>
      ) : (
        <div className="flex flex-col gap-4">
          {highlight ? (
            <Alert className="border-border/70 bg-card/70">
              <AlertDescription className="text-sm leading-6">{highlight}</AlertDescription>
            </Alert>
          ) : null}
          {children}
        </div>
      )}
    </div>
  );
}
