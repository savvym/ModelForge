import { notFound } from "next/navigation";
import { BenchmarkLeaderboardDetailPanel } from "@/features/eval/components/benchmark-leaderboard-detail";
import { getBenchmarkLeaderboard } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function BenchmarkLeaderboardDetailPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const leaderboard = await getBenchmarkLeaderboard(id, projectId).catch(() => null);

  if (!leaderboard) {
    notFound();
  }

  return <BenchmarkLeaderboardDetailPanel initialLeaderboard={leaderboard} />;
}
