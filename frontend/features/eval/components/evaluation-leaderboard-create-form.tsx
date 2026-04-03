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
  createEvaluationLeaderboard,
  getAvailableEvaluationLeaderboardRuns
} from "@/features/eval/api";
import type {
  EvaluationCatalogResponseV2,
  EvaluationLeaderboardRunCandidateV2
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

type EvaluationLeaderboardCreateFormProps = {
  catalog: EvaluationCatalogResponseV2;
};

export function EvaluationLeaderboardCreateForm({
  catalog
}: EvaluationLeaderboardCreateFormProps) {
  const router = useRouter();
  const defaultKind = catalog.suites.length > 0 ? "suite" : "spec";
  const [targetKind, setTargetKind] = React.useState<"spec" | "suite">(defaultKind);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [targetName, setTargetName] = React.useState("");
  const [targetVersion, setTargetVersion] = React.useState("");
  const [availableRuns, setAvailableRuns] = React.useState<EvaluationLeaderboardRunCandidateV2[]>([]);
  const [selectedRunIds, setSelectedRunIds] = React.useState<string[]>([]);
  const [runQuery, setRunQuery] = React.useState("");
  const [loadingRuns, setLoadingRuns] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const targetOptions = targetKind === "suite" ? catalog.suites : catalog.specs;
  const selectedTarget =
    targetOptions.find((item) => item.name === targetName) ?? targetOptions[0] ?? null;
  const versionOptions = selectedTarget?.versions ?? [];

  React.useEffect(() => {
    const nextTarget = targetOptions[0]?.name ?? "";
    if (!targetName || !targetOptions.some((item) => item.name === targetName)) {
      setTargetName(nextTarget);
    }
  }, [targetKind, targetName, targetOptions]);

  React.useEffect(() => {
    const nextVersion = versionOptions[0]?.version ?? "";
    if (!targetVersion || !versionOptions.some((item) => item.version === targetVersion)) {
      setTargetVersion(nextVersion);
    }
  }, [targetVersion, versionOptions]);

  React.useEffect(() => {
    if (!targetName || !targetVersion) {
      setAvailableRuns([]);
      setSelectedRunIds([]);
      return;
    }

    let cancelled = false;
    setLoadingRuns(true);
    setError(null);

    getAvailableEvaluationLeaderboardRuns({
      kind: targetKind,
      name: targetName,
      version: targetVersion
    })
      .then((runs) => {
        if (cancelled) {
          return;
        }
        setAvailableRuns(runs);
        setSelectedRunIds((current) => current.filter((runId) => runs.some((run) => run.run_id === runId)));
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setAvailableRuns([]);
        setSelectedRunIds([]);
        setError(err instanceof Error ? err.message : "读取可选评测任务失败");
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingRuns(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [targetKind, targetName, targetVersion]);

  const filteredRuns = React.useMemo(() => {
    const normalizedQuery = runQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableRuns;
    }
    return availableRuns.filter((run) =>
      [run.run_name, run.run_id, run.model_name].join(" ").toLowerCase().includes(normalizedQuery)
    );
  }, [availableRuns, runQuery]);

  const allVisibleSelected =
    filteredRuns.length > 0 && filteredRuns.every((run) => selectedRunIds.includes(run.run_id));

  function toggleRun(runId: string, checked: boolean) {
    setSelectedRunIds((current) => {
      if (checked) {
        return current.includes(runId) ? current : [...current, runId];
      }
      return current.filter((item) => item !== runId);
    });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("请输入排行榜名称。");
      return;
    }
    if (!targetName || !targetVersion) {
      setError("请选择排行榜目标和版本。");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createEvaluationLeaderboard({
        name: name.trim(),
        description: description.trim() || undefined,
        target: {
          kind: targetKind,
          name: targetName,
          version: targetVersion
        },
        run_ids: selectedRunIds
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
            placeholder="例如：综合能力基线排行榜"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="leaderboard-description">说明</Label>
          <Input
            id="leaderboard-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="可选，用来说明榜单适用范围和排序规则"
          />
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>目标类型</Label>
            <Select value={targetKind} onValueChange={(value) => setTargetKind(value as "spec" | "suite")}>
              <SelectTrigger>
                <SelectValue placeholder="选择目标类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="suite">评测套件</SelectItem>
                <SelectItem value="spec">评测类型</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>目标</Label>
            <Select value={targetName} onValueChange={setTargetName}>
              <SelectTrigger>
                <SelectValue placeholder="选择目标" />
              </SelectTrigger>
              <SelectContent>
                {targetOptions.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    {item.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>版本</Label>
            <Select value={targetVersion} onValueChange={setTargetVersion}>
              <SelectTrigger>
                <SelectValue placeholder="选择版本" />
              </SelectTrigger>
              <SelectContent>
                {versionOptions.map((version) => (
                  <SelectItem key={version.id} value={version.version}>
                    {version.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          排行榜会绑定到单个 spec 或 suite version。只有完成并产出 overall score 的 runs 才能加入排行榜。
        </p>
      </fieldset>

      <fieldset className="space-y-4 rounded-lg border border-border p-4">
        <legend className="px-2 text-sm font-medium">关联可选运行</legend>

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">可选运行</div>
            <div className="text-xs text-muted-foreground">
              当前共 {availableRuns.length} 条可纳入排行榜的运行，已选 {selectedRunIds.length} 条
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="w-[260px]"
              placeholder="搜索运行名称、ID 或模型"
              value={runQuery}
              onChange={(event) => setRunQuery(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                setSelectedRunIds((current) =>
                  allVisibleSelected
                    ? current.filter((runId) => !filteredRuns.some((run) => run.run_id === runId))
                    : Array.from(new Set([...current, ...filteredRuns.map((run) => run.run_id)]))
                )
              }
            >
              {allVisibleSelected ? "取消全选可见项" : "全选可见项"}
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[56px]">选择</TableHead>
                <TableHead>运行</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>排行榜得分</TableHead>
                <TableHead>指标</TableHead>
                <TableHead>完成时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loadingRuns ? (
                <TableRow>
                  <TableCell className="py-8 text-center text-sm text-muted-foreground" colSpan={6}>
                    正在读取可选运行...
                  </TableCell>
                </TableRow>
              ) : filteredRuns.length === 0 ? (
                <TableRow>
                  <TableCell className="py-8 text-center text-sm text-muted-foreground" colSpan={6}>
                    当前没有可加入排行榜的运行。
                  </TableCell>
                </TableRow>
              ) : (
                filteredRuns.map((run) => {
                  const checked = selectedRunIds.includes(run.run_id);
                  return (
                    <TableRow key={run.run_id}>
                      <TableCell>
                        <input
                          checked={checked}
                          className="h-4 w-4 rounded border-slate-700 bg-transparent text-sky-500"
                          onChange={(event) => toggleRun(run.run_id, event.target.checked)}
                          type="checkbox"
                        />
                      </TableCell>
                      <TableCell className="align-top">
                        <div className="font-medium text-slate-100">{run.run_name}</div>
                        <div className="mt-1 font-mono text-xs text-slate-500">{run.run_id}</div>
                      </TableCell>
                      <TableCell className="align-top text-slate-300">{run.model_name}</TableCell>
                      <TableCell className="align-top text-slate-300">{run.score.toFixed(4)}</TableCell>
                      <TableCell className="align-top text-slate-400">{run.metric_name}</TableCell>
                      <TableCell className="align-top text-slate-400">{formatDateTime(run.finished_at)}</TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>

        <p className="text-xs text-muted-foreground">
          你可以先创建一个空排行榜，后面再继续往里添加新的完成运行。
        </p>
      </fieldset>

      <div className="flex items-center justify-end gap-3">
        <Button type="button" variant="ghost" onClick={() => router.push("/model/eval?tab=leaderboards")}>
          取消
        </Button>
        <Button disabled={submitting} type="submit">
          {submitting ? "创建中..." : "创建排行榜"}
        </Button>
      </div>
    </form>
  );
}
