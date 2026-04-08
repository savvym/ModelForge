"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createJudgePolicy } from "@/features/eval/api";
import type { EvaluationCatalogResponseV2 } from "@/types/api";

const DEFAULT_TEMPLATE_VERSION = "__none__";

export function JudgePolicyCreateForm({
  catalog
}: {
  catalog: EvaluationCatalogResponseV2;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const templateVersionOptions = React.useMemo(
    () =>
      catalog.templates.flatMap((template) =>
        template.versions.map((version) => ({
          id: version.id,
          label: `${template.display_name} · v${version.version}`
        }))
      ),
    [catalog.templates]
  );

  const [name, setName] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [strategy, setStrategy] = React.useState("judge-template");
  const [templateVersionId, setTemplateVersionId] = React.useState(DEFAULT_TEMPLATE_VERSION);
  const [modelSelectorText, setModelSelectorText] = React.useState("{}");
  const [executionParamsText, setExecutionParamsText] = React.useState('{"temperature": 0, "max_tokens": 2048}');
  const [parserConfigText, setParserConfigText] = React.useState("{}");
  const [retryPolicyText, setRetryPolicyText] = React.useState('{"maximum_attempts": 1}');

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim() || !displayName.trim()) {
      setError("请填写策略名称和显示名称。");
      return;
    }

    try {
      setSubmitting(true);
      await createJudgePolicy({
        name: normalizeName(name),
        display_name: displayName.trim(),
        description: description.trim() || undefined,
        strategy,
        template_spec_version_id:
          templateVersionId === DEFAULT_TEMPLATE_VERSION ? undefined : templateVersionId,
        model_selector_json: parseJsonObject(modelSelectorText, "Model Selector"),
        execution_params_json: parseJsonObject(executionParamsText, "执行参数"),
        parser_config_json: parseJsonObject(parserConfigText, "Parser 配置"),
        retry_policy_json: parseJsonObject(retryPolicyText, "重试策略")
      });
      router.push("/model/eval?tab=templates");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建 Judge Policy 失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="grid gap-6 md:grid-cols-2">
        <Field label="策略名称">
          <Input onChange={(event) => setName(event.target.value)} placeholder="judge_policy_default" value={name} />
        </Field>
        <Field label="显示名称">
          <Input onChange={(event) => setDisplayName(event.target.value)} placeholder="默认 Judge 策略" value={displayName} />
        </Field>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="执行策略">
          <Select onValueChange={setStrategy} value={strategy}>
            <SelectTrigger>
              <SelectValue placeholder="选择策略类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="judge-template">judge-template</SelectItem>
              <SelectItem value="rubric">rubric</SelectItem>
              <SelectItem value="pairwise">pairwise</SelectItem>
            </SelectContent>
          </Select>
        </Field>

        <Field label="绑定模板版本">
          <Select onValueChange={setTemplateVersionId} value={templateVersionId}>
            <SelectTrigger>
              <SelectValue placeholder="可选：绑定模板版本" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DEFAULT_TEMPLATE_VERSION}>不绑定模板版本</SelectItem>
              {templateVersionOptions.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <Field label="描述">
        <Textarea
          className="min-h-[96px]"
          onChange={(event) => setDescription(event.target.value)}
          placeholder="描述这条策略的适用模型、解析方式和执行语义。"
          value={description}
        />
      </Field>

      <div className="grid gap-6 md:grid-cols-2">
        <Field label="Model Selector (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setModelSelectorText(event.target.value)}
            value={modelSelectorText}
          />
        </Field>
        <Field label="执行参数 (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setExecutionParamsText(event.target.value)}
            value={executionParamsText}
          />
        </Field>
        <Field label="Parser 配置 (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setParserConfigText(event.target.value)}
            value={parserConfigText}
          />
        </Field>
        <Field label="重试策略 (JSON)">
          <Textarea
            className="min-h-[140px] font-mono text-xs"
            onChange={(event) => setRetryPolicyText(event.target.value)}
            value={retryPolicyText}
          />
        </Field>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button disabled={submitting} type="submit">
          {submitting ? "创建中..." : "创建 Judge Policy"}
        </Button>
      </div>
    </form>
  );
}

function normalizeName(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function parseJsonObject(value: string, label: string) {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} 必须是 JSON 对象。`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof Error && error.message.includes(label)) {
      throw error;
    }
    throw new Error(`${label} 不是合法 JSON。`);
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-sm text-slate-200">{label}</Label>
      {children}
    </div>
  );
}
