import { notFound } from "next/navigation";
import { EvaluationLeaderboardDetailPanel } from "@/features/eval/components/evaluation-leaderboard-detail-panel";
import { getEvaluationLeaderboard } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EvaluationLeaderboardDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const detail = await getEvaluationLeaderboard(id, projectId).catch(() => null);

  if (!detail) {
    notFound();
  }

  return <EvaluationLeaderboardDetailPanel initialLeaderboard={detail} />;
}
