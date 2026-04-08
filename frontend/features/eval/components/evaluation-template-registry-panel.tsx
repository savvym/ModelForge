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

export function EvaluationTemplateRegistryPanel({
  catalog
}: {
  catalog: EvaluationCatalogResponseV2;
}) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">模板资产</h2>
          <p className="text-sm text-slate-400">
            模板只保存 prompt、变量和输出结构，不再直接绑定模型 Provider。
          </p>
        </div>
        <div className="overflow-hidden rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>模板</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>版本数</TableHead>
                <TableHead>当前激活版本</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {catalog.templates.map((template) => {
                const activeVersion =
                  template.versions.find((version) => version.is_active) ?? template.versions[0] ?? null;
                return (
                  <TableRow key={template.id}>
                    <TableCell className="min-w-[260px] align-top">
                      <div className="font-medium text-slate-100">{template.display_name}</div>
                      <div className="mt-1 text-xs text-slate-500">{template.name}</div>
                      {template.description ? (
                        <div className="mt-2 max-w-[480px] text-sm leading-6 text-slate-400">
                          {template.description}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>{template.template_type}</TableCell>
                    <TableCell>{template.versions.length}</TableCell>
                    <TableCell>
                      {activeVersion ? (
                        <div className="space-y-1">
                          <div className="text-sm text-slate-200">v{activeVersion.version}</div>
                          <div className="text-xs text-slate-500">
                            vars · {activeVersion.vars_json.length}
                          </div>
                        </div>
                      ) : (
                        "--"
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-100">Judge Policy</h2>
          <p className="text-sm text-slate-400">
            Judge Policy 承接模型选择、执行参数、解析策略和重试策略，是模板之外的执行规则层。
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {catalog.judge_policies.length ? (
            catalog.judge_policies.map((policy) => (
              <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none" key={policy.id}>
                <CardHeader className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="text-base text-slate-50">{policy.display_name}</CardTitle>
                    <Badge variant="outline">{policy.strategy}</Badge>
                  </div>
                  <div className="text-xs text-slate-500">{policy.name}</div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <PolicyMetaRow
                    label="模板绑定"
                    value={policy.template_spec_version_id ? "已绑定模板版本" : "未绑定"}
                  />
                  <PolicyMetaRow
                    label="Model Selector"
                    value={Object.keys(policy.model_selector_json).length ? "已配置" : "未配置"}
                  />
                  <PolicyMetaRow
                    label="执行参数"
                    value={
                      Object.keys(policy.execution_params_json).length
                        ? JSON.stringify(policy.execution_params_json)
                        : "未配置"
                    }
                  />
                  <PolicyMetaRow
                    label="重试策略"
                    value={
                      Object.keys(policy.retry_policy_json).length
                        ? JSON.stringify(policy.retry_policy_json)
                        : "未配置"
                    }
                  />
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-800/80 px-4 py-10 text-sm text-slate-500">
              当前还没有 Judge Policy。
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function PolicyMetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-2 break-all text-sm leading-6 text-slate-200">{value}</div>
    </div>
  );
}
