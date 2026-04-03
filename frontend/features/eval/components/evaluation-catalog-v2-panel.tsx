import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import type { EvaluationCatalogResponseV2 } from "@/types/api";

export function EvaluationCatalogV2Panel({ catalog }: { catalog: EvaluationCatalogResponseV2 }) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">评测套件</h2>
          <p className="text-sm text-slate-400">
            套件是一等公民，负责承接百炼式基线评测和多基准组合评测。
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {catalog.suites.map((suite) => {
            const activeVersion = suite.versions.find((version) => version.enabled) ?? suite.versions[0] ?? null;
            return (
              <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none" key={suite.id}>
                <CardHeader className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base text-slate-50">{suite.display_name}</CardTitle>
                    <Badge variant="outline">{suite.name}</Badge>
                  </div>
                  <p className="text-sm leading-6 text-slate-400">
                    {suite.description || "当前套件没有额外描述。"}
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <MetaCard label="激活版本" value={activeVersion?.display_name ?? "--"} />
                    <MetaCard
                      label="评测项数量"
                      value={String(activeVersion?.items.filter((item) => item.enabled).length ?? 0)}
                    />
                  </div>
                  {activeVersion?.items.length ? (
                    <div className="flex flex-wrap gap-2">
                      {activeVersion.items
                        .filter((item) => item.enabled)
                        .map((item) => (
                          <span
                            className="rounded-full border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-3 py-1 text-xs text-slate-300"
                            key={item.id}
                          >
                            {item.group_name ? `${item.group_name} · ` : ""}
                            {item.display_name}
                          </span>
                        ))}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
                      当前套件还没有启用的评测项。
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">评测类型与版本</h2>
          <p className="text-sm text-slate-400">
            每个评测类型可以挂多个不可变版本，运行时只消费冻结后的版本快照。
          </p>
        </div>
        <div className="overflow-hidden rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>评测类型</TableHead>
                <TableHead>能力分类</TableHead>
                <TableHead>推荐版本</TableHead>
                <TableHead>执行引擎</TableHead>
                <TableHead>样本量</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {catalog.specs.map((spec) => {
                const recommendedVersion =
                  spec.versions.find((version) => version.is_recommended && version.enabled) ??
                  spec.versions.find((version) => version.enabled) ??
                  null;
                return (
                  <TableRow key={spec.id}>
                    <TableCell className="min-w-[240px] align-top">
                      <div className="font-medium text-slate-100">{spec.display_name}</div>
                      <div className="mt-1 text-xs text-slate-500">{spec.name}</div>
                      {spec.description ? (
                        <div className="mt-2 max-w-[440px] text-sm leading-6 text-slate-400">
                          {spec.description}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      {[spec.capability_group, spec.capability_category].filter(Boolean).join(" / ") || "--"}
                    </TableCell>
                    <TableCell>
                      {recommendedVersion ? (
                        <div className="space-y-1">
                          <div className="text-sm text-slate-200">{recommendedVersion.display_name}</div>
                          <div className="text-xs text-slate-500">{recommendedVersion.version}</div>
                        </div>
                      ) : (
                        "--"
                      )}
                    </TableCell>
                    <TableCell>
                      {recommendedVersion
                        ? `${recommendedVersion.engine} / ${recommendedVersion.execution_mode}`
                        : "--"}
                    </TableCell>
                    <TableCell>{recommendedVersion?.sample_count ?? "--"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-200">{value}</div>
    </div>
  );
}
