import { EvaluationLeaderboardCreateForm } from "@/features/eval/components/evaluation-leaderboard-create-form";
import { getBenchmarkCatalog, getEvaluationCatalog } from "@/features/eval/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateEvaluationLeaderboardPage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const [catalog, benchmarks] = await Promise.all([
    getEvaluationCatalog(projectId).catch(() => ({
      specs: [],
      suites: [],
      templates: [],
      judge_policies: []
    })),
    getBenchmarkCatalog(projectId).catch(() => [])
  ]);

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-[28px] font-semibold tracking-tight text-foreground">创建排行榜</h1>
        <p className="text-sm text-muted-foreground">
          从同一个 Benchmark、spec 或 suite version 的 completed runs 中挑选候选项，建立可持续维护的榜单。
        </p>
      </div>

      <EvaluationLeaderboardCreateForm benchmarks={benchmarks} catalog={catalog} />
    </div>
  );
}
