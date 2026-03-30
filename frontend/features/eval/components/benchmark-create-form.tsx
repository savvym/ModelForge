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
import { createBenchmarkDefinition } from "@/features/eval/api";
import { cn } from "@/lib/utils";

const EVAL_METHODS = [
  {
    value: "accuracy",
    label: "Accuracy (准确率)",
    description: "适用于选择题、问答等有标准答案的评测"
  },
  {
    value: "judge-model",
    label: "Judge Model (模型评分)",
    description: "使用 LLM 作为评委对模型回答打分，适用于开放式生成评测"
  }
] as const;

const CATEGORIES = [
  { value: "llm", label: "语言模型" },
  { value: "math", label: "数学推理" },
  { value: "code", label: "代码生成" },
  { value: "reasoning", label: "逻辑推理" },
  { value: "knowledge", label: "知识问答" },
  { value: "instruction", label: "指令遵循" },
  { value: "domain", label: "领域专业" },
  { value: "other", label: "其他" }
] as const;

export function BenchmarkCreateForm() {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = React.useState(false);

  const [name, setName] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [category, setCategory] = React.useState("llm");
  const [evalMethod, setEvalMethod] = React.useState("accuracy");

  // Advanced: field mapping
  const [inputField, setInputField] = React.useState("input");
  const [targetField, setTargetField] = React.useState("target");
  const [choicesField, setChoicesField] = React.useState("choices");

  // Advanced: prompt
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [promptTemplate, setPromptTemplate] = React.useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("请输入 Benchmark ID。");
      return;
    }
    if (!displayName.trim()) {
      setError("请输入显示名称。");
      return;
    }

    const isDefaultMapping =
      inputField === "input" && targetField === "target" && choicesField === "choices";

    setSubmitting(true);
    try {
      await createBenchmarkDefinition({
        name: name.trim().toLowerCase().replace(/\s+/g, "_"),
        display_name: displayName.trim(),
        description: description.trim() || undefined,
        category,
        default_eval_method: evalMethod,
        requires_judge_model: evalMethod === "judge-model",
        field_mapping: isDefaultMapping
          ? undefined
          : {
              input_field: inputField,
              target_field: targetField,
              choices_field: choicesField || undefined
            },
        system_prompt: systemPrompt.trim() || undefined,
        prompt_template: promptTemplate.trim() || undefined
      });
      router.push("/model/eval?tab=management");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Info */}
      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">基础信息</legend>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="name">Benchmark ID</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="如 my_mcq_benchmark"
            />
            <p className="text-xs text-muted-foreground">唯一标识，小写字母和下划线</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="displayName">显示名称</Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="如 My MCQ Benchmark"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">描述</Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="评测内容和用途说明"
          />
        </div>

        <div className="space-y-2">
          <Label>分类</Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </fieldset>

      {/* Eval Method */}
      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">评测方法</legend>

        <div className="grid gap-3">
          {EVAL_METHODS.map((method) => (
            <button
              key={method.value}
              type="button"
              onClick={() => setEvalMethod(method.value)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors",
                evalMethod === method.value
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground/30"
              )}
            >
              <span className="text-sm font-medium">{method.label}</span>
              <span className="text-xs text-muted-foreground">{method.description}</span>
            </button>
          ))}
        </div>
      </fieldset>

      {/* Advanced Options */}
      <div>
        <button
          type="button"
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? "收起" : "展开"}高级选项（字段映射 & Prompt 模板）
        </button>
      </div>

      {showAdvanced && (
        <>
          <fieldset className="space-y-4 rounded-lg border border-border p-4">
            <legend className="px-2 text-sm font-medium">
              字段映射
              <span className="ml-2 font-normal text-muted-foreground">
                数据集 JSONL 字段名 → 标准格式
              </span>
            </legend>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="inputField">输入字段</Label>
                <Input
                  id="inputField"
                  value={inputField}
                  onChange={(e) => setInputField(e.target.value)}
                  placeholder="input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="targetField">答案字段</Label>
                <Input
                  id="targetField"
                  value={targetField}
                  onChange={(e) => setTargetField(e.target.value)}
                  placeholder="target"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="choicesField">选项字段</Label>
                <Input
                  id="choicesField"
                  value={choicesField}
                  onChange={(e) => setChoicesField(e.target.value)}
                  placeholder="choices (留空则无选项)"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              标准格式为 {`{input, target, choices, id}`}。如果你的数据集字段名不同（如 question/answer），在这里配置映射。
            </p>
          </fieldset>

          <fieldset className="space-y-4 rounded-lg border border-border p-4">
            <legend className="px-2 text-sm font-medium">Prompt 模板（可选）</legend>

            <div className="space-y-2">
              <Label htmlFor="systemPrompt">System Prompt</Label>
              <Input
                id="systemPrompt"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="如：你是一个评测助手..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="promptTemplate">Prompt Template</Label>
              <Input
                id="promptTemplate"
                value={promptTemplate}
                onChange={(e) => setPromptTemplate(e.target.value)}
                placeholder="如：请回答以下问题：{question}"
              />
            </div>
          </fieldset>
        </>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting ? "创建中..." : "创建 Benchmark"}
        </Button>
        <Button type="button" variant="outline" onClick={() => router.back()}>
          取消
        </Button>
      </div>
    </form>
  );
}
