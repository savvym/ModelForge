import Link from "next/link";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { buttonVariants } from "@/components/ui/button";
import { getRepo, getTree } from "@/features/data-lake/api";
import { RepoFileTree } from "@/features/data-lake/components/repo-file-tree";
import { RepoHeader } from "@/features/data-lake/components/repo-header";
import { RepoUploadDialog } from "@/features/data-lake/components/repo-upload-dialog";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function RepoTreePage({
  params
}: {
  params: Promise<{ id: string; ref: string; path?: string[] }>;
}) {
  const resolved = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const path = (resolved.path ?? []).map((segment) => decodeURIComponent(segment)).join("/");
  const ref = decodeURIComponent(resolved.ref);

  const [repo, tree] = await Promise.all([
    getRepo(resolved.id, projectId),
    getTree(resolved.id, ref, path, projectId).catch(() => ({
      ref,
      path,
      entries: []
    }))
  ]);

  const breadcrumbs = buildBreadcrumbs(resolved.id, ref, path);

  return (
    <div className="flex flex-col gap-4">
      <RepoHeader repo={repo} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ConsoleBreadcrumb items={breadcrumbs} />
        <div className="flex gap-2">
          <Link
            href={`/data-lake/${resolved.id}/commits/${encodeURIComponent(ref)}`}
            className={buttonVariants({ size: "sm", variant: "outline" })}
          >
            查看提交历史
          </Link>
          <RepoUploadDialog repoId={resolved.id} branch={ref} currentPath={path} />
        </div>
      </div>
      <RepoFileTree repoId={resolved.id} branch={ref} path={path} entries={tree.entries} />
    </div>
  );
}

function buildBreadcrumbs(repoId: string, ref: string, path: string) {
  const parts = path ? path.split("/") : [];
  const items: { label: string; href?: string }[] = [
    { label: "数据湖", href: "/data-lake" },
    {
      label: ref,
      href: `/data-lake/${repoId}/tree/${encodeURIComponent(ref)}`
    }
  ];
  for (let index = 0; index < parts.length; index += 1) {
    const segment = parts[index];
    const accumulated = parts
      .slice(0, index + 1)
      .map((part) => encodeURIComponent(part))
      .join("/");
    const isLast = index === parts.length - 1;
    items.push({
      label: segment,
      href: isLast ? undefined : `/data-lake/${repoId}/tree/${encodeURIComponent(ref)}/${accumulated}`
    });
  }
  return items;
}
