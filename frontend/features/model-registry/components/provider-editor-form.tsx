"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { createModelProvider, updateModelProvider } from "@/features/model-registry/api";
import { modelApiFormatOptions } from "@/features/model-registry/api-format";
import { ModelRegistryBreadcrumb } from "@/features/model-registry/components/model-registry-breadcrumb";
import { cn } from "@/lib/utils";
import type { ModelProviderSummary } from "@/types/api";

type ProviderEditorFormProps = {
  mode: "create" | "edit";
  initialProvider?: Pick<
    ModelProviderSummary,
    "id" | "name" | "api_format" | "base_url" | "organization" | "description"
  >;
};

export function ProviderEditorForm({ mode, initialProvider }: ProviderEditorFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [form, setForm] = useState({
    name: initialProvider?.name ?? "",
    api_format: initialProvider?.api_format ?? "chat-completions",
    base_url: initialProvider?.base_url ?? "",
    api_key: "",
    organization: initialProvider?.organization ?? "",
    description: initialProvider?.description ?? ""
  });

  function updateField(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit() {
    if (!form.name.trim() || !form.base_url.trim()) {
      setFeedback({ tone: "error", text: "请填写 Provider 名称和 Base URL。" });
      return;
    }

    setFeedback(null);
    startTransition(() => {
      void (async () => {
        try {
          const payload = {
            name: form.name.trim(),
            api_format: form.api_format,
            base_url: form.base_url.trim(),
            organization: form.organization.trim() || null,
            description: form.description.trim() || null
          };

          const provider =
            mode === "edit" && initialProvider
              ? await updateModelProvider(initialProvider.id, {
                  ...payload,
                  ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {})
                })
              : await createModelProvider({
                  ...payload,
                  provider_type: "openai-compatible",
                  adapter: "litellm",
                  api_key: form.api_key.trim() || null
                });

          router.push(`/model-square?provider=${provider.id}`);
          router.refresh();
        } catch (error: unknown) {
          setFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "保存 Provider 失败"
          });
        }
      })();
    });
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <ModelRegistryBreadcrumb current={mode === "edit" ? "编辑 Provider" : "增加 Provider"} />
        <h1 className="text-2xl font-semibold tracking-[-0.03em] text-zinc-950">
          {mode === "edit" ? "编辑 Provider" : "增加 Provider"}
        </h1>
      </div>

      {feedback ? (
        <div
          className={cn(
            "rounded-md border px-3 py-2 text-sm",
            "border-zinc-200 bg-zinc-50 text-zinc-700"
          )}
        >
          {feedback.text}
        </div>
      ) : null}

      <Card className="rounded-md border-zinc-200 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base">
            {mode === "edit" ? "Provider 配置" : "新建 Provider"}
          </CardTitle>
          <CardDescription>使用 OpenAI Compatible 或 Google Generative AI 方式接入外部模型服务。</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <Field
            label="Provider 名称"
            onChange={(value) => updateField("name", value)}
            placeholder="例如 Venus Production"
            value={form.name}
          />
          <Field
            label="Base URL"
            onChange={(value) => updateField("base_url", value)}
            placeholder="例如 https://gateway.example.com/v1"
            value={form.base_url}
          />
          <SelectField
            label="API 格式"
            onChange={(value) => updateField("api_format", value)}
            options={modelApiFormatOptions}
            value={form.api_format}
          />
          <Field
            label="Organization"
            onChange={(value) => updateField("organization", value)}
            placeholder="可选"
            value={form.organization}
          />
          <Field
            label="API Key"
            onChange={(value) => updateField("api_key", value)}
            placeholder={mode === "edit" ? "留空则保持当前 API Key 不变" : "sk-..."}
            type="password"
            value={form.api_key}
          />
          <div className="lg:col-span-2">
            <TextField
              label="说明"
              onChange={(value) => updateField("description", value)}
              placeholder="简要描述该 Provider 的用途。"
              value={form.description}
            />
          </div>
          <div className="flex gap-2 lg:col-span-2">
            <Button disabled={isPending} onClick={submit} type="button">
              {mode === "edit" ? "保存修改" : "创建 Provider"}
            </Button>
            <Button
              disabled={isPending}
              onClick={() => router.back()}
              type="button"
              variant="outline"
            >
              取消
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text"
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        type={type}
        value={value}
      />
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Select onValueChange={onChange} value={value}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Textarea
        className="min-h-24 rounded-md"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
    </div>
  );
}
