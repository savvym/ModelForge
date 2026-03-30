import Link from "next/link";
import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConsoleListTableSurface } from "@/components/console/list-surface";
import { getBenchmark, getBenchmarkSampleFileUrl } from "@/features/eval/api";
import { BenchmarkVersionTable } from "@/features/eval/components/benchmark-version-table";
import { formatEvalMethod } from "@/features/eval/status";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { cn } from "@/lib/utils";

export default async function ModelEvalBenchmarkDetailPage({
  params
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const benchmark = await getBenchmark(name, projectId).catch(() => null);

  if (!benchmark) {
    notFound();
  }

  const sampleFileUrl = getBenchmarkSampleFileUrl(benchmark.name);
  const example = buildBenchmarkExample(benchmark.sample_example_json);

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800/70 pb-4">
        <div className="space-y-1.5">
          <ConsoleBreadcrumb
            items={[
              { label: "模型评测", href: "/model/eval" },
              { label: "评测管理", href: "/model/eval?tab=management" },
              { label: benchmark.display_name }
            ]}
          />
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold tracking-tight text-slate-50">
              {benchmark.display_name}
            </h1>
            <Badge variant="outline">{benchmark.version_count} Versions</Badge>
            <Badge variant={benchmark.runtime_available ? "default" : "secondary"}>
              {benchmark.runtime_available ? "已接入运行时" : "仅元信息"}
            </Badge>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate-400">{benchmark.description}</p>
        </div>

        <div className="flex gap-3">
          <Link href="/model/eval?tab=management">
            <Button variant="outline">返回评测管理</Button>
          </Link>
          {benchmark.runtime_available ? (
            <Link href={`/model/eval-benchmarks/${benchmark.name}/versions/create`}>
              <Button variant="outline">新增 Version</Button>
            </Link>
          ) : null}
          {benchmark.runtime_available ? (
            <Link href="/model/eval?tab=jobs&create=1">
              <Button>创建评测任务</Button>
            </Link>
          ) : null}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">Benchmark 信息</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <DetailItem label="Benchmark Name" value={benchmark.name} />
            <DetailItem label="Family" value={benchmark.family_display_name || benchmark.family_name || "--"} />
            <DetailItem label="默认评测方式" value={formatEvalMethod(benchmark.default_eval_method)} />
            <DetailItem label="数据集 ID" value={benchmark.dataset_id || "--"} />
            <DetailItem label="类别" value={benchmark.category || "--"} />
            <DetailItem
              label="Judge 模型"
              value={benchmark.requires_judge_model ? "Required" : "Optional"}
            />
            <DetailItem
              label="自定义数据源"
              value={benchmark.supports_custom_dataset ? "Supported" : "Not Supported"}
            />
            <DetailItem
              label="Version 统计"
              value={`${benchmark.enabled_version_count}/${benchmark.version_count} Enabled`}
            />
            <DetailItem
              label="子集"
              value={benchmark.subset_list.length ? benchmark.subset_list.join(", ") : "--"}
            />
            <DetailItem label="项目任务数" value={benchmark.eval_job_count.toLocaleString()} />
            <DetailItem label="最近运行" value={formatDateTime(benchmark.latest_eval_at)} />
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
          <CardHeader>
            <CardTitle className="text-base text-slate-50">管理边界</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-slate-400">
            <p>
              当前页面展示的是系统内置的 Benchmark Type。原始任务定义、说明文本和提示模板属于内置元信息，
              样本 schema、prompt contract 和执行逻辑则来自已经接入的 runtime。
            </p>
            <p>
              {benchmark.runtime_available
                ? "当前类型已经接入运行时，系统内可以继续管理这个 Benchmark 的 Version，也就是不同的数据集版本、样本数和启停状态。"
                : "当前类型还没有接入运行时，所以这里只能查看元信息；Version 管理和任务创建会在接入后开放。"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <div className="grid gap-6 xl:grid-cols-2">
          <ExampleCard
            benchmarkName={benchmark.name}
            example={example}
            sampleFileUrl={sampleFileUrl}
          />
          <SchemaCard
            content={{
              schema: benchmark.sample_schema_json,
              prompt_schema: benchmark.prompt_schema_json,
              prompt_defaults: benchmark.prompt_config_json
            }}
            description={
              benchmark.runtime_available
                ? "这里保留原始数据格式和 prompt contract 作为开发参考。上传 Version 时，系统会按对应 runtime 实际校验原始文件。"
                : "当前还没有接入运行时，因此这里只展示元信息里的格式参考。"
            }
            title="格式参考"
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <SchemaCard
            content={benchmark.statistics_json}
            description="内置元信息里的样本量、子集和长度统计。"
            title="Statistics"
          />
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <SchemaCard
            content={{
              few_shot_num: benchmark.few_shot_num,
              eval_split: benchmark.eval_split,
              train_split: benchmark.train_split,
              metric_names: benchmark.metric_names,
              tags: benchmark.tags,
              paper_url: benchmark.paper_url,
              meta_updated_at: benchmark.meta_updated_at,
            }}
            description="内置元信息里的基础配置和标签。"
            title="Benchmark Meta"
          />
          <SchemaCard
            content={{
              prompt_template: benchmark.prompt_template,
              system_prompt: benchmark.system_prompt,
              few_shot_prompt_template: benchmark.few_shot_prompt_template
            }}
            description="内置元信息里的提示模板文本，仅作为参考，不直接代表系统运行时使用的 prompt。"
            title="Prompt Template Reference"
          />
        </div>

        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-50">Version 列表</h2>
            <p className="mt-1 text-sm text-slate-400">
              {benchmark.runtime_available
                ? "查看每个 Version 的数据源、样本数和项目内运行情况。"
                : "当前类型尚未接入运行时，因此暂不支持 Version 管理。"}
            </p>
          </div>
        </div>

        <ConsoleListTableSurface>
          <BenchmarkVersionTable benchmark={benchmark} />
        </ConsoleListTableSurface>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 break-all text-sm text-slate-100">{value}</div>
    </div>
  );
}

function SchemaCard({
  title,
  description,
  content
}: {
  title: string;
  description: string;
  content: unknown;
}) {
  return (
    <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
      <CardHeader>
        <CardTitle className="text-base text-slate-50">{title}</CardTitle>
        <p className="text-sm leading-6 text-slate-400">{description}</p>
      </CardHeader>
      <CardContent>
        <pre className="overflow-x-auto rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] p-4 text-xs leading-6 text-slate-300">
          {JSON.stringify(content, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}

type BenchmarkExampleView = {
  subset?: string | null;
  sampleId?: string | null;
  inputText?: string | null;
  choices: string[];
  target?: string | null;
  rubrics: string[];
  metadata?: Record<string, unknown> | null;
};

function ExampleCard({
  benchmarkName,
  sampleFileUrl,
  example
}: {
  benchmarkName: string;
  sampleFileUrl: string;
  example: BenchmarkExampleView | null;
}) {
  return (
    <Card className="border-slate-800/80 bg-[rgba(10,15,22,0.72)] shadow-none">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-2">
          <CardTitle className="text-base text-slate-50">示例样本</CardTitle>
          <p className="text-sm leading-6 text-slate-400">
            展示一个可直接参考的 benchmark 示例，并提供样例文件下载，方便你准备
            Version 数据。
          </p>
        </div>
        <a
          className={cn(buttonVariants({ variant: "outline" }))}
          download
          href={sampleFileUrl}
        >
          下载样例文件
        </a>
      </CardHeader>
      <CardContent className="space-y-4">
        {example ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">{benchmarkName}</Badge>
              {example.subset ? <Badge variant="outline">subset: {example.subset}</Badge> : null}
              {example.sampleId ? <Badge variant="outline">id: {example.sampleId}</Badge> : null}
            </div>

            {example.inputText ? (
              <ExampleBlock label="输入示例" value={example.inputText} />
            ) : null}

            {example.choices.length ? (
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wide text-slate-500">选项</div>
                <div className="grid gap-2">
                  {example.choices.map((choice, index) => (
                    <div
                      key={`${index}-${choice}`}
                      className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-3 py-2 text-sm text-slate-200"
                    >
                      <span className="mr-2 text-slate-500">
                        {String.fromCharCode(65 + index)}.
                      </span>
                      {choice}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {example.target ? <ExampleBlock label="参考答案" value={example.target} /> : null}

            {example.rubrics.length ? (
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wide text-slate-500">评分 Rubrics</div>
                <div className="grid gap-2">
                  {example.rubrics.map((rubric, index) => (
                    <div
                      key={`${index}-${rubric}`}
                      className="rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] px-3 py-2 text-sm text-slate-200"
                    >
                      {rubric}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {example.metadata ? (
              <SchemaCard
                content={example.metadata}
                description="示例样本中携带的补充元数据。"
                title="Metadata"
              />
            ) : null}
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-800/80 bg-[rgba(15,23,32,0.52)] px-4 py-6 text-sm leading-6 text-slate-400">
            当前没有内置示例，下载按钮会退回到基于 schema 生成的最小样例文件。
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ExampleBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-slate-800/80 bg-[rgba(15,23,32,0.72)] p-4 text-xs leading-6 text-slate-300">
        {value}
      </pre>
    </div>
  );
}

function buildBenchmarkExample(
  value?: Record<string, unknown> | null
): BenchmarkExampleView | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const root = value as Record<string, unknown>;
  const sample = isRecord(root.data) ? root.data : root;
  const metadata = isRecord(sample.metadata) ? sample.metadata : null;

  return {
    subset:
      typeof root.subset === "string"
        ? root.subset
        : typeof sample.subset_key === "string"
          ? sample.subset_key
          : typeof metadata?.subject === "string"
            ? metadata.subject
            : null,
    sampleId:
      typeof sample.id === "string" || typeof sample.id === "number"
        ? String(sample.id)
        : null,
    inputText: extractExampleInput(sample),
    choices: Array.isArray(sample.choices)
      ? sample.choices.map((item) => String(item))
      : [],
    target: extractExampleTarget(sample),
    rubrics: Array.isArray(sample.rubrics)
      ? sample.rubrics.map((item) => String(item))
      : [],
    metadata
  };
}

function extractExampleInput(sample: Record<string, unknown>) {
  const input = sample.input;
  const messages = Array.isArray(input) ? input : Array.isArray(sample.messages) ? sample.messages : [];
  if (messages.length) {
    const parts = messages
      .map((item) => {
        if (!isRecord(item) || typeof item.content !== "string") {
          return null;
        }
        const role = typeof item.role === "string" ? item.role : "message";
        return `${role.toUpperCase()}\n${item.content}`;
      })
      .filter((item): item is string => Boolean(item));
    if (parts.length) {
      return parts.join("\n\n");
    }
  }
  const context = typeof sample.context === "string" ? sample.context : null;
  const question = typeof sample.question === "string" ? sample.question : null;
  if (context || question) {
    return [context ? `背景信息\n${context}` : null, question ? `问题\n${question}` : null]
      .filter((item): item is string => Boolean(item))
      .join("\n\n");
  }
  if (typeof input === "string") {
    return input;
  }
  return null;
}

function extractExampleTarget(sample: Record<string, unknown>) {
  if (typeof sample.target === "string" || typeof sample.target === "number") {
    return String(sample.target);
  }
  if (Array.isArray(sample.target)) {
    return sample.target.map((item) => String(item)).join("\n");
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}
