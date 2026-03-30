"use client";

import { FileUp, FolderOpen } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { createBenchmarkVersion, updateBenchmarkVersion } from "@/features/eval/api";
import { uploadManagedFile } from "@/features/object-store/api";
import { S3BrowserDialog } from "@/features/object-store/components/s3-browser-dialog";
import { cn } from "@/lib/utils";
import type { BenchmarkDefinitionSummary, BenchmarkVersionSummary } from "@/types/api";

type BenchmarkVersionEditorFormProps = {
  mode: "create" | "edit";
  benchmark: Pick<BenchmarkDefinitionSummary, "name" | "display_name">;
  initialVersion?: BenchmarkVersionSummary;
  projectId?: string | null;
};

export function BenchmarkVersionEditorForm({
  mode,
  benchmark,
  initialVersion,
  projectId
}: BenchmarkVersionEditorFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isUploading, setIsUploading] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error";
    text: string;
  } | null>(null);
  const [form, setForm] = useState({
    id: initialVersion?.id ?? "",
    display_name: initialVersion?.display_name ?? "",
    description: initialVersion?.description ?? "",
    dataset_source_uri: initialVersion?.dataset_source_uri ?? "",
    enabled: initialVersion?.enabled === false ? "false" : "true"
  });
  const isBusy = isPending || isUploading;

  function updateField(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function uploadFile(file: File) {
    const versionId = form.id.trim();
    if (!versionId) {
      setFeedback({
        tone: "error",
        text: "请先填写 Version ID，再上传数据文件到对象存储。"
      });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }
    if (!projectId) {
      setFeedback({
        tone: "error",
        text: "缺少项目上下文，无法确定对象存储上传目录。"
      });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setIsUploading(true);
    setFeedback(null);
    try {
      const upload = await uploadManagedFile({
        file,
        prefix: `projects/${projectId}/benchmarks/${benchmark.name}/versions/${versionId}/`
      });
      setForm((current) => ({
        ...current,
        dataset_source_uri: upload.uri
      }));
      setFeedback({
        tone: "success",
        text: `文件已上传到对象存储：${upload.uri}`
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "上传到对象存储失败"
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function submit() {
    if (!form.id.trim() || !form.display_name.trim()) {
      setFeedback({ tone: "error", text: "请填写 Version ID 和展示名称。" });
      return;
    }
    if (!form.dataset_source_uri.trim()) {
      setFeedback({ tone: "error", text: "请先上传数据文件，或从对象存储选择一个 s3:// URI。" });
      return;
    }
    if (!form.dataset_source_uri.trim().startsWith("s3://")) {
      setFeedback({ tone: "error", text: "Benchmark Version 仅支持使用对象存储中的 s3:// URI。" });
      return;
    }

    setFeedback(null);
    startTransition(() => {
      void (async () => {
        try {
          const payload = {
            display_name: form.display_name.trim(),
            description: form.description.trim() || null,
            dataset_source_uri: form.dataset_source_uri.trim() || null,
            enabled: form.enabled === "true"
          };

          if (mode === "edit" && initialVersion) {
            await updateBenchmarkVersion(benchmark.name, initialVersion.id, payload);
          } else {
            await createBenchmarkVersion(benchmark.name, {
              id: form.id.trim(),
              ...payload
            });
          }

          router.push(`/model/eval-benchmarks/${benchmark.name}`);
          router.refresh();
        } catch (error) {
          setFeedback({
            tone: "error",
            text: error instanceof Error ? error.message : "保存 Benchmark Version 失败"
          });
        }
      })();
    });
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <ConsoleBreadcrumb
          items={[
            { label: "模型评测", href: "/model/eval" },
            { label: "评测管理", href: "/model/eval?tab=management" },
            { label: benchmark.display_name, href: `/model/eval-benchmarks/${benchmark.name}` },
            {
              label: mode === "edit" && initialVersion ? initialVersion.display_name : "新增 Version",
              href:
                mode === "edit" && initialVersion
                  ? `/model/eval-benchmarks/${benchmark.name}/versions/${initialVersion.id}/edit`
                  : `/model/eval-benchmarks/${benchmark.name}/versions/create`
            }
          ]}
        />
        <input
          accept=".jsonl,application/x-ndjson,application/json,text/plain"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) {
              return;
            }
            void uploadFile(file);
          }}
          ref={fileInputRef}
          type="file"
        />
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
          {mode === "edit" ? "编辑 Benchmark Version" : "新增 Benchmark Version"}
        </h1>
      </div>

      {feedback ? (
        <div
          className={cn(
            "rounded-xl border px-3 py-2 text-sm",
            feedback.tone === "error"
              ? "border-rose-800/80 bg-rose-950/40 text-rose-200"
              : "border-emerald-800/80 bg-emerald-950/30 text-emerald-200"
          )}
        >
          {feedback.text}
        </div>
      ) : null}

      <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
        <CardHeader>
          <CardTitle className="text-base text-slate-50">Version 配置</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <Field
            disabled={mode === "edit"}
            label="Version ID"
            onChange={(value) => updateField("id", value)}
            placeholder="例如 cl_bench_smoke_1"
            value={form.id}
          />
          <Field
            label="展示名称"
            onChange={(value) => updateField("display_name", value)}
            placeholder="例如 CL-bench Smoke (1条)"
            value={form.display_name}
          />
          <Field
            label="数据源 URI"
            onChange={(value) => updateField("dataset_source_uri", value)}
            placeholder="例如 s3://nta-default/projects/<project-id>/files/benchmarks/.../dataset.jsonl"
            value={form.dataset_source_uri}
          />
          <SelectField
            label="启用状态"
            onChange={(value) => updateField("enabled", value)}
            options={[
              { label: "Enabled", value: "true" },
              { label: "Disabled", value: "false" }
            ]}
            value={form.enabled}
          />
          <div className="space-y-2 lg:col-span-2">
            <Label>对象存储文件</Label>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={isBusy}
                onClick={() => fileInputRef.current?.click()}
                type="button"
                variant="outline"
              >
                <FileUp className="mr-2 h-4 w-4" />
                {isUploading ? "上传中..." : "上传到对象存储"}
              </Button>
              <Button
                disabled={isBusy}
                onClick={() => setBrowserOpen(true)}
                type="button"
                variant="outline"
              >
                <FolderOpen className="mr-2 h-4 w-4" />
                从对象存储选择
              </Button>
            </div>
            <div className="text-xs leading-5 text-slate-500">
              Benchmark Version 统一使用对象存储中的 JSONL 文件。上传后的对象会放在
              `projects/&lt;project_id&gt;/benchmarks/{benchmark.name}/versions/&lt;version_id&gt;/`
              目录下，并自动回填 `s3://` URI。
            </div>
          </div>
          <div className="lg:col-span-2">
            <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3 text-sm leading-6 text-slate-400">
              系统会在创建或更新 Version 时，从对象存储读取 JSONL 数据、逐行校验是否符合
              Benchmark 的样本 schema，并自动计算样本数后落库。
            </div>
          </div>
          <div className="lg:col-span-2">
            <TextField
              label="说明"
              onChange={(value) => updateField("description", value)}
              placeholder="描述这个 Version 的样本来源、范围和使用意图。"
              value={form.description}
            />
          </div>
          <div className="flex gap-2 lg:col-span-2">
            <Button disabled={isBusy} onClick={submit} type="button">
              {mode === "edit" ? "保存修改" : "创建 Version"}
            </Button>
            <Button
              disabled={isBusy}
              onClick={() => router.back()}
              type="button"
              variant="outline"
            >
              取消
            </Button>
          </div>
        </CardContent>
      </Card>
      <S3BrowserDialog
        description="浏览当前项目对象存储，选择一个 JSONL 对象作为 Benchmark Version 的数据源。"
        initialUri={form.dataset_source_uri}
        onClose={() => setBrowserOpen(false)}
        onSelect={(uri) => {
          updateField("dataset_source_uri", uri);
          setFeedback(null);
          setBrowserOpen(false);
        }}
        open={browserOpen}
        title="选择 Benchmark Version 数据文件"
      />
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  disabled = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
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
        className="min-h-24"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
    </div>
  );
}
