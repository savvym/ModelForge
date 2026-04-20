import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { EvalSuiteSummaryV2 } from "@/types/api";

type SpecVersionLookup = Record<
  string,
  {
    specName: string;
    specDisplayName: string;
    version: string;
    versionDisplayName: string;
  }
>;

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-card/80 px-4 py-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-2 text-sm text-foreground">{value}</div>
    </div>
  );
}

export function EvalSuiteDetailPanel({
  suite,
  specVersionLookup
}: {
  suite: EvalSuiteSummaryV2;
  specVersionLookup: SpecVersionLookup;
}) {
  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-foreground">{suite.display_name}</h1>
            <Badge variant="outline">{suite.name}</Badge>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            {suite.description || "当前评测套件没有额外描述。"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/model/eval?tab=catalog">
            返回管理
          </Link>
          <Link
            className={buttonVariants({ size: "sm", variant: "outline" })}
            href={`/model/eval-suites/${encodeURIComponent(suite.name)}/edit`}
          >
            编辑评测套件
          </Link>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <SummaryCard label="能力分组" value={suite.capability_group || "--"} />
        <SummaryCard label="版本数量" value={String(suite.versions.length)} />
        <SummaryCard
          label="启用评测项"
          value={String(
            suite.versions.reduce(
              (total, version) => total + version.items.filter((item) => item.enabled).length,
              0
            )
          )}
        />
      </section>

      <div className="space-y-4">
        {suite.versions.map((version) => (
          <Card
            className="border-border bg-card/80 shadow-none"
            key={version.id}
          >
            <CardHeader className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base text-foreground">{version.display_name}</CardTitle>
                    <Badge variant="outline">{version.version}</Badge>
                    {version.enabled ? <Badge variant="outline">启用中</Badge> : <Badge variant="outline">已停用</Badge>}
                  </div>
                  <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                    {version.description || "当前版本没有额外描述。"}
                  </p>
                </div>
                <SummaryCard label="评测项" value={String(version.items.length)} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-hidden rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>评测项</TableHead>
                      <TableHead>分组</TableHead>
                      <TableHead>关联评测类型</TableHead>
                      <TableHead>权重</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {version.items.map((item) => {
                      const linkedSpec = specVersionLookup[item.spec_version_id];
                      return (
                        <TableRow key={item.id}>
                          <TableCell className="min-w-[220px] align-top">
                            <div className="font-medium text-foreground">{item.display_name}</div>
                            <div className="mt-1 text-xs text-muted-foreground">{item.item_key}</div>
                          </TableCell>
                          <TableCell className="text-sm text-foreground">{item.group_name || "--"}</TableCell>
                          <TableCell className="min-w-[240px]">
                            {linkedSpec ? (
                              <div className="space-y-1">
                                <Link
                                  className="text-sm text-foreground transition-colors hover:text-primary"
                                  href={`/model/eval-specs/${encodeURIComponent(linkedSpec.specName)}`}
                                >
                                  {linkedSpec.specDisplayName}
                                </Link>
                                <div className="text-xs text-muted-foreground">
                                  {linkedSpec.versionDisplayName} · {linkedSpec.version}
                                </div>
                              </div>
                            ) : (
                              <div className="text-sm text-muted-foreground">{item.spec_version_id}</div>
                            )}
                          </TableCell>
                          <TableCell className="text-sm text-foreground">{item.weight}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{item.enabled ? "启用中" : "已停用"}</Badge>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
