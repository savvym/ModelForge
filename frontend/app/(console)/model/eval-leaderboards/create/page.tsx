import { BenchmarkLeaderboardCreateForm } from "@/features/eval/components/benchmark-leaderboard-create-form";
import { getBenchmarkCatalog } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateBenchmarkLeaderboardPage({
  searchParams
}: {
  searchParams: Promise<{ benchmark?: string; version?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const benchmarks = await getBenchmarkCatalog(projectId).catch(() => []);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold">创建排行榜</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          先绑定一个 Benchmark Version，再把已完成且有得分的评测任务纳入排行榜，形成同一标准下的模型排序。
        </p>
      </div>

      <BenchmarkLeaderboardCreateForm
        benchmarks={benchmarks}
        initialBenchmarkName={resolvedSearchParams.benchmark ?? null}
        initialVersionId={resolvedSearchParams.version ?? null}
      />
    </div>
  );
}
