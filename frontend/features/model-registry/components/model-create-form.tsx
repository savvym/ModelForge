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
import { createRegistryModel, updateRegistryModel } from "@/features/model-registry/api";
import { modelApiFormatOptions } from "@/features/model-registry/api-format";
import { ModelRegistryBreadcrumb } from "@/features/model-registry/components/model-registry-breadcrumb";
import { cn } from "@/lib/utils";
import type { ModelProviderSummary, RegistryModelSummary } from "@/types/api";

type ModelCreateFormProps = {
  mode?: "create" | "edit";
  providers: ModelProviderSummary[];
  initialProviderId?: string | null;
  initialModel?: Pick<
    RegistryModelSummary,
    | "id"
    | "name"
    | "model_code"
    | "provider_id"
    | "vendor"
    | "api_format"
    | "category"
    | "description"
    | "is_provider_managed"
  >;
};

const unboundProviderValue = "__unbound_provider__";

const modelCategoryOptions = [
  { label: "深度思考", value: "深度思考" },
  { label: "文本生成", value: "文本生成" },
  { label: "视频生成", value: "视频生成" },
  { label: "图片生成", value: "图片生成" },
  { label: "语音模型", value: "语音模型" },
  { label: "向量模型", value: "向量模型" }
] as const;

function formatModelCategory(value?: string | null) {
  if (!value) {
    return "";
  }

  const normalized = value.toLowerCase();
  if (normalized === "chat-model" || normalized === "text-generation") {
    return "文本生成";
  }
  if (normalized === "reasoning-model") {
    return "深度思考";
  }
  if (normalized === "video-model") {
    return "视频生成";
  }
  if (normalized === "image-model") {
    return "图片生成";
  }
  if (
    normalized === "voice-model" ||
    normalized === "audio-model" ||
    normalized === "asr-model" ||
    normalized === "tts-model"
  ) {
    return "语音模型";
  }
  if (
    normalized === "vector-model" ||
    normalized === "embedding-model" ||
    normalized === "embeddings-model"
  ) {
    return "向量模型";
  }

  return value;
}

export function ModelCreateForm({
  mode = "create",
  providers,
  initialProviderId,
  initialModel
}: ModelCreateFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [form, setForm] = useState({
    name: initialModel?.name ?? "",
    model_code: initialModel?.model_code ?? "",
    provider_id: initialModel?.provider_id ?? initialProviderId ?? unboundProviderValue,
    vendor: initialModel?.vendor ?? "",
    api_format: initialModel?.api_format ?? "chat-completions",
    category: formatModelCategory(initialModel?.category) || "文本生成",
    description: initialModel?.description ?? ""
  });
  const categoryOptions = [
    ...modelCategoryOptions,
    ...(form.category &&
    !modelCategoryOptions.some((option) => option.value === form.category)
      ? [{ label: form.category, value: form.category }]
      : [])
  ];

  function updateField(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit() {
    if (!form.name.trim() || !form.model_code.trim()) {
      setFeedback({ tone: "error", text: "请填写模型名称和模型 ID。" });
      return;
    }

    setFeedback(null);
    startTransition(() => {
      void (async () => {
        try {
          if (mode === "edit" && initialModel) {
            await updateRegistryModel(initialModel.id, {
              name: form.name.trim(),
              model_code: form.model_code.trim(),
              provider_id: form.provider_id === unboundProviderValue ? null : form.provider_id,
              vendor: form.vendor.trim() || null,
              api_format: form.api_format,
              category: form.category.trim() || null,
              description: form.description.trim() || null
            });
          } else {
            await createRegistryModel({
              name: form.name.trim(),
              model_code: form.model_code.trim(),
              provider_id: form.provider_id === unboundProviderValue ? null : form.provider_id,
              vendor: form.vendor.trim() || null,
              source: "manual",
              api_format: form.api_format,
              category: form.category.trim() || null,
              description: form.description.trim() || null
            });
          }

          const target = form.provider_id ? `/model-square?provider=${form.provider_id}` : "/model-square";
          router.push(target);
          router.refresh();
        } catch (error: unknown) {
          setFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "创建 Model 失败"
          });
        }
      })();
    });
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <ModelRegistryBreadcrumb current={mode === "edit" ? "编辑 Model" : "增加 Model"} />
        <h1 className="text-2xl font-semibold tracking-[-0.03em] text-zinc-950">
          {mode === "edit" ? "编辑 Model" : "增加 Model"}
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
          <CardTitle className="text-base">{mode === "edit" ? "模型配置" : "模型信息"}</CardTitle>
          <CardDescription>
            {mode === "edit"
              ? "调整模型名称、Provider 归属和展示属性。"
              : "用于补充手工模型映射或自定义部署名。"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <Field
            label="模型名称"
            onChange={(value) => updateField("name", value)}
            placeholder="例如 GPT-5 Production"
            value={form.name}
          />
          <Field
            label="模型 ID"
            onChange={(value) => updateField("model_code", value)}
            placeholder="例如 gpt-5 或你的部署名"
            value={form.model_code}
          />
          <SelectField
            label="Provider"
            onChange={(value) => updateField("provider_id", value)}
            options={[
              { label: "不绑定 Provider", value: unboundProviderValue },
              ...providers.map((provider) => ({ label: provider.name, value: provider.id }))
            ]}
            value={form.provider_id}
          />
          <Field
            label="Vendor"
            onChange={(value) => updateField("vendor", value)}
            placeholder="可选"
            value={form.vendor}
          />
          <SelectField
            label="API 格式"
            onChange={(value) => updateField("api_format", value)}
            options={modelApiFormatOptions}
            value={form.api_format}
          />
          <SelectField
            label="分类"
            onChange={(value) => updateField("category", value)}
            options={categoryOptions.map((option) => ({
              label: option.label,
              value: option.value
            }))}
            value={form.category}
          />
          <div className="lg:col-span-2">
            <TextField
              label="说明"
              onChange={(value) => updateField("description", value)}
              placeholder="描述模型用途、部署环境或调用限制。"
              value={form.description}
            />
          </div>
          {mode === "edit" && initialModel?.is_provider_managed ? (
            <div className="lg:col-span-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
              当前模型由 Provider 同步生成。下次执行“同步模型”后，模型名称、模型 ID、Vendor、
              API 格式等字段可能会被上游配置覆盖。
            </div>
          ) : null}
          <div className="flex gap-2 lg:col-span-2">
            <Button disabled={isPending} onClick={submit} type="button">
              {mode === "edit" ? "保存修改" : "创建 Model"}
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
      <Input onChange={(event) => onChange(event.target.value)} placeholder={placeholder} value={value} />
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
