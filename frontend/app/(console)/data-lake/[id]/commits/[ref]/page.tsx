import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { getRepo, listCommits } from "@/features/data-lake/api";
import { RepoCommitList } from "@/features/data-lake/components/repo-commit-list";
import { RepoHeader } from "@/features/data-lake/components/repo-header";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function RepoCommitsPage({
  params
}: {
  params: Promise<{ id: string; ref: string }>;
}) {
  const resolved = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const ref = decodeURIComponent(resolved.ref);
  const [repo, history] = await Promise.all([
    getRepo(resolved.id, projectId),
    listCommits(resolved.id, ref, { pageSize: 50 }, projectId).catch(() => ({
      commits: [],
      page: 1,
      page_size: 50,
      total: 0
    }))
  ]);

  return (
    <div className="flex flex-col gap-4">
      <RepoHeader repo={repo} />
      <ConsoleBreadcrumb
        items={[
          { label: "数据湖", href: "/data-lake" },
          { label: ref, href: `/data-lake/${resolved.id}/tree/${encodeURIComponent(ref)}` },
          { label: "提交历史" }
        ]}
      />
      <div className="text-xs text-muted-foreground">{history.total} 次提交</div>
      <RepoCommitList commits={history.commits} />
    </div>
  );
}
