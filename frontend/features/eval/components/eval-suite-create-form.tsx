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
import { createEvalSuite, updateEvalSuite } from "@/features/eval/api";
import type {
  EvaluationCatalogResponseV2,
  EvalSuiteItemSummaryV2,
  EvalSuiteSummaryV2,
  EvalSuiteVersionSummaryV2
} from "@/types/api";

type SuiteItemState = {
  id: string;
  itemKey: string;
  displayName: string;
  specName: string;
  specVersionId: string;
  groupName: string;
  weight: string;
};

type EvalSuiteFormProps = {
  catalog: EvaluationCatalogResponseV2;
  initialValue?: EvalSuiteSummaryV2;
  mode?: "create" | "edit";
};

export function EvalSuiteCreateForm({
  catalog,
  initialValue,
  mode = "create"
}: EvalSuiteFormProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const specOptions = React.useMemo(
    () =>
      catalog.specs
        .map((spec) => ({
          name: spec.name,
          displayName: spec.display_name,
          defaultGroupName: spec.capability_category ?? "",
          versions: spec.versions.filter((version) => version.enabled)
        }))
        .filter((spec) => spec.versions.length > 0),
    [catalog.specs]
  );

  const managedVersion = React.useMemo(
    () => getManagedSuiteVersion(initialValue),
    [initialValue]
  );

  const [name, setName] = React.useState(initialValue?.name ?? "");
  const [displayName, setDisplayName] = React.useState(initialValue?.display_name ?? "");
  const [description, setDescription] = React.useState(initialValue?.description ?? "");
  const [capabilityGroup, setCapabilityGroup] = React.useState(initialValue?.capability_group ?? "基线评测");
  const [version, setVersion] = React.useState(managedVersion?.version ?? "v1");
  const [versionDisplayName, setVersionDisplayName] = React.useState(
    managedVersion?.display_name ?? "默认套件版本"
  );
  const [items, setItems] = React.useState<SuiteItemState[]>(() =>
    getInitialSuiteItems({ catalog, initialValue, specOptions })
  );

  React.useEffect(() => {
    if (!items.length && specOptions.length) {
      setItems([createItemFromSpec(specOptions[0])]);
    }
  }, [items.length, specOptions]);

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
      const versionPayload = {
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
      };
      if (mode === "edit") {
        if (!initialValue || !managedVersion) {
          throw new Error("缺少可编辑的评测套件版本。");
        }
        await updateEvalSuite(initialValue.name, {
          display_name: displayName.trim(),
          description: normalizeOptional(description),
          capability_group: normalizeOptional(capabilityGroup),
          version: {
            version_id: managedVersion.id,
            ...versionPayload
          }
        });
      } else {
        await createEvalSuite({
          name: normalizeName(name),
          display_name: displayName.trim(),
          description: normalizeOptional(description),
          capability_group: normalizeOptional(capabilityGroup),
          initial_version: versionPayload
        });
      }
      router.push("/model/eval?tab=catalog");
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : `${mode === "edit" ? "更新" : "创建"}评测套件失败`);
    } finally {
      setSubmitting(false);
    }
  }

  function handleAddItem() {
    const fallback = specOptions[0];
    if (!fallback) {
      return;
    }
    setItems((current) => [...current, createItemFromSpec(fallback)]);
  }

  function handleItemSpecChange(itemId: string, specName: string) {
    const spec = specOptions.find((entry) => entry.name === specName);
    const defaultVersionId = spec?.versions.find((entry) => entry.is_recommended)?.id ?? spec?.versions[0]?.id ?? "";
    setItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              itemKey: spec?.name ?? item.itemKey,
              specName,
              specVersionId: defaultVersionId,
              displayName: item.displayName.trim() ? item.displayName : spec?.displayName ?? item.displayName,
              groupName: spec?.defaultGroupName ?? item.groupName
            }
          : item
      )
    );
  }

  function handleItemVersionChange(itemId: string, specVersionId: string) {
    setItems((current) =>
      current.map((item) => (item.id === itemId ? { ...item, specVersionId } : item))
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
          <Input
            disabled={mode === "edit"}
            onChange={(event) => setName(event.target.value)}
            placeholder="baseline_general"
            value={name}
          />
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
              先选择评测类型，再选择对应版本，并按分组组织套件结构。
            </div>
          </div>
          <Button disabled={!specOptions.length} onClick={handleAddItem} type="button" variant="outline">
            <Plus className="mr-2 h-4 w-4" />
            添加评测项
          </Button>
        </div>

        {!specOptions.length ? (
          <div className="rounded-xl border border-dashed border-slate-800/80 px-4 py-6 text-sm text-slate-500">
            当前没有可选的评测类型版本，请先创建 Eval Spec。
          </div>
        ) : null}

        <div className="space-y-4">
          {items.map((item, index) => {
            const selectedSpec = specOptions.find((option) => option.name === item.specName) ?? specOptions[0] ?? null;
            const selectedVersions = selectedSpec?.versions ?? [];
            return (
              <div
                className="grid gap-4 rounded-xl border border-slate-800/80 bg-[rgba(14,20,29,0.84)] p-4 md:grid-cols-[1fr_1fr_1fr_1fr_120px_auto]"
                key={item.id}
              >
                <Field label={`评测类型 #${index + 1}`}>
                  <Select onValueChange={(value) => handleItemSpecChange(item.id, value)} value={item.specName}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择评测类型" />
                    </SelectTrigger>
                    <SelectContent>
                      {specOptions.map((option) => (
                        <SelectItem key={option.name} value={option.name}>
                          {option.displayName}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="版本">
                  <Select onValueChange={(value) => handleItemVersionChange(item.id, value)} value={item.specVersionId}>
                    <SelectTrigger>
                      <SelectValue placeholder="选择版本" />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedVersions.map((option) => (
                        <SelectItem key={option.id} value={option.id}>
                          {option.display_name} · {option.version}
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
            );
          })}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button disabled={submitting || !specOptions.length} type="submit">
          {submitting ? `${mode === "edit" ? "保存" : "创建"}中...` : mode === "edit" ? "保存评测套件" : "创建评测套件"}
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

function getManagedSuiteVersion(suite?: EvalSuiteSummaryV2): EvalSuiteVersionSummaryV2 | undefined {
  return suite?.versions.find((version) => version.enabled) ?? suite?.versions[0];
}

function createItemFromSpec(spec: {
  name: string;
  displayName: string;
  defaultGroupName: string;
  versions: Array<{ id: string; is_recommended: boolean }>;
}) {
  return {
    id: crypto.randomUUID(),
    itemKey: spec.name,
    displayName: spec.displayName,
    specName: spec.name,
    specVersionId: spec.versions.find((entry) => entry.is_recommended)?.id ?? spec.versions[0]?.id ?? "",
    groupName: spec.defaultGroupName,
    weight: "1"
  } satisfies SuiteItemState;
}

function getInitialSuiteItems({
  catalog,
  initialValue,
  specOptions
}: {
  catalog: EvaluationCatalogResponseV2;
  initialValue?: EvalSuiteSummaryV2;
  specOptions: Array<{
    name: string;
    displayName: string;
    defaultGroupName: string;
    versions: Array<{ id: string; is_recommended: boolean }>;
  }>;
}) {
  const managedVersion = getManagedSuiteVersion(initialValue);
  if (managedVersion?.items.length) {
    return managedVersion.items.map((item) => hydrateItemFromSummary(item, catalog));
  }
  if (specOptions.length) {
    return [createItemFromSpec(specOptions[0])];
  }
  return [];
}

function hydrateItemFromSummary(
  item: EvalSuiteItemSummaryV2,
  catalog: EvaluationCatalogResponseV2
): SuiteItemState {
  const spec = catalog.specs.find((entry) =>
    entry.versions.some((version) => version.id === item.spec_version_id)
  );
  return {
    id: crypto.randomUUID(),
    itemKey: item.item_key,
    displayName: item.display_name,
    specName: spec?.name ?? "",
    specVersionId: item.spec_version_id,
    groupName: item.group_name ?? "",
    weight: String(item.weight)
  };
}
