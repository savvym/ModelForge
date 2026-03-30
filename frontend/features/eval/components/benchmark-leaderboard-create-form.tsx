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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  createBenchmarkLeaderboard,
  getAvailableBenchmarkLeaderboardJobs
} from "@/features/eval/api";
import { formatLeaderboardMetricName } from "@/features/eval/status";
import type {
  BenchmarkDefinitionSummary,
  BenchmarkLeaderboardJobCandidate
} from "@/types/api";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

type BenchmarkLeaderboardCreateFormProps = {
  benchmarks: BenchmarkDefinitionSummary[];
  initialBenchmarkName?: string | null;
  initialVersionId?: string | null;
};

export function BenchmarkLeaderboardCreateForm({
  benchmarks,
  initialBenchmarkName,
  initialVersionId
}: BenchmarkLeaderboardCreateFormProps) {
  const router = useRouter();
  const defaultBenchmark =
    benchmarks.find((item) => item.name === initialBenchmarkName && item.versions.length > 0) ??
    benchmarks.find((item) => item.versions.length > 0) ??
    benchmarks[0] ??
    null;

  const [name, setName] = React.useState("");
  const [benchmarkName, setBenchmarkName] = React.useState(defaultBenchmark?.name ?? "");
  const [versionId, setVersionId] = React.useState(initialVersionId ?? defaultBenchmark?.versions[0]?.id ?? "");
  const [availableJobs, setAvailableJobs] = React.useState<BenchmarkLeaderboardJobCandidate[]>([]);
  const [selectedJobIds, setSelectedJobIds] = React.useState<string[]>([]);
  const [jobQuery, setJobQuery] = React.useState("");
  const [loadingJobs, setLoadingJobs] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const selectedBenchmark =
    benchmarks.find((item) => item.name === benchmarkName) ?? defaultBenchmark ?? null;
  const versions = selectedBenchmark?.versions ?? [];

  React.useEffect(() => {
    if (!versions.length) {
      if (versionId) {
        setVersionId("");
      }
      return;
    }

    if (!versions.some((item) => item.id === versionId)) {
      const nextVersion =
        (initialVersionId && versions.find((item) => item.id === initialVersionId)?.id) ??
        versions[0].id;
      setVersionId(nextVersion);
    }
  }, [initialVersionId, versionId, versions]);

  React.useEffect(() => {
    if (!benchmarkName || !versionId) {
      setAvailableJobs([]);
      setSelectedJobIds([]);
      return;
    }

    let cancelled = false;
    setLoadingJobs(true);
    setError(null);

    getAvailableBenchmarkLeaderboardJobs({
      benchmarkName,
      benchmarkVersionId: versionId
    })
      .then((jobs) => {
        if (cancelled) {
          return;
        }
        setAvailableJobs(jobs);
        setSelectedJobIds((current) => current.filter((id) => jobs.some((job) => job.eval_job_id === id)));
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setAvailableJobs([]);
        setSelectedJobIds([]);
        setError(err instanceof Error ? err.message : "读取可选评测任务失败");
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingJobs(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [benchmarkName, versionId]);

  const filteredJobs = React.useMemo(() => {
    const normalizedQuery = jobQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableJobs;
    }
    return availableJobs.filter((job) =>
      [job.eval_job_name, job.eval_job_id, job.model_name].join(" ").toLowerCase().includes(normalizedQuery)
    );
  }, [availableJobs, jobQuery]);

  const allVisibleSelected =
    filteredJobs.length > 0 && filteredJobs.every((job) => selectedJobIds.includes(job.eval_job_id));

  function toggleJob(jobId: string, checked: boolean) {
    setSelectedJobIds((current) => {
      if (checked) {
        return current.includes(jobId) ? current : [...current, jobId];
      }
      return current.filter((item) => item !== jobId);
    });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("请输入排行榜名称。");
      return;
    }
    if (!benchmarkName || !versionId) {
      setError("请选择 Benchmark 和 Version。");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createBenchmarkLeaderboard({
        name: name.trim(),
        benchmark_name: benchmarkName,
        benchmark_version_id: versionId,
        eval_job_ids: selectedJobIds
      });
      router.push(`/model/eval-leaderboards/${created.id}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建排行榜失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">基础信息</legend>

        <div className="space-y-2">
          <Label htmlFor="leaderboard-name">排行榜名称</Label>
          <Input
            id="leaderboard-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="例如：网络问答模型排行榜"
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Benchmark</Label>
            <Select value={benchmarkName} onValueChange={setBenchmarkName}>
              <SelectTrigger>
                <SelectValue placeholder="选择 Benchmark" />
              </SelectTrigger>
              <SelectContent>
                {benchmarks.map((benchmark) => (
                  <SelectItem key={benchmark.name} value={benchmark.name}>
                    {benchmark.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Version</Label>
            <Select value={versionId} onValueChange={setVersionId}>
              <SelectTrigger>
                <SelectValue placeholder="选择 Version" />
              </SelectTrigger>
              <SelectContent>
                {versions.length === 0 ? (
                  <SelectItem value="no-version" disabled>
                    当前 Benchmark 暂无可用 Version
                  </SelectItem>
                ) : (
                  versions.map((version) => (
                    <SelectItem key={version.id} value={version.id}>
                      {version.display_name}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          排行榜会绑定到单个 Benchmark Version。只有使用这个 Version、且已经完成并产出得分的评测任务，才可以加入排行榜。
        </p>
      </fieldset>

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">关联可选任务</legend>

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">可选任务</div>
            <div className="text-xs text-muted-foreground">
              当前共 {availableJobs.length} 条可纳入排行榜的评测任务，已选 {selectedJobIds.length} 条
            </div>
          </div>

          <div className="w-full max-w-sm">
            <Input
              value={jobQuery}
              onChange={(event) => setJobQuery(event.target.value)}
              placeholder="搜索任务名称、ID 或模型"
            />
          </div>
        </div>

        <div className="rounded-xl border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[72px] text-center">
                  <input
                    aria-label="全选当前列表"
                    checked={allVisibleSelected}
                    className="h-4 w-4 accent-slate-100"
                    disabled={filteredJobs.length === 0}
                    onChange={(event) => {
                      if (event.target.checked) {
                        setSelectedJobIds((current) => [
                          ...new Set([...current, ...filteredJobs.map((job) => job.eval_job_id)])
                        ]);
                      } else {
                        const visibleIds = new Set(filteredJobs.map((job) => job.eval_job_id));
                        setSelectedJobIds((current) => current.filter((id) => !visibleIds.has(id)));
                      }
                    }}
                    type="checkbox"
                  />
                </TableHead>
                <TableHead>任务名称</TableHead>
                <TableHead>评测模型</TableHead>
                <TableHead>排行榜得分</TableHead>
                <TableHead>评分指标</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loadingJobs ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={6}>
                    可选评测任务加载中...
                  </TableCell>
                </TableRow>
              ) : filteredJobs.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={6}>
                    当前没有可加入排行榜的评测任务。
                  </TableCell>
                </TableRow>
              ) : (
                filteredJobs.map((job) => {
                  const checked = selectedJobIds.includes(job.eval_job_id);
                  return (
                    <TableRow key={job.eval_job_id}>
                      <TableCell className="text-center">
                        <input
                          aria-label={`选择 ${job.eval_job_name}`}
                          checked={checked}
                          className="h-4 w-4 accent-slate-100"
                          onChange={(event) => toggleJob(job.eval_job_id, event.target.checked)}
                          type="checkbox"
                        />
                      </TableCell>
                      <TableCell className="align-top">
                        <div className="font-medium text-slate-100">{job.eval_job_name}</div>
                        <div className="mt-1 text-xs text-slate-500">{job.eval_job_id}</div>
                      </TableCell>
                      <TableCell className="align-top text-slate-300">{job.model_name}</TableCell>
                      <TableCell className="align-top text-slate-100">
                        {job.score.toFixed(4)}
                      </TableCell>
                      <TableCell className="align-top text-slate-400">
                        {formatLeaderboardMetricName(job.metric_name)}
                      </TableCell>
                      <TableCell className="align-top text-slate-400">
                        {formatDateTime(job.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>

        <p className="text-xs text-muted-foreground">
          你可以先创建一个空排行榜，后面再继续往里添加任务。
        </p>
      </fieldset>

      <div className="flex justify-end gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/model/eval?tab=leaderboards")}
        >
          取消
        </Button>
        <Button disabled={submitting} type="submit">
          {submitting ? "创建中..." : "创建排行榜"}
        </Button>
      </div>
    </form>
  );
}
