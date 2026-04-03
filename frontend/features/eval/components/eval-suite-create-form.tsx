"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
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
import { createEvalSuite } from "@/features/eval/api";
import type { EvaluationCatalogResponseV2 } from "@/types/api";

type SuiteItemState = {
  id: string;
  itemKey: string;
  displayName: string;
  specVersionId: string;
  groupName: string;
  weight: string;
};

export function EvalSuiteCreateForm({ catalog }: { catalog: EvaluationCatalogResponseV2 }) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const specVersionOptions = React.useMemo(
    () =>
      catalog.specs.flatMap((spec) =>
        spec.versions
          .filter((version) => version.enabled)
          .map((version) => ({
            id: version.id,
            itemKey: spec.name,
            displayName: spec.display_name,
            label: `${spec.display_name} · ${version.display_name}`,
            versionName: version.version,
            groupName: spec.capability_category ?? ""
          }))
      ),
    [catalog.specs]
  );

  const [name, setName] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [capabilityGroup, setCapabilityGroup] = React.useState("基线评测");
  const [version, setVersion] = React.useState("v1");
  const [versionDisplayName, setVersionDisplayName] = React.useState("默认套件版本");
  const [items, setItems] = React.useState<SuiteItemState[]>(() =>
    specVersionOptions.length ? [createItemFromOption(specVersionOptions[0])] : []
  );

  React.useEffect(() => {
    if (!items.length && specVersionOptions.length) {
      setItems([createItemFromOption(specVersionOptions[0])]);
    }
  }, [items.length, specVersionOptions]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (!name.trim() || !displayName.trim() || !version.trim() || !versionDisplayName.trim()) {
      setError("请填写套件名称、显示名称、版本号和版本显示名称。");
      return;
    }
    if (!items.length) {
      setError("请至少添加一个评测项。");
      return;
    }

    try {
      setSubmitting(true);
      await createEvalSuite({
        name: normalizeName(name),
        display_name: displayName.trim(),
        description: normalizeOptional(description),
        capability_group: normalizeOptional(capabilityGroup),
        initial_version: {
          version: version.trim(),
          display_name: versionDisplayName.trim(),
          description: normalizeOptional(description),
          enabled: true,
          items: items.map((item, index) => ({
            item_key: normalizeName(item.itemKey || item.displayName),
            display_name: item.displayName.trim(),
            spec_version_id: item.specVersionId,
            position: index,
            weight: parseWeight(item.weight),
            group_name: normalizeOptional(item.groupName),
            overrides_json: {},
            enabled: true
          }))
        }
      });
      router.push("/model/eval?tab=catalog");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建评测套件失败");
    } finally {
      setSubmitting(false);
    }
  }

  function handleAddItem() {
    const fallback = specVersionOptions[0];
    if (!fallback) {
      return;
    }
    setItems((current) => [...current, createItemFromOption(fallback)]);
  }

  function handleItemSpecChange(itemId: string, specVersionId: string) {
    const option = specVersionOptions.find((entry) => entry.id === specVersionId);
    setItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              specVersionId,
              itemKey: option?.itemKey ?? item.itemKey,
              displayName: item.displayName || option?.displayName || item.displayName,
              groupName: option?.groupName ?? item.groupName
            }
          : item
      )
    );
  }

  function updateItem(itemId: string, patch: Partial<SuiteItemState>) {
    setItems((current) => current.map((item) => (item.id === itemId ? { ...item, ...patch } : item)));
  }

  function removeItem(itemId: string) {
    setItems((current) => current.filter((item) => item.id !== itemId));
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="grid gap-6 md:grid-cols-2">
        <Field label="评测套件名称">
          <Input onChange={(event) => setName(event.target.value)} placeholder="baseline_general" value={name} />
        </Field>
        <Field label="显示名称">
          <Input onChange={(event) => setDisplayName(event.target.value)} placeholder="通用基线评测" value={displayName} />
        </Field>
      </div>

      <Field label="描述">
        <Textarea
          className="min-h-[96px]"
          onChange={(event) => setDescription(event.target.value)}
          placeholder="描述这个套件覆盖的能力范围和适用场景。"
          value={description}
        />
      </Field>

      <div className="grid gap-6 md:grid-cols-3">
        <Field label="能力分组">
          <Input onChange={(event) => setCapabilityGroup(event.target.value)} value={capabilityGroup} />
        </Field>
        <Field label="版本号">
          <Input onChange={(event) => setVersion(event.target.value)} value={version} />
        </Field>
        <Field label="版本显示名称">
          <Input onChange={(event) => setVersionDisplayName(event.target.value)} value={versionDisplayName} />
        </Field>
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-800/80 bg-[rgba(10,15,22,0.72)] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium text-slate-100">评测项</div>
            <div className="mt-1 text-sm text-slate-400">
              选择要纳入套件的评测类型版本，并按分组组织。
            </div>
          </div>
          <Button disabled={!specVersionOptions.length} onClick={handleAddItem} type="button" variant="outline">
            <Plus className="mr-2 h-4 w-4" />
            添加评测项
          </Button>
        </div>

        {!specVersionOptions.length ? (
          <div className="rounded-xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
            当前没有可选的评测类型版本，请先创建 Eval Spec。
          </div>
        ) : null}

        <div className="space-y-4">
          {items.map((item, index) => (
            <div
              className="grid gap-4 rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] p-4 md:grid-cols-[1.2fr_1fr_1fr_120px_auto]"
              key={item.id}
            >
              <Field label={`评测类型版本 #${index + 1}`}>
                <Select onValueChange={(value) => handleItemSpecChange(item.id, value)} value={item.specVersionId}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择版本" />
                  </SelectTrigger>
                  <SelectContent>
                    {specVersionOptions.map((option) => (
                      <SelectItem key={option.id} value={option.id}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="显示名称">
                <Input
                  onChange={(event) => updateItem(item.id, { displayName: event.target.value })}
                  value={item.displayName}
                />
              </Field>
              <Field label="分组">
                <Input
                  onChange={(event) => updateItem(item.id, { groupName: event.target.value })}
                  placeholder="如：学科 / 数学 / 推理"
                  value={item.groupName}
                />
              </Field>
              <Field label="权重">
                <Input
                  onChange={(event) => updateItem(item.id, { weight: event.target.value })}
                  value={item.weight}
                />
              </Field>
              <div className="flex items-end">
                <Button
                  disabled={items.length === 1}
                  onClick={() => removeItem(item.id)}
                  type="button"
                  variant="ghost"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button disabled={submitting || !specVersionOptions.length} type="submit">
          {submitting ? "创建中..." : "创建评测套件"}
        </Button>
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-sm text-slate-200">{label}</Label>
      {children}
    </div>
  );
}

function normalizeName(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function normalizeOptional(value: string) {
  const normalized = value.trim();
  return normalized || undefined;
}

function parseWeight(value: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error("评测项权重必须是大于 0 的数字。");
  }
  return parsed;
}

function createItemFromOption(option: {
  id: string;
  itemKey: string;
  displayName: string;
  groupName: string;
}) {
  return {
    id: crypto.randomUUID(),
    itemKey: option.itemKey,
    displayName: option.displayName,
    specVersionId: option.id,
    groupName: option.groupName,
    weight: "1"
  } satisfies SuiteItemState;
}
