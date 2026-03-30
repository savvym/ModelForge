"use client";

import { ChevronDown, Check, ListFilter } from "lucide-react";
import { useRouter } from "next/navigation";
import { consoleListFilterTriggerClassName } from "@/components/console/list-surface";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const formatOptions = [
  {
    label: "模型精调",
    items: [
      { label: "SFT 精调", value: "sft" },
      { label: "直接偏好学习", value: "dpo" },
      { label: "继续预训练", value: "continued-pretrain" }
    ]
  },
  {
    label: "模型评测",
    items: [{ label: "标准评测集", value: "generic-eval" }]
  }
] as const;

const formatLabelMap: Record<string, string> = {
  sft: "SFT 精调",
  dpo: "直接偏好学习",
  "continued-pretrain": "继续预训练",
  "generic-eval": "标准评测集"
};

export function DatasetFormatFilter({
  currentValues,
  q,
  scope,
  variant = "toolbar"
}: {
  currentValues: string[];
  q: string;
  scope: string;
  variant?: "toolbar" | "icon";
}) {
  const router = useRouter();
  const selectedLabels = currentValues
    .map((value) => formatLabelMap[value])
    .filter((label): label is string => Boolean(label));
  const hasSelections = currentValues.length > 0;
  const currentLabel =
    selectedLabels.length === 0
      ? "All"
      : selectedLabels.length === 1
        ? selectedLabels[0]
        : `已选 ${selectedLabels.length} 项`;
  const filterSummary =
    selectedLabels.length <= 1 ? currentLabel : `已选 ${selectedLabels.length} 项`;

  function navigate(nextValues: string[]) {
    const params = new URLSearchParams();
    params.set("scope", scope);
    if (q) {
      params.set("q", q);
    }
    for (const nextValue of nextValues) {
      params.append("recipe", nextValue);
    }
    router.push(`/dataset?${params.toString()}`);
  }

  function handleToggle(value: string) {
    if (currentValues.includes(value)) {
      navigate(currentValues.filter((item) => item !== value));
      return;
    }

    navigate([...currentValues, value]);
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {variant === "icon" ? (
          <Button
            aria-label={hasSelections ? `数据格式筛选，${filterSummary}` : "数据格式筛选"}
            className={cn(
              "h-7 w-7 rounded-sm px-0",
              hasSelections && "border-zinc-300 bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
            )}
            title={hasSelections ? `数据格式：${filterSummary}` : "数据格式筛选"}
            type="button"
            variant="ghost"
          >
            <ListFilter className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            className={cn(
              consoleListFilterTriggerClassName,
              "w-full min-w-0 text-left"
            )}
            type="button"
            variant="ghost"
          >
            <span className="truncate">{currentLabel}</span>
            <ChevronDown className="ml-2 h-3 w-3 shrink-0 text-slate-500" />
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[148px] min-w-[148px] rounded-lg border-slate-800/85 p-1">
        <DropdownMenuItem
          className={cn(
            "min-h-7 justify-between rounded-md px-2 py-1.5 text-[12.5px]",
            !hasSelections && "bg-slate-800/85 font-medium text-slate-50"
          )}
          onSelect={() => navigate([])}
        >
          清空筛选
          {!hasSelections ? <Check className="h-4 w-4" /> : null}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {formatOptions.map((group, groupIndex) => (
          <div key={group.label}>
            {groupIndex > 0 ? <DropdownMenuSeparator /> : null}
            <DropdownMenuLabel className="px-2 py-1 text-[10px] tracking-[0.08em] text-slate-500">
              {group.label}
            </DropdownMenuLabel>
            {group.items.map((item) => (
              <DropdownMenuItem
                className="min-h-7 justify-between rounded-md px-2 py-1.5 text-[12.5px]"
                key={item.value}
                onSelect={(event) => {
                  event.preventDefault();
                  handleToggle(item.value);
                }}
              >
                {item.label}
                {currentValues.includes(item.value) ? <Check className="h-4 w-4" /> : null}
              </DropdownMenuItem>
            ))}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
