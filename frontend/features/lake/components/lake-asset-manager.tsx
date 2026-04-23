"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import {
  Archive,
  Database,
  FileDown,
  FolderOpen,
  Loader2,
  MoreHorizontal,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud
} from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  ConsoleListFilterField,
  ConsoleListHeader,
  ConsoleListTableSurface,
  ConsoleListToolbar,
  ConsoleListToolbarCluster,
  consoleListFilterTriggerClassName,
  consoleListSearchInputClassName
} from "@/components/console/list-surface";
import {
  archiveBronzeAsset,
  createBronzeImport,
  deleteBronzeAsset,
  refreshBronzeAsset
} from "@/features/lake/api";
import { cn } from "@/lib/utils";
import type {
  BronzeAssetSummary,
  BronzeAssetType,
  BronzeImportMethod,
  BronzeJobSummary
} from "@/types/api";

type LakeAssetManagerProps = {
  assets: BronzeAssetSummary[];
  jobs: BronzeJobSummary[];
};

type ManagerTab = "assets" | "sources" | "jobs";

type ImportFormState = {
  assetType: BronzeAssetType;
  importMethod: BronzeImportMethod;
  sourceUri: string;
  urlList: string;
  name: string;
  provider: string;
  product: string;
  tags: string;
  captureMode: string;
  extractImages: string;
  triggerSilver: string;
  entrypoint: string;
  manifestUri: string;
};

const defaultImportForm: ImportFormState = {
  assetType: "web_page",
  importMethod: "url",
  sourceUri: "",
  urlList: "",
  name: "",
  provider: "",
  product: "",
  tags: "",
  captureMode: "raw_render_screenshot",
  extractImages: "yes",
  triggerSilver: "no",
  entrypoint: "",
  manifestUri: ""
};

const assetTypeOptions: Array<{
  value: BronzeAssetType;
  label: string;
  description: string;
}> = [
  {
    value: "web_page",
    label: "网页",
    description: "需要 URL，由抓取任务冻结 raw / rendered / screenshot"
  },
  {
    value: "website_batch",
    label: "批量网页",
    description: "需要 sitemap URL 或 URL 列表"
  },
  {
    value: "pdf",
    label: "PDF",
    description: "需要对象存储文件 URI"
  },
  {
    value: "markdown",
    label: "Markdown",
    description: "需要对象存储文件 URI"
  },
  {
    value: "markdown_package",
    label: "Markdown + Images",
    description: "需要对象存储目录，可选入口文件与 manifest"
  },
  {
    value: "image",
    label: "图片",
    description: "需要对象存储图片 URI"
  },
  {
    value: "object_prefix",
    label: "对象目录",
    description: "需要对象存储目录 prefix"
  }
];

const importMethodOptionsByAssetType: Record<
  BronzeAssetType,
  Array<{ value: BronzeImportMethod; label: string }>
> = {
  web_page: [{ value: "url", label: "URL" }],
  website_batch: [
    { value: "sitemap", label: "Sitemap URL" },
    { value: "url_list", label: "URL 列表" }
  ],
  pdf: [{ value: "object_key", label: "对象存储文件" }],
  markdown: [{ value: "object_key", label: "对象存储文件" }],
  markdown_package: [{ value: "object_prefix", label: "对象存储目录" }],
  image: [{ value: "object_key", label: "对象存储文件" }],
  object_prefix: [{ value: "object_prefix", label: "对象存储目录" }]
};

const defaultImportMethodByAssetType: Record<BronzeAssetType, BronzeImportMethod> = {
  web_page: "url",
  website_batch: "sitemap",
  pdf: "object_key",
  markdown: "object_key",
  markdown_package: "object_prefix",
  image: "object_key",
  object_prefix: "object_prefix"
};

export function LakeAssetManager({ assets, jobs }: LakeAssetManagerProps) {
  const router = useRouter();
  const [items, setItems] = React.useState(assets);
  const [jobItems, setJobItems] = React.useState(jobs);
  const [activeTab, setActiveTab] = React.useState<ManagerTab>("assets");
  const [query, setQuery] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [sourceTypeFilter, setSourceTypeFilter] = React.useState("all");
  const [importOpen, setImportOpen] = React.useState(false);
  const [importForm, setImportForm] = React.useState<ImportFormState>(defaultImportForm);
  const [submittingImport, setSubmittingImport] = React.useState(false);
  const [pendingAction, setPendingAction] = React.useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = React.useState<BronzeAssetSummary | null>(null);

  React.useEffect(() => {
    setItems(assets);
  }, [assets]);

  React.useEffect(() => {
    setJobItems(jobs);
  }, [jobs]);

  const sourceTypeOptions = React.useMemo(() => {
    return Array.from(new Set(items.map((asset) => asset.source_type))).sort((left, right) =>
      left.localeCompare(right, "zh-CN")
    );
  }, [items]);

  const filteredItems = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((asset) => {
      const matchesQuery =
        !normalizedQuery ||
        asset.name.toLowerCase().includes(normalizedQuery) ||
        asset.id.toLowerCase().includes(normalizedQuery) ||
        (asset.source_uri ?? "").toLowerCase().includes(normalizedQuery) ||
        (asset.provider ?? "").toLowerCase().includes(normalizedQuery) ||
        (asset.product ?? "").toLowerCase().includes(normalizedQuery) ||
        asset.ingestion_job_name.toLowerCase().includes(normalizedQuery);
      const matchesStatus = statusFilter === "all" || asset.status === statusFilter;
      const matchesSourceType =
        sourceTypeFilter === "all" || asset.source_type === sourceTypeFilter;
      return matchesQuery && matchesStatus && matchesSourceType;
    });
  }, [items, query, sourceTypeFilter, statusFilter]);

  const sourceRows = React.useMemo(() => buildSourceRows(items), [items]);
  const filteredSources = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sourceRows.filter((source) => {
      return (
        !normalizedQuery ||
        source.uri.toLowerCase().includes(normalizedQuery) ||
        source.provider.toLowerCase().includes(normalizedQuery) ||
        source.product.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [query, sourceRows]);

  const capturedCount = items.filter((asset) => asset.status === "captured").length;
  const registeredCount = items.filter((asset) => asset.status === "registered").length;
  const artifactCount = items.reduce((sum, asset) => sum + asset.artifact_count, 0);
  const imageCount = items.reduce((sum, asset) => sum + asset.image_count, 0);
  const selectedAssetTypeOption =
    assetTypeOptions.find((option) => option.value === importForm.assetType) ?? assetTypeOptions[0];
  const importMethodOptions = importMethodOptionsByAssetType[importForm.assetType];
  const showCaptureControls =
    importForm.assetType === "web_page" || importForm.assetType === "website_batch";
  const showEntrypoint =
    importForm.assetType === "markdown_package" || importForm.assetType === "object_prefix";

  async function handleImportSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sourceUri =
      importForm.importMethod === "url_list"
        ? importForm.urlList.trim()
        : importForm.sourceUri.trim();
    if (!sourceUri) {
      toast.error(getSourceUriRequiredMessage(importForm.assetType, importForm.importMethod));
      return;
    }

    setSubmittingImport(true);
    try {
      const result = await createBronzeImport({
        asset_type: importForm.assetType,
        import_method: importForm.importMethod,
        source_uri: sourceUri,
        name: importForm.name.trim() || null,
        provider: importForm.provider.trim() || null,
        product: importForm.product.trim() || null,
        tags: parseTags(importForm.tags),
        capture_mode: importForm.captureMode,
        extract_images: importForm.extractImages === "yes",
        trigger_silver: importForm.triggerSilver === "yes",
        entrypoint: importForm.entrypoint.trim() || null,
        manifest_uri: importForm.manifestUri.trim() || null
      });
      setItems((current) => [
        result.asset,
        ...current.filter((asset) => asset.id !== result.asset.id)
      ]);
      setJobItems((current) => [
        result.job,
        ...current.filter((job) => job.id !== result.job.id)
      ]);
      setImportOpen(false);
      setImportForm(defaultImportForm);
      toast.success(`已登记 ${formatSourceTypeLabel(result.asset.source_type)} 资产`);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入 Bronze 资产失败");
    } finally {
      setSubmittingImport(false);
    }
  }

  async function handleRefresh(asset: BronzeAssetSummary) {
    setPendingAction(`refresh:${asset.id}`);
    try {
      const job = await refreshBronzeAsset(asset.id);
      setItems((current) =>
        current.map((item) =>
          item.id === asset.id
            ? { ...item, status: "capturing", hash_status: "pending", updated_at: new Date().toISOString() }
            : item
        )
      );
      setJobItems((current) => current.map((item) => (item.id === job.id ? job : item)));
      toast.success("已提交刷新抓取");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "刷新抓取失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleArchive(asset: BronzeAssetSummary) {
    setPendingAction(`archive:${asset.id}`);
    try {
      const detail = await archiveBronzeAsset(asset.id);
      setItems((current) =>
        current.map((item) => (item.id === asset.id ? summarizeDetail(detail) : item))
      );
      toast.success("已归档 Bronze 资产");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "归档失败");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSoftDelete() {
    if (!confirmTarget) {
      return;
    }
    setPendingAction(`delete:${confirmTarget.id}`);
    try {
      await deleteBronzeAsset(confirmTarget.id);
      setItems((current) => current.filter((asset) => asset.id !== confirmTarget.id));
      toast.success("已软删除 Bronze 资产");
      setConfirmTarget(null);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除失败");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ConsoleListHeader
        actions={
          <>
            <Button onClick={() => setImportOpen(true)} size="sm" type="button">
              <UploadCloud data-icon="inline-start" />
              导入 Bronze 资产
            </Button>
            <Link href="/data">
              <Button size="sm" type="button" variant="outline">
                <FolderOpen data-icon="inline-start" />
                对象存储
              </Button>
            </Link>
          </>
        }
        description="数据湖现在承载 Bronze：网页、PDF、Markdown、图片和对象目录会在这里冻结为 snapshot 与 artifacts。"
        title="数据湖"
      />

      <div className="grid gap-3 md:grid-cols-4">
        <SummaryStatCard icon={Database} label="Bronze 资产" value={items.length} hint={`${capturedCount} 个已冻结`} />
        <SummaryStatCard icon={Search} label="登记待处理" value={registeredCount} hint="等待抓取或生成 manifest" />
        <SummaryStatCard icon={FileDown} label="Artifacts" value={artifactCount} hint={`${imageCount} 个图片证据`} />
        <SummaryStatCard icon={RefreshCw} label="导入任务" value={jobItems.length} hint="按资产类型选择来源方式" />
      </div>

      <Tabs onValueChange={(value) => setActiveTab(value as ManagerTab)} value={activeTab}>
        <TabsList className="h-auto w-full justify-start gap-1 rounded-lg border border-border/60 bg-card/60 p-1">
          <TabsTrigger value="assets">资产</TabsTrigger>
          <TabsTrigger value="sources">数据源</TabsTrigger>
          <TabsTrigger value="jobs">导入任务</TabsTrigger>
        </TabsList>

        <ConsoleListToolbar className="pt-3">
          <ConsoleListToolbarCluster className="min-w-0 flex-1 gap-2">
            <div className="relative min-w-[300px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className={cn(consoleListSearchInputClassName, "w-full")}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索资产、来源、产品、Provider 或任务"
                type="search"
                value={query}
              />
            </div>

            <ConsoleListFilterField className="w-[156px] min-w-[156px]" label="状态">
              <Select onValueChange={setStatusFilter} value={statusFilter}>
                <SelectTrigger className={consoleListFilterTriggerClassName}>
                  <SelectValue placeholder="全部状态" />
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectGroup>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="registered">已登记</SelectItem>
                    <SelectItem value="capturing">抓取中</SelectItem>
                    <SelectItem value="captured">已保存</SelectItem>
                    <SelectItem value="changed">已变化</SelectItem>
                    <SelectItem value="unchanged">未变化</SelectItem>
                    <SelectItem value="failed">失败</SelectItem>
                    <SelectItem value="archived">归档</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </ConsoleListFilterField>

            <ConsoleListFilterField className="w-[172px] min-w-[172px]" label="来源类型">
              <Select onValueChange={setSourceTypeFilter} value={sourceTypeFilter}>
                <SelectTrigger className={consoleListFilterTriggerClassName}>
                  <SelectValue placeholder="全部来源" />
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectGroup>
                    <SelectItem value="all">全部来源</SelectItem>
                    {sourceTypeOptions.map((value) => (
                      <SelectItem key={value} value={value}>
                        {formatSourceTypeLabel(value)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </ConsoleListFilterField>
          </ConsoleListToolbarCluster>
        </ConsoleListToolbar>

        <TabsContent className="mt-3" value="assets">
          <AssetsTable
            assets={filteredItems}
            onArchive={handleArchive}
            onDelete={setConfirmTarget}
            onRefresh={handleRefresh}
            pendingAction={pendingAction}
          />
        </TabsContent>

        <TabsContent className="mt-3" value="sources">
          <SourcesTable sources={filteredSources} />
        </TabsContent>

        <TabsContent className="mt-3" value="jobs">
          <JobsTable jobs={jobItems} />
        </TabsContent>
      </Tabs>

      <Dialog onOpenChange={setImportOpen} open={importOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>导入 Bronze 资产</DialogTitle>
            <DialogDescription>
              先选择资产类型，再填写这种资产需要的来源位置。URL 只属于网页类资产。
            </DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-4" onSubmit={handleImportSubmit}>
            <div className="grid gap-3 md:grid-cols-2">
              <Field className="md:col-span-2" label="资产类型">
                <Select
                  onValueChange={(value) => {
                    const assetType = value as BronzeAssetType;
                    setImportForm((current) => ({
                      ...current,
                      assetType,
                      importMethod: defaultImportMethodByAssetType[assetType],
                      sourceUri: "",
                      urlList: "",
                      entrypoint: "",
                      manifestUri: ""
                    }));
                  }}
                  value={importForm.assetType}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {assetTypeOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{selectedAssetTypeOption.description}</p>
              </Field>

              <Field label="来源方式">
                <Select
                  onValueChange={(value) =>
                    setImportForm((current) => ({
                      ...current,
                      importMethod: value as BronzeImportMethod,
                      sourceUri: "",
                      urlList: ""
                    }))
                  }
                  value={importForm.importMethod}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {importMethodOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>

              <SourceLocatorField
                assetType={importForm.assetType}
                importMethod={importForm.importMethod}
                onSourceUriChange={(value) =>
                  setImportForm((current) => ({ ...current, sourceUri: value }))
                }
                onUrlListChange={(value) =>
                  setImportForm((current) => ({ ...current, urlList: value }))
                }
                sourceUri={importForm.sourceUri}
                urlList={importForm.urlList}
              />

              <Field label="资产名称">
                <Input
                  onChange={(event) => setImportForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="留空则按来源位置生成"
                  value={importForm.name}
                />
              </Field>
              <Field label="Provider">
                <Input
                  onChange={(event) => setImportForm((current) => ({ ...current, provider: event.target.value }))}
                  placeholder="tencent"
                  value={importForm.provider}
                />
              </Field>
              <Field label="产品 / 领域">
                <Input
                  onChange={(event) => setImportForm((current) => ({ ...current, product: event.target.value }))}
                  placeholder="tencent-clb"
                  value={importForm.product}
                />
              </Field>
              <Field label="Tags">
                <Input
                  onChange={(event) => setImportForm((current) => ({ ...current, tags: event.target.value }))}
                  placeholder="clb, docs, api"
                  value={importForm.tags}
                />
              </Field>
              {showEntrypoint ? (
                <>
                  <Field label="入口文件">
                    <Input
                      onChange={(event) =>
                        setImportForm((current) => ({ ...current, entrypoint: event.target.value }))
                      }
                      placeholder="original.md 或 docs/index.md"
                      value={importForm.entrypoint}
                    />
                  </Field>
                  <Field label="Manifest URI">
                    <Input
                      onChange={(event) =>
                        setImportForm((current) => ({ ...current, manifestUri: event.target.value }))
                      }
                      placeholder="s3://bucket/path/manifest.json"
                      value={importForm.manifestUri}
                    />
                  </Field>
                </>
              ) : null}
              {showCaptureControls ? (
                <>
                  <Field label="抓取模式">
                    <Select
                      onValueChange={(value) => setImportForm((current) => ({ ...current, captureMode: value }))}
                      value={importForm.captureMode}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem value="raw_render_screenshot">raw + render + screenshot</SelectItem>
                          <SelectItem value="raw_only">raw only</SelectItem>
                          <SelectItem value="render_screenshot">render + screenshot</SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="提取图片">
                    <Select
                      onValueChange={(value) => setImportForm((current) => ({ ...current, extractImages: value }))}
                      value={importForm.extractImages}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem value="yes">是</SelectItem>
                          <SelectItem value="no">否</SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                </>
              ) : null}
              <Field label="触发 Silver">
                <Select
                  onValueChange={(value) => setImportForm((current) => ({ ...current, triggerSilver: value }))}
                  value={importForm.triggerSilver}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="no">否</SelectItem>
                      <SelectItem value="yes">是</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            <DialogFooter>
              <Button
                disabled={submittingImport}
                onClick={() => setImportOpen(false)}
                type="button"
                variant="outline"
              >
                取消
              </Button>
              <Button disabled={submittingImport} type="submit">
                {submittingImport ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
                登记资产
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        onOpenChange={(open) => {
          if (!open && !pendingAction?.startsWith("delete:")) {
            setConfirmTarget(null);
          }
        }}
        open={confirmTarget !== null}
      >
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>软删除 Bronze 资产</AlertDialogTitle>
            <AlertDialogDescription>
              这会移除资产记录的默认可见性，但不会直接删除对象存储里的 artifacts。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="rounded-lg border border-border bg-card/80 px-3 py-2 text-sm">
            <div className="font-medium text-foreground">{confirmTarget?.name}</div>
            <div className="mt-1 truncate text-xs text-muted-foreground">
              {confirmTarget?.source_uri ?? confirmTarget?.id}
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingAction?.startsWith("delete:")}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="min-w-[96px] bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={pendingAction?.startsWith("delete:")}
              onClick={() => void handleSoftDelete()}
            >
              {pendingAction?.startsWith("delete:") ? "删除中..." : "软删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AssetsTable({
  assets,
  onArchive,
  onDelete,
  onRefresh,
  pendingAction
}: {
  assets: BronzeAssetSummary[];
  onArchive: (asset: BronzeAssetSummary) => void;
  onDelete: (asset: BronzeAssetSummary) => void;
  onRefresh: (asset: BronzeAssetSummary) => void;
  pendingAction: string | null;
}) {
  return (
    <ConsoleListTableSurface>
      <Table className="min-w-[1520px] table-fixed">
        <TableHeader className="bg-transparent">
          <TableRow className="hover:bg-transparent">
            <TableHead className={stickyHeadClassName}>资产名称</TableHead>
            <TableHead className="w-[130px]">来源类型</TableHead>
            <TableHead className="w-[300px]">来源 URI</TableHead>
            <TableHead className="w-[150px]">产品 / 领域</TableHead>
            <TableHead className="w-[150px]">最新快照</TableHead>
            <TableHead className="w-[110px]">Artifacts</TableHead>
            <TableHead className="w-[120px]">Hash 状态</TableHead>
            <TableHead className="w-[120px]">状态</TableHead>
            <TableHead className="w-[160px]">导入任务</TableHead>
            <TableHead className="w-[145px]">更新时间</TableHead>
            <TableHead className="w-[120px] text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {assets.length === 0 ? (
            <EmptyRow colSpan={11} message="没有匹配的 Bronze 资产" />
          ) : (
            assets.map((asset) => {
              const statusMeta = getBronzeStatusMeta(asset.status);
              const isRefreshing = pendingAction === `refresh:${asset.id}`;
              const isArchiving = pendingAction === `archive:${asset.id}`;
              return (
                <TableRow key={asset.id} className="bg-transparent">
                  <TableCell className={stickyCellClassName}>
                    <div className="min-w-0">
                      <Link className="truncate font-medium text-foreground hover:underline" href={`/lake-assets/${asset.id}`}>
                        {asset.name}
                      </Link>
                      <div className="mt-1 truncate text-xs text-muted-foreground">{asset.id}</div>
                    </div>
                  </TableCell>
                  <TableCell>{formatSourceTypeLabel(asset.source_type)}</TableCell>
                  <TableCell>
                    <div className="truncate text-sm text-muted-foreground">{asset.source_uri ?? "-"}</div>
                  </TableCell>
                  <TableCell>
                    <div className="truncate text-sm text-foreground">
                      {asset.product || asset.provider || "未归类"}
                    </div>
                    {asset.provider ? <div className="mt-1 truncate text-xs text-muted-foreground">{asset.provider}</div> : null}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {asset.latest_snapshot_at ? formatDateTime(asset.latest_snapshot_at) : "无 snapshot"}
                  </TableCell>
                  <TableCell className="text-sm text-foreground">
                    {asset.artifact_count} files
                    {asset.image_count ? ` / ${asset.image_count} images` : ""}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{formatHashStatus(asset.hash_status)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="truncate text-sm text-foreground">{asset.ingestion_job_name}</div>
                    <div className="mt-1 truncate text-xs text-muted-foreground">{asset.ingestion_job_id}</div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDateTime(asset.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button aria-label="资产操作" className="size-8 p-0" size="sm" type="button" variant="ghost">
                          <MoreHorizontal />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-44">
                        <DropdownMenuGroup>
                          <DropdownMenuItem asChild>
                            <Link href={`/lake-assets/${asset.id}`}>查看详情</Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem disabled={isRefreshing} onClick={() => onRefresh(asset)}>
                            <RefreshCw />
                            刷新抓取
                          </DropdownMenuItem>
                          <DropdownMenuItem disabled>生成 Silver</DropdownMenuItem>
                          <DropdownMenuItem disabled={isArchiving} onClick={() => onArchive(asset)}>
                            <Archive />
                            归档
                          </DropdownMenuItem>
                          <DropdownMenuItem disabled={!asset.object_key} asChild={!!asset.object_key}>
                            {asset.object_key ? (
                              <Link href={buildObjectHref(asset)}>
                                <FolderOpen />
                                打开对象
                              </Link>
                            ) : (
                              <span>打开对象</span>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuItem className="text-destructive" onClick={() => onDelete(asset)}>
                            <Trash2 />
                            删除
                          </DropdownMenuItem>
                        </DropdownMenuGroup>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
  );
}

function SourcesTable({ sources }: { sources: SourceRow[] }) {
  return (
    <ConsoleListTableSurface>
      <Table className="min-w-[980px] table-fixed">
        <TableHeader className="bg-transparent">
          <TableRow className="hover:bg-transparent">
            <TableHead>来源 URI</TableHead>
            <TableHead className="w-[140px]">Provider</TableHead>
            <TableHead className="w-[160px]">产品 / 领域</TableHead>
            <TableHead className="w-[120px]">资产数</TableHead>
            <TableHead className="w-[140px]">最新状态</TableHead>
            <TableHead className="w-[150px]">更新时间</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sources.length === 0 ? (
            <EmptyRow colSpan={6} message="没有匹配的数据源" />
          ) : (
            sources.map((source) => {
              const statusMeta = getBronzeStatusMeta(source.status);
              return (
                <TableRow key={source.key}>
                  <TableCell>
                    <div className="truncate font-medium text-foreground">{source.uri}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{formatSourceTypeLabel(source.sourceType)}</div>
                  </TableCell>
                  <TableCell>{source.provider || "-"}</TableCell>
                  <TableCell>{source.product || "未归类"}</TableCell>
                  <TableCell>{source.assetCount}</TableCell>
                  <TableCell>
                    <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDateTime(source.updatedAt)}</TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
  );
}

function JobsTable({ jobs }: { jobs: BronzeJobSummary[] }) {
  return (
    <ConsoleListTableSurface>
      <Table className="min-w-[980px] table-fixed">
        <TableHeader className="bg-transparent">
          <TableRow className="hover:bg-transparent">
            <TableHead>导入任务</TableHead>
            <TableHead className="w-[140px]">来源</TableHead>
            <TableHead className="w-[120px]">状态</TableHead>
            <TableHead className="w-[140px]">进度</TableHead>
            <TableHead className="w-[150px]">创建时间</TableHead>
            <TableHead className="w-[150px]">更新时间</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.length === 0 ? (
            <EmptyRow colSpan={6} message="还没有 Bronze 导入任务" />
          ) : (
            jobs.map((job) => {
              const statusMeta = getBronzeStatusMeta(job.status);
              return (
                <TableRow key={job.id}>
                  <TableCell>
                    <div className="truncate font-medium text-foreground">{job.name}</div>
                    <div className="mt-1 truncate text-xs text-muted-foreground">{job.id}</div>
                  </TableCell>
                  <TableCell>
                    {formatSourceTypeLabel(job.resource_type || job.source_type)} · {job.source_type}
                  </TableCell>
                  <TableCell>
                    <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
                  </TableCell>
                  <TableCell>
                    {job.completed_asset_count}/{job.planned_asset_count}
                    {job.failed_asset_count ? `，失败 ${job.failed_asset_count}` : ""}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDateTime(job.created_at)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDateTime(job.updated_at)}</TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </ConsoleListTableSurface>
  );
}

function SummaryStatCard({
  icon: Icon,
  hint,
  label,
  value
}: {
  icon: typeof Database;
  hint: string;
  label: string;
  value: number | string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="text-[12px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold text-foreground">{value}</div>
          <div className="truncate text-xs text-muted-foreground">{hint}</div>
        </div>
        <div className="rounded-full border border-border bg-background/60 p-2 text-foreground">
          <Icon className="size-4" />
        </div>
      </div>
    </div>
  );
}

function SourceLocatorField({
  assetType,
  importMethod,
  onSourceUriChange,
  onUrlListChange,
  sourceUri,
  urlList
}: {
  assetType: BronzeAssetType;
  importMethod: BronzeImportMethod;
  onSourceUriChange: (value: string) => void;
  onUrlListChange: (value: string) => void;
  sourceUri: string;
  urlList: string;
}) {
  const config = getSourceLocatorConfig(assetType, importMethod);

  if (importMethod === "url_list") {
    return (
      <Field className="md:col-span-2" label={config.label}>
        <Textarea
          autoFocus
          onChange={(event) => onUrlListChange(event.target.value)}
          placeholder={config.placeholder}
          required
          value={urlList}
        />
      </Field>
    );
  }

  return (
    <Field label={config.label}>
      <Input
        autoFocus
        onChange={(event) => onSourceUriChange(event.target.value)}
        placeholder={config.placeholder}
        required
        type={config.inputType}
        value={sourceUri}
      />
    </Field>
  );
}

function Field({
  children,
  className,
  label
}: {
  children: React.ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <TableRow className="bg-transparent hover:bg-transparent">
      <TableCell className="py-12 text-center text-sm text-muted-foreground" colSpan={colSpan}>
        {message}
      </TableCell>
    </TableRow>
  );
}

type SourceRow = {
  key: string;
  uri: string;
  sourceType: string;
  provider: string;
  product: string;
  assetCount: number;
  status: string;
  updatedAt: string;
};

function buildSourceRows(assets: BronzeAssetSummary[]) {
  const byKey = new Map<string, SourceRow>();
  for (const asset of assets) {
    const uri = asset.source_uri || asset.object_key || asset.id;
    const key = `${asset.source_type}:${uri}`;
    const current = byKey.get(key);
    if (!current) {
      byKey.set(key, {
        key,
        uri,
        sourceType: asset.source_type,
        provider: asset.provider || "",
        product: asset.product || "",
        assetCount: 1,
        status: asset.status,
        updatedAt: asset.updated_at
      });
      continue;
    }
    current.assetCount += 1;
    if (new Date(asset.updated_at).getTime() > new Date(current.updatedAt).getTime()) {
      current.status = asset.status;
      current.updatedAt = asset.updated_at;
    }
  }
  return Array.from(byKey.values()).sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
  );
}

function summarizeDetail(detail: BronzeAssetSummary): BronzeAssetSummary {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    source_type: detail.source_type,
    source_uri: detail.source_uri,
    provider: detail.provider,
    product: detail.product,
    tags: detail.tags,
    latest_snapshot_id: detail.latest_snapshot_id,
    latest_snapshot_at: detail.latest_snapshot_at,
    artifact_count: detail.artifact_count,
    image_count: detail.image_count,
    hash_status: detail.hash_status,
    status: detail.status,
    ingestion_job_id: detail.ingestion_job_id,
    ingestion_job_name: detail.ingestion_job_name,
    object_bucket: detail.object_bucket,
    object_key: detail.object_key,
    size_bytes: detail.size_bytes,
    metadata: detail.metadata,
    error_message: detail.error_message,
    created_at: detail.created_at,
    updated_at: detail.updated_at
  };
}

function getSourceLocatorConfig(
  assetType: BronzeAssetType,
  importMethod: BronzeImportMethod
): { label: string; placeholder: string; inputType: "text" | "url" } {
  if (importMethod === "url") {
    return {
      label: "网页 URL",
      placeholder: "https://cloud.tencent.com/document/product/214/6097",
      inputType: "url"
    };
  }
  if (importMethod === "sitemap") {
    return {
      label: "Sitemap URL",
      placeholder: "https://example.com/sitemap.xml",
      inputType: "url"
    };
  }
  if (importMethod === "url_list") {
    return {
      label: "URL 列表",
      placeholder: "https://example.com/page-a\nhttps://example.com/page-b",
      inputType: "text"
    };
  }
  if (importMethod === "object_prefix") {
    return {
      label: assetType === "markdown_package" ? "文档包目录" : "对象目录",
      placeholder: "s3://bucket/bronze/source/asset/snapshot/",
      inputType: "text"
    };
  }
  return {
    label: "对象 URI",
    placeholder: getObjectKeyPlaceholder(assetType),
    inputType: "text"
  };
}

function getObjectKeyPlaceholder(assetType: BronzeAssetType) {
  const placeholderByType: Partial<Record<BronzeAssetType, string>> = {
    pdf: "s3://bucket/bronze/docs/original.pdf",
    markdown: "s3://bucket/bronze/docs/original.md",
    image: "s3://bucket/bronze/images/topology.png"
  };
  return placeholderByType[assetType] ?? "s3://bucket/path/file";
}

function getSourceUriRequiredMessage(
  assetType: BronzeAssetType,
  importMethod: BronzeImportMethod
) {
  if (importMethod === "url_list") {
    return "请输入 URL 列表";
  }
  if (importMethod === "url" || importMethod === "sitemap") {
    return "请输入 URL";
  }
  if (importMethod === "object_prefix") {
    return assetType === "markdown_package" ? "请输入文档包对象目录" : "请输入对象目录 URI";
  }
  return "请输入对象 URI";
}

function parseTags(value: string) {
  return value
    .split(/[,\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function buildObjectHref(asset: BronzeAssetSummary) {
  if (!asset.object_key) {
    return "/data";
  }
  const params = new URLSearchParams();
  if (asset.object_bucket) {
    params.set("bucket", asset.object_bucket);
  }
  const parentPrefix = asset.object_key.includes("/")
    ? `${asset.object_key.slice(0, asset.object_key.lastIndexOf("/"))}/`
    : asset.object_key;
  params.set("prefix", parentPrefix);
  return `/data?${params.toString()}`;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatSourceTypeLabel(value: string) {
  const labelByType: Record<string, string> = {
    directory: "对象目录",
    document: "文档",
    image: "图片",
    markdown: "Markdown",
    markdown_package: "Markdown + Images",
    object_key: "对象文件",
    object_prefix: "对象目录",
    object_storage: "对象存储",
    pdf: "PDF",
    sitemap: "Sitemap",
    upload: "上传",
    uploaded_package: "上传包",
    url: "URL",
    url_list: "URL 列表",
    web_page: "网页",
    website_batch: "批量网页"
  };
  return labelByType[value] ?? value;
}

function formatHashStatus(value: string) {
  const labelByStatus: Record<string, string> = {
    changed: "changed",
    new: "new",
    none: "none",
    pending: "pending",
    unchanged: "unchanged"
  };
  return labelByStatus[value] ?? value;
}

function getBronzeStatusMeta(status: string) {
  const metaByStatus: Record<string, { label: string; className: string }> = {
    archived: {
      label: "归档",
      className: "border-border bg-muted/50 text-muted-foreground"
    },
    captured: {
      label: "已保存",
      className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
    },
    capturing: {
      label: "抓取中",
      className: "border-amber-500/25 bg-amber-500/10 text-amber-200"
    },
    changed: {
      label: "已变化",
      className: "border-sky-500/25 bg-sky-500/10 text-sky-200"
    },
    failed: {
      label: "失败",
      className: "border-rose-500/25 bg-rose-500/10 text-rose-200"
    },
    registered: {
      label: "已登记",
      className: "border-violet-500/25 bg-violet-500/10 text-violet-200"
    },
    unchanged: {
      label: "未变化",
      className: "border-border bg-secondary text-secondary-foreground"
    }
  };
  return (
    metaByStatus[status] ?? {
      label: status,
      className: "border-border bg-muted/40 text-foreground"
    }
  );
}

const stickyHeadClassName =
  "sticky left-0 z-20 w-[320px] min-w-[320px] bg-card/95 pr-5 backdrop-blur";

const stickyCellClassName = cn(
  "sticky left-0 z-10 w-[320px] min-w-[320px] bg-card/95 pr-5 align-top",
  "after:absolute after:right-0 after:top-0 after:h-full after:w-px after:bg-border/70"
);
