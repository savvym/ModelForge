"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
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
import { createProbeTask } from "@/features/eval/api";
import type { ProbeSummary } from "@/types/api";

type ProbeTaskCreateFormProps = {
  onCreated?: () => void;
  probes: ProbeSummary[];
};

export function ProbeTaskCreateForm({
  onCreated,
  probes
}: ProbeTaskCreateFormProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [probeId, setProbeId] = React.useState(probes[0]?.id ?? "");
  const [name, setName] = React.useState("");
  const [model, setModel] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [apiKeyEnv, setApiKeyEnv] = React.useState("OPENAI_API_KEY");
  const [prompt, setPrompt] = React.useState("请简短回复 ok。");
  const [number, setNumber] = React.useState("4");
  const [parallel, setParallel] = React.useState("1");
  const [timeoutSeconds, setTimeoutSeconds] = React.useState("1800");
  const [totalTimeout, setTotalTimeout] = React.useState("600");
  const [maxTokens, setMaxTokens] = React.useState("256");

  React.useEffect(() => {
    if (!probes.length) {
      setProbeId("");
      return;
    }
    if (probes.some((probe) => probe.id === probeId)) {
      return;
    }
    setProbeId(probes[0]?.id ?? "");
  }, [probeId, probes]);

  const disabled = submitting || probes.length === 0;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!probeId || !model.trim() || !url.trim()) {
      toast.error("请先填写 Probe、模型名称和目标 URL。");
      return;
    }

    const parsedNumber = parsePositiveInteger(number, "请求轮数");
    const parsedParallel = parsePositiveInteger(parallel, "并发数");
    const parsedTimeoutSeconds = parsePositiveInteger(timeoutSeconds, "任务超时时间");
    const parsedTotalTimeout = parsePositiveInteger(totalTimeout, "单请求总超时");
    const parsedMaxTokens = parsePositiveInteger(maxTokens, "最大输出 Token");

    if (
      parsedNumber == null ||
      parsedParallel == null ||
      parsedTimeoutSeconds == null ||
      parsedTotalTimeout == null ||
      parsedMaxTokens == null
    ) {
      return;
    }

    setSubmitting(true);
    try {
      await createProbeTask({
        probe_id: probeId,
        name: name.trim() || undefined,
        runtime_kind: "evalscope-perf",
        timeout_seconds: parsedTimeoutSeconds,
        config: {
          model: model.trim(),
          url: url.trim(),
          api_key_env: apiKeyEnv.trim() || undefined,
          prompt: prompt.trim() || undefined,
          number: parsedNumber,
          parallel: parsedParallel,
          total_timeout: parsedTotalTimeout,
          max_tokens: parsedMaxTokens,
          enable_progress_tracker: true
        }
      });
      toast.success("Probe 任务已创建");
      onCreated?.();
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建 Probe 任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="flex w-full max-w-4xl flex-col gap-6" onSubmit={handleSubmit}>
      {probes.length === 0 ? (
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/40 px-4 py-3 text-sm text-slate-400">
          当前项目还没有已注册的 Probe。先启动一个 probe agent，它注册成功后就能在这里创建任务。
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <FieldBlock
          description="选择一个目标 Probe。离线 Probe 也可以先排队，等它重新上线后再领取任务。"
          label="Probe 节点"
        >
          <Select disabled={disabled} onValueChange={setProbeId} value={probeId}>
            <SelectTrigger>
              <SelectValue placeholder="选择 Probe" />
            </SelectTrigger>
            <SelectContent>
              {probes.map((probe) => (
                <SelectItem key={probe.id} value={probe.id}>
                  {probe.display_name} · {probe.status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldBlock>

        <FieldBlock description="给这次压测起一个容易识别的名字。" label="任务名称">
          <Input
            disabled={disabled}
            onChange={(event) => setName(event.target.value)}
            placeholder="例如：香港探针 · GPT-5.4 峰值吞吐"
            value={name}
          />
        </FieldBlock>

        <FieldBlock description="传给 evalscope perf 的目标模型名称。" label="模型名称">
          <Input
            disabled={disabled}
            onChange={(event) => setModel(event.target.value)}
            placeholder="例如：GPT-5.4"
            value={model}
          />
        </FieldBlock>

        <FieldBlock description="探针实际压测的 OpenAI 兼容接口地址。" label="目标 URL">
          <Input
            disabled={disabled}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com/v1/chat/completions"
            value={url}
          />
        </FieldBlock>

        <FieldBlock description="Probe 进程读取 API Key 的环境变量名。" label="API Key 环境变量">
          <Input
            disabled={disabled}
            onChange={(event) => setApiKeyEnv(event.target.value)}
            placeholder="OPENAI_API_KEY"
            value={apiKeyEnv}
          />
        </FieldBlock>

        <FieldBlock description="每个请求默认允许的总超时时间，单位秒。" label="单请求总超时">
          <Input
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => setTotalTimeout(event.target.value)}
            type="number"
            value={totalTimeout}
          />
        </FieldBlock>
      </div>

      <FieldBlock
        description="默认用一个很短的 prompt 做 perf 压测；如果你有固定压测语句，可以直接写在这里。"
        label="压测 Prompt"
      >
        <Textarea
          className="min-h-[120px]"
          disabled={disabled}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="请输入压测 Prompt"
          value={prompt}
        />
      </FieldBlock>

      <div className="grid gap-6 md:grid-cols-4">
        <FieldBlock description="发起多少轮请求。" label="请求轮数">
          <Input
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => setNumber(event.target.value)}
            type="number"
            value={number}
          />
        </FieldBlock>

        <FieldBlock description="evalscope perf 的并发数。" label="并发数">
          <Input
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => setParallel(event.target.value)}
            type="number"
            value={parallel}
          />
        </FieldBlock>

        <FieldBlock description="整个 Probe 任务的最大运行时长。" label="任务超时（秒）">
          <Input
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => setTimeoutSeconds(event.target.value)}
            type="number"
            value={timeoutSeconds}
          />
        </FieldBlock>

        <FieldBlock description="请求输出上限。" label="最大输出 Token">
          <Input
            disabled={disabled}
            inputMode="numeric"
            onChange={(event) => setMaxTokens(event.target.value)}
            type="number"
            value={maxTokens}
          />
        </FieldBlock>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-slate-800/80 pt-4">
        <Button disabled={disabled} type="submit">
          {submitting ? "创建中..." : "创建 Probe 任务"}
        </Button>
      </div>
    </form>
  );
}

function FieldBlock({
  label,
  description,
  children
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2.5">
      <div className="space-y-1">
        <Label className="text-[13px] font-medium text-slate-200">{label}</Label>
        <p className="text-xs leading-5 text-slate-500">{description}</p>
      </div>
      {children}
    </div>
  );
}

function parsePositiveInteger(value: string, label: string) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    toast.error(`${label}必须是大于 0 的整数。`);
    return null;
  }
  return parsed;
}
