"use client";

import * as React from "react";
import {
  Check,
  ChevronRight,
  LibraryBig,
  Search,
  Server
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type ModelTargetSource = "registry" | "deployment";

export type ModelTargetOption = {
  id: string;
  modelId?: string | null;
  name: string;
  providerName: string;
  source: ModelTargetSource;
  targetId: string;
};

type ModelTargetSelectorDialogProps = {
  description?: string;
  emptyMessage?: string;
  onOpenChange: (open: boolean) => void;
  onSelect: (modelId: string) => void;
  open: boolean;
  options: ModelTargetOption[];
  selectedId: string;
  title?: string;
  trigger: React.ReactNode;
};

const ALL_PROVIDERS = "__all__";

export function ModelTargetSelectorDialog({
  description = "从模型广场或我的部署中选择一个可用模型。",
  emptyMessage = "当前没有可选择的模型。",
  onOpenChange,
  onSelect,
  open,
  options,
  selectedId,
  title = "选择模型",
  trigger
}: ModelTargetSelectorDialogProps) {
  const selectedModel = options.find((option) => option.id === selectedId) ?? null;
  const registryOptions = React.useMemo(
    () => options.filter((option) => option.source === "registry"),
    [options]
  );
  const deploymentOptions = React.useMemo(
    () => options.filter((option) => option.source === "deployment"),
    [options]
  );
  const [activeSource, setActiveSource] = React.useState<ModelTargetSource>(
    selectedModel?.source ?? (registryOptions.length ? "registry" : "deployment")
  );
  const [activeProvider, setActiveProvider] = React.useState(
    selectedModel?.source === "registry" ? selectedModel.providerName : ALL_PROVIDERS
  );
  const [query, setQuery] = React.useState("");

  React.useEffect(() => {
    if (!open) {
      return;
    }

    const nextSource = selectedModel?.source ?? (registryOptions.length ? "registry" : "deployment");
    setActiveSource(nextSource);
    setActiveProvider(
      selectedModel?.source === "registry" ? selectedModel.providerName : ALL_PROVIDERS
    );
    setQuery("");
  }, [open, registryOptions.length, selectedModel]);

  const providerSummaries = React.useMemo(() => {
    const counts = new Map<string, number>();
    registryOptions.forEach((option) => {
      counts.set(option.providerName, (counts.get(option.providerName) ?? 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, count]) => ({ count, name }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [registryOptions]);

  const modelSourceTabs = [
    {
      count: registryOptions.length,
      icon: LibraryBig,
      label: "模型广场",
      value: "registry" as const
    },
    {
      count: deploymentOptions.length,
      icon: Server,
      label: "我的部署",
      value: "deployment" as const
    }
  ];

  const visibleRegistryOptions = registryOptions.filter((option) => {
    if (activeProvider !== ALL_PROVIDERS && option.providerName !== activeProvider) {
      return false;
    }
    return matchesModelQuery(option, query);
  });
  const visibleDeploymentOptions = deploymentOptions.filter((option) =>
    matchesModelQuery(option, query)
  );
  const visibleOptions =
    activeSource === "registry" ? visibleRegistryOptions : visibleDeploymentOptions;

  function selectModel(modelId: string) {
    onSelect(modelId);
    onOpenChange(false);
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[min(760px,calc(100vh-2rem))] max-w-[940px] gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-5 py-4 pr-14">
          <DialogTitle className="text-[18px] text-foreground">{title}</DialogTitle>
          <DialogDescription className="text-xs leading-5">{description}</DialogDescription>
          <div className="relative mt-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-9 rounded-lg bg-background/70 pl-9"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索模型、Provider 或部署"
              value={query}
            />
          </div>
        </DialogHeader>

        {options.length ? (
          <div className="grid min-h-[460px] grid-cols-1 overflow-hidden md:grid-cols-[168px_minmax(0,1fr)] lg:grid-cols-[168px_230px_minmax(0,1fr)]">
            <div className="border-b border-border bg-muted/20 p-2 md:border-b-0 md:border-r">
              <div className="space-y-1">
                {modelSourceTabs.map((item) => {
                  const isActive = item.value === activeSource;
                  return (
                    <button
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors",
                        isActive
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-background/70 hover:text-foreground"
                      )}
                      key={item.value}
                      onClick={() => {
                        setActiveSource(item.value);
                        if (item.value === "deployment") {
                          setActiveProvider(ALL_PROVIDERS);
                        }
                      }}
                      type="button"
                    >
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {item.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {activeSource === "registry" ? (
              <ProviderColumn
                activeProvider={activeProvider}
                onProviderChange={setActiveProvider}
                providers={providerSummaries}
                totalCount={registryOptions.length}
              />
            ) : null}

            <div className="min-h-0 overflow-hidden">
              <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground">
                    {activeSource === "registry" ? formatProviderTitle(activeProvider) : "我的部署"}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {visibleOptions.length.toLocaleString("zh-CN")} 个可选模型
                  </div>
                </div>
                {activeSource === "registry" && activeProvider !== ALL_PROVIDERS ? (
                  <Badge variant="secondary" className="max-w-[220px] truncate">
                    {activeProvider}
                  </Badge>
                ) : null}
              </div>

              <div className="console-scrollbar-subtle max-h-[430px] min-h-[360px] overflow-y-auto p-2">
                {visibleOptions.length ? (
                  <div className="space-y-1">
                    {visibleOptions.map((model) => (
                      <ModelTargetRow
                        key={model.id}
                        model={model}
                        onSelect={() => selectModel(model.id)}
                        selected={model.id === selectedId}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex min-h-[300px] items-center justify-center px-4 text-center text-sm text-muted-foreground">
                    当前筛选下没有可选模型。
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex min-h-[280px] items-center justify-center px-8 text-center text-sm text-muted-foreground">
            {emptyMessage}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ProviderColumn({
  activeProvider,
  onProviderChange,
  providers,
  totalCount
}: {
  activeProvider: string;
  onProviderChange: (provider: string) => void;
  providers: Array<{ count: number; name: string }>;
  totalCount: number;
}) {
  return (
    <div className="min-h-0 border-b border-border bg-card/50 md:border-b-0 lg:border-r">
      <div className="border-b border-border px-4 py-3">
        <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Provider</div>
        <div className="mt-1 text-sm font-medium text-foreground">递进筛选</div>
      </div>
      <div className="console-scrollbar-subtle max-h-[220px] overflow-y-auto p-2 lg:max-h-[430px]">
        <ProviderButton
          active={activeProvider === ALL_PROVIDERS}
          count={totalCount}
          label="全部 Provider"
          onClick={() => onProviderChange(ALL_PROVIDERS)}
        />
        {providers.map((provider) => (
          <ProviderButton
            active={provider.name === activeProvider}
            count={provider.count}
            key={provider.name}
            label={provider.name}
            onClick={() => onProviderChange(provider.name)}
          />
        ))}
      </div>
    </div>
  );
}

function ProviderButton({
  active,
  count,
  label,
  onClick
}: {
  active: boolean;
  count: number;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "group mb-1 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
      )}
      onClick={onClick}
      type="button"
    >
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
      <ChevronRight
        className={cn(
          "h-3.5 w-3.5 shrink-0 transition-opacity",
          active ? "opacity-100" : "opacity-0 group-hover:opacity-70"
        )}
      />
    </button>
  );
}

function ModelTargetRow({
  model,
  onSelect,
  selected
}: {
  model: ModelTargetOption;
  onSelect: () => void;
  selected: boolean;
}) {
  return (
    <button
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
        selected
          ? "border-primary/40 bg-primary/10"
          : "border-transparent bg-transparent hover:border-border hover:bg-muted/45"
      )}
      onClick={onSelect}
      type="button"
    >
      <span
        className={cn(
          "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
          model.source === "deployment" ? "bg-emerald-500" : "bg-primary"
        )}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {model.name}
        </span>
        <span className="mt-1 block truncate text-xs text-muted-foreground">
          {model.providerName}
        </span>
        <span className="mt-1 block truncate font-mono text-[11px] text-muted-foreground/80">
          {model.targetId}
        </span>
      </span>
      {selected ? <Check className="mt-1 h-4 w-4 shrink-0 text-primary" /> : null}
    </button>
  );
}

function matchesModelQuery(option: ModelTargetOption, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  return [option.name, option.providerName, option.targetId, option.modelId ?? ""]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function formatProviderTitle(provider: string) {
  return provider === ALL_PROVIDERS ? "全部模型广场模型" : provider;
}
