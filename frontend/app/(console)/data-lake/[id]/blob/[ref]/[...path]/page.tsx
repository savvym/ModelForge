import { notFound } from "next/navigation";
import { ConsoleBreadcrumb } from "@/components/console/console-breadcrumb";
import { getFile, getRepo } from "@/features/data-lake/api";
import { RepoFileViewer } from "@/features/data-lake/components/repo-file-viewer";
import { RepoHeader } from "@/features/data-lake/components/repo-header";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function RepoBlobPage({
  params
}: {
  params: Promise<{ id: string; ref: string; path: string[] }>;
}) {
  const resolved = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const path = resolved.path.map((segment) => decodeURIComponent(segment)).join("/");
  const ref = decodeURIComponent(resolved.ref);

  const repo = await getRepo(resolved.id, projectId);
  let file;
  try {
    file = await getFile(resolved.id, ref, path, projectId);
  } catch {
    notFound();
  }

  return (
    <div className="flex flex-col gap-4">
      <RepoHeader repo={repo} />
      <ConsoleBreadcrumb items={buildBreadcrumbs(resolved.id, ref, path)} />
      <RepoFileViewer repoId={resolved.id} file={file} />
    </div>
  );
}

function buildBreadcrumbs(repoId: string, ref: string, path: string) {
  const parts = path.split("/");
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
    if (isLast) {
      items.push({ label: segment });
    } else {
      items.push({
        label: segment,
        href: `/data-lake/${repoId}/tree/${encodeURIComponent(ref)}/${accumulated}`
      });
    }
  }
  return items;
}
