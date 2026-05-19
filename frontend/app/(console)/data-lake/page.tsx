import {
  ConsoleListHeader,
  ConsoleListSearchForm,
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { listRepos } from "@/features/data-lake/api";
import { RepoCreateDialog } from "@/features/data-lake/components/repo-create-dialog";
import { RepoListTable } from "@/features/data-lake/components/repo-list-table";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function DataLakePage({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const projectId = await getCurrentProjectIdFromCookie();
  const result = await listRepos({ query, pageSize: 100 }, projectId).catch(() => ({
    items: [],
    total: 0,
    page: 1,
    page_size: 100
  }));

  return (
    <div className="flex flex-col gap-4">
      <ConsoleListHeader
        title="数据湖"
        description="以 Git 仓库为单位管理原始资产 — md、HTML、图片、URL 解析结果都可以放进同一个仓库，并具备版本历史。"
        actions={<RepoCreateDialog />}
      />
      <ConsoleListToolbar>
        <ConsoleListToolbarCluster>
          <ConsoleListSearchForm action="/data-lake" defaultValue={query} placeholder="按名称搜索仓库…" />
        </ConsoleListToolbarCluster>
        <div className="text-xs text-muted-foreground">共 {result.total} 个仓库</div>
      </ConsoleListToolbar>
      <RepoListTable repos={result.items} />
    </div>
  );
}
