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
import { createEvalCollection } from "@/features/eval/api";
import type { BenchmarkDefinitionSummary, CollectionDatasetEntry } from "@/types/api";
import { Plus, X } from "lucide-react";

interface EntryRow {
  benchmark_name: string;
  version_id: string;
  weight: number;
}

export function EvalCollectionCreateForm({
  benchmarks
}: {
  benchmarks: BenchmarkDefinitionSummary[];
}) {
  const router = useRouter();
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [entries, setEntries] = React.useState<EntryRow[]>([
    { benchmark_name: "", version_id: "", weight: 1.0 }
  ]);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  function addEntry() {
    setEntries((prev) => [...prev, { benchmark_name: "", version_id: "", weight: 1.0 }]);
  }

  function removeEntry(index: number) {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  }

  function updateEntry(index: number, field: keyof EntryRow, value: string | number) {
    setEntries((prev) =>
      prev.map((entry, i) => {
        if (i !== index) return entry;
        const updated = { ...entry, [field]: value };
        // Reset version when benchmark changes
        if (field === "benchmark_name") {
          updated.version_id = "";
        }
        return updated;
      })
    );
  }

  function getVersionsForBenchmark(benchmarkName: string) {
    const benchmark = benchmarks.find((b) => b.name === benchmarkName);
    return benchmark?.versions.filter((v) => v.enabled) ?? [];
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const validEntries = entries.filter((e) => e.benchmark_name && e.version_id);
    if (!name.trim()) {
      setError("请输入套件名称。");
      return;
    }
    if (validEntries.length === 0) {
      setError("请至少添加一个 Benchmark。");
      return;
    }

    setSubmitting(true);
    try {
      const datasets: CollectionDatasetEntry[] = validEntries.map((e) => ({
        benchmark_name: e.benchmark_name,
        version_id: e.version_id,
        weight: e.weight
      }));
      await createEvalCollection({
        name: name.trim(),
        description: description.trim() || undefined,
        datasets
      });
      router.push("/model/eval-collections");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="name">套件名称</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="如：推理能力综合评测"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">描述（可选）</Label>
        <Input
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="套件用途说明"
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label>Benchmark 列表</Label>
          <Button type="button" variant="outline" size="sm" onClick={addEntry}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            添加
          </Button>
        </div>

        {entries.map((entry, index) => {
          const versions = getVersionsForBenchmark(entry.benchmark_name);
          return (
            <div
              key={index}
              className="flex items-start gap-2 rounded-md border border-border bg-card p-3"
            >
              <div className="flex-1 space-y-2">
                <Select
                  value={entry.benchmark_name}
                  onValueChange={(v) => updateEntry(index, "benchmark_name", v)}
                >
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue placeholder="选择 Benchmark" />
                  </SelectTrigger>
                  <SelectContent>
                    {benchmarks.map((b) => (
                      <SelectItem key={b.name} value={b.name}>
                        {b.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {entry.benchmark_name && (
                  <Select
                    value={entry.version_id}
                    onValueChange={(v) => updateEntry(index, "version_id", v)}
                  >
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue placeholder="选择版本" />
                    </SelectTrigger>
                    <SelectContent>
                      {versions.map((v) => (
                        <SelectItem key={v.id} value={v.id}>
                          {v.display_name} ({v.sample_count} 条)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div className="w-20">
                <Input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={entry.weight}
                  onChange={(e) => updateEntry(index, "weight", parseFloat(e.target.value) || 1)}
                  className="h-8 text-center text-sm"
                  title="权重"
                />
              </div>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 shrink-0"
                onClick={() => removeEntry(index)}
                disabled={entries.length <= 1}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          );
        })}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-3">
        <Button type="submit" disabled={submitting}>
          {submitting ? "创建中..." : "创建评测套件"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/model/eval-collections")}
        >
          取消
        </Button>
      </div>
    </form>
  );
}
