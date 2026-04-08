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
import { createTemplateSpec } from "@/features/eval/api";

const TEMPLATE_TYPES = [
  { value: "judge-template", label: "Judge Template" },
  { value: "rubric", label: "Rubric" },
  { value: "pairwise", label: "Pairwise" },
  { value: "structured-output", label: "Structured Output" }
] as const;

export function TemplateSpecCreateForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [templateType, setTemplateType] = React.useState<string>("judge-template");
  const [prompt, setPrompt] = React.useState("");
  const [varsText, setVarsText] = React.useState("input, output, target");
  const [outputSchemaText, setOutputSchemaText] = React.useState("{}");
  const [parserConfigText, setParserConfigText] = React.useState("{}");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim() || !displayName.trim() || !prompt.trim()) {
      setError("请填写名称、显示名称和 Prompt。");
      return;
    }

    try {
      setSubmitting(true);
      await createTemplateSpec({
        name: normalizeName(name),
        display_name: displayName.trim(),
        description: description.trim() || undefined,
        template_type: templateType,
        prompt: prompt.trim(),
        vars_json: varsText
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        output_schema_json: parseJsonObject(outputSchemaText, "输出 Schema"),
        parser_config_json: parseJsonObject(parserConfigText, "Parser 配置")
      });
      router.push("/model/eval?tab=templates");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建模板失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="grid gap-6 md:grid-cols-2">
        <Field label="模板名称">
          <Input onChange={(event) => setName(event.target.value)} placeholder="judge_template_default" value={name} />
        </Field>
        <Field label="显示名称">
          <Input onChange={(event) => setDisplayName(event.target.value)} placeholder="默认 Judge 模板" value={displayName} />
        </Field>
      </div>

      <Field label="模板类型">
        <Select onValueChange={setTemplateType} value={templateType}>
          <SelectTrigger>
            <SelectValue placeholder="选择模板类型" />
          </SelectTrigger>
          <SelectContent>
            {TEMPLATE_TYPES.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="描述">
        <Textarea
          className="min-h-[96px]"
          onChange={(event) => setDescription(event.target.value)}
          placeholder="描述这个模板的用途和适用场景。"
          value={description}
        />
      </Field>

      <Field label="Prompt">
        <Textarea
          className="min-h-[180px] font-mono text-xs"
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="你是一个评测器，请根据输入、输出和参考答案给出结构化评分。"
          value={prompt}
        />
      </Field>

      <div className="grid gap-6 md:grid-cols-3">
        <Field label="变量列表">
          <Input onChange={(event) => setVarsText(event.target.value)} value={varsText} />
        </Field>
        <Field label="输出 Schema (JSON)">
          <Textarea
            className="min-h-[120px] font-mono text-xs"
            onChange={(event) => setOutputSchemaText(event.target.value)}
            value={outputSchemaText}
          />
        </Field>
        <Field label="Parser 配置 (JSON)">
          <Textarea
            className="min-h-[120px] font-mono text-xs"
            onChange={(event) => setParserConfigText(event.target.value)}
            value={parserConfigText}
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
          {submitting ? "创建中..." : "创建模板"}
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
