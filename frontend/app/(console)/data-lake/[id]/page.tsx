import { redirect } from "next/navigation";
import { getRepo } from "@/features/data-lake/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function RepoOverviewPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const repo = await getRepo(id, projectId);
  redirect(`/data-lake/${id}/tree/${encodeURIComponent(repo.default_branch)}`);
}
