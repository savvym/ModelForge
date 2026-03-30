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

export function ConsolePage({
  pageKey,
  highlight,
  showScaffold = true,
  children
}: {
  pageKey: keyof typeof consolePageMeta;
  highlight?: string;
  showScaffold?: boolean;
  children?: React.ReactNode;
}) {
  const meta = consolePageMeta[pageKey];
  const groupLabel = groupLabelMap[meta.group];

  return (
    <div className="space-y-4">
      <section className="space-y-1.5 pb-2">
        <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500">
          {groupLabel}
        </div>
        <div className="space-y-1">
          <h1 className="text-[24px] font-semibold tracking-tight text-slate-50">{meta.title}</h1>
          <p className="max-w-3xl text-[13px] leading-5 text-slate-400">{meta.description}</p>
        </div>
      </section>

      {showScaffold ? (
        <>
          {highlight ? (
            <div className="rounded-2xl border border-slate-800/70 bg-[rgba(13,18,25,0.6)] px-4 py-3 text-[13px] leading-6 text-slate-300">
              {highlight}
            </div>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_340px]">
            <Card className="overflow-hidden rounded-[20px] border-slate-800/70 bg-[rgba(13,18,25,0.54)] shadow-none">
              <CardHeader className="border-b border-slate-800/70 bg-transparent px-5 py-4">
                <CardTitle className="text-base text-slate-100">Console Surface</CardTitle>
                <CardDescription>
                  当前页面已经并入统一控制台布局，后续把真实业务数据和操作流接进来即可。
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 pt-4 md:grid-cols-3">
                {scaffoldCards.map((item) => (
                  <div
                    className="rounded-xl border border-slate-800/70 bg-[rgba(10,15,22,0.46)] p-4"
                    key={item.title}
                  >
                    <div className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                      Ready
                    </div>
                    <div className="mt-3 text-base font-semibold text-slate-100">{item.title}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">{item.description}</div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="overflow-hidden rounded-[20px] border-slate-800/70 bg-[rgba(13,18,25,0.54)] shadow-none">
              <CardHeader className="border-b border-slate-800/70 bg-transparent px-5 py-4">
                <CardTitle className="text-base text-slate-100">Next Step</CardTitle>
                <CardDescription>保持控制台壳层一致，再逐页接入真实工作流。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-4">
                <div className="rounded-xl border border-slate-800/70 bg-[rgba(10,15,22,0.46)] px-4 py-3">
                  <div className="text-xs uppercase tracking-[0.14em] text-slate-500">Focus</div>
                  <div className="mt-2 text-sm leading-6 text-slate-300">
                    优先把列表页、详情页和创建流统一成同一套 header、table、drawer 和 dialog 语言。
                  </div>
                </div>
                <div className="space-y-3 text-sm text-slate-400">
                  <div className="flex items-start justify-between gap-3">
                    <span>Layout shell</span>
                    <span className="text-slate-200">Ready</span>
                  </div>
                  <div className="flex items-start justify-between gap-3">
                    <span>Data surfaces</span>
                    <span className="text-slate-200">In progress</span>
                  </div>
                  <div className="flex items-start justify-between gap-3">
                    <span>Workflow actions</span>
                    <span className="text-slate-200">Pending</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {children ? <div className="space-y-4">{children}</div> : null}
        </>
      ) : (
        <div className="space-y-4">
          {highlight ? (
            <div className="rounded-2xl border border-slate-800/70 bg-[rgba(13,18,25,0.6)] px-4 py-3 text-[13px] leading-6 text-slate-300">
              {highlight}
            </div>
          ) : null}
          {children}
        </div>
      )}
    </div>
  );
}
