import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  BenchmarkEvaluationRunCreateInputV2,
  BenchmarkDefinitionCreateInput,
  BenchmarkDefinitionDetail,
  BenchmarkDefinitionSummary,
  BenchmarkDefinitionUpdateInput,
  BenchmarkVersionCreateInput,
  EvalJobCreateInput,
  EvalJobDetail,
  EvalJobSummary,
  EvalTemplateCreateInput,
  EvalTemplateSummary,
  EvalTemplateUpdateInput,
  BenchmarkVersionSummary,
  BenchmarkVersionUpdateInput,
  ObjectStoreObjectPreviewResponse,
  ProbeSummary,
  ProbeTaskCreateInput,
  ProbeTaskDetail,
  ProbeTaskSummary,
  EvaluationCatalogResponseV2,
  EvaluationLeaderboardAddRunsInputV2,
  EvaluationLeaderboardCreateInputV2,
  EvaluationLeaderboardDetailV2,
  EvaluationLeaderboardRunCandidateV2,
  EvaluationLeaderboardSummaryV2,
  EvaluationRunCancelResponseV2,
  EvaluationRunCreateInputV2,
  EvaluationRunDetailV2,
  EvaluationRunSummaryV2,
  EvalSpecCreateInputV2,
  EvalSpecUpdateInputV2,
  EvalSpecSummaryV2,
  EvalSuiteCreateInputV2,
  EvalSuiteUpdateInputV2,
  EvalSuiteSummaryV2,
  JudgePolicyCreateInputV2,
  JudgePolicySummaryV2,
  TemplateSpecCreateInputV2,
  TemplateSpecSummaryV2
} from "@/types/api";

export async function getEvalJobs(projectId?: string | null): Promise<EvalJobSummary[]> {
  return apiFetch<EvalJobSummary[]>("/eval-jobs", { projectId });
}

export async function getEvalJob(
  jobId: string,
  projectId?: string | null
): Promise<EvalJobDetail> {
  return apiFetch<EvalJobDetail>(`/eval-jobs/${jobId}`, { projectId });
}

export async function createEvalJob(payload: EvalJobCreateInput): Promise<EvalJobSummary> {
  return apiFetch<EvalJobSummary>("/eval-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteEvalJob(jobId: string): Promise<void> {
  return apiFetch<void>(`/eval-jobs/${jobId}`, {
    method: "DELETE"
  });
}

export async function stopEvalJob(jobId: string): Promise<EvalJobSummary> {
  return apiFetch<EvalJobSummary>(`/eval-jobs/${jobId}/stop`, {
    method: "POST"
  });
}

export async function getBenchmarkCatalog(
  projectId?: string | null
): Promise<BenchmarkDefinitionSummary[]> {
  return apiFetch<BenchmarkDefinitionSummary[]>("/benchmarks", { projectId });
}

export async function getBenchmark(
  benchmarkName: string,
  projectId?: string | null
): Promise<BenchmarkDefinitionDetail> {
  return apiFetch<BenchmarkDefinitionDetail>(`/benchmarks/${benchmarkName}`, { projectId });
}

export async function createBenchmarkDefinition(
  payload: BenchmarkDefinitionCreateInput
): Promise<BenchmarkDefinitionSummary> {
  return apiFetch<BenchmarkDefinitionSummary>("/benchmarks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateBenchmarkDefinition(
  benchmarkName: string,
  payload: BenchmarkDefinitionUpdateInput
): Promise<BenchmarkDefinitionSummary> {
  return apiFetch<BenchmarkDefinitionSummary>(`/benchmarks/${benchmarkName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function getBenchmarkSampleFileUrl(benchmarkName: string): string {
  return `${getApiBaseUrl()}/benchmarks/${encodeURIComponent(benchmarkName)}/sample-file`;
}

export async function createBenchmarkVersion(
  benchmarkName: string,
  payload: BenchmarkVersionCreateInput
): Promise<BenchmarkVersionSummary> {
  return apiFetch<BenchmarkVersionSummary>(`/benchmarks/${benchmarkName}/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateBenchmarkVersion(
  benchmarkName: string,
  versionId: string,
  payload: BenchmarkVersionUpdateInput
): Promise<BenchmarkVersionSummary> {
  return apiFetch<BenchmarkVersionSummary>(`/benchmarks/${benchmarkName}/versions/${versionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteBenchmarkVersion(
  benchmarkName: string,
  versionId: string
): Promise<void> {
  await apiFetch<void>(`/benchmarks/${benchmarkName}/versions/${versionId}`, {
    method: "DELETE"
  });
}

export async function getBenchmarkVersionPreview(
  benchmarkName: string,
  versionId: string
): Promise<ObjectStoreObjectPreviewResponse> {
  return apiFetch<ObjectStoreObjectPreviewResponse>(
    `/benchmarks/${benchmarkName}/versions/${versionId}/preview`
  );
}

export function getBenchmarkVersionDownloadUrl(
  benchmarkName: string,
  versionId: string
): string {
  return `${getApiBaseUrl()}/benchmarks/${encodeURIComponent(benchmarkName)}/versions/${encodeURIComponent(versionId)}/download`;
}

// -- Eval Templates --

export async function getEvalTemplates(): Promise<EvalTemplateSummary[]> {
  return apiFetch<EvalTemplateSummary[]>("/eval-templates");
}

export async function getEvalTemplate(
  name: string,
  version?: number
): Promise<EvalTemplateSummary> {
  const params = version != null ? `?version=${version}` : "";
  return apiFetch<EvalTemplateSummary>(`/eval-templates/${name}${params}`);
}

export async function getEvalTemplateVersions(
  name: string
): Promise<EvalTemplateSummary[]> {
  return apiFetch<EvalTemplateSummary[]>(`/eval-templates/${name}/versions`);
}

export async function createEvalTemplate(
  payload: EvalTemplateCreateInput
): Promise<EvalTemplateSummary> {
  return apiFetch<EvalTemplateSummary>("/eval-templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateEvalTemplate(
  name: string,
  payload: EvalTemplateUpdateInput
): Promise<EvalTemplateSummary> {
  return apiFetch<EvalTemplateSummary>(`/eval-templates/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// -- Probes --

export async function getProbes(
  projectId?: string | null
): Promise<ProbeSummary[]> {
  return apiFetch<ProbeSummary[]>("/api/v2/probes", { projectId });
}

export async function getProbeTasks(
  projectId?: string | null,
  options?: {
    probeId?: string | null;
    status?: string | null;
  }
): Promise<ProbeTaskSummary[]> {
  const params = new URLSearchParams();
  if (options?.probeId) {
    params.set("probe_id", options.probeId);
  }
  if (options?.status) {
    params.set("status", options.status);
  }
  const query = params.toString();
  return apiFetch<ProbeTaskSummary[]>(`/api/v2/probe-tasks${query ? `?${query}` : ""}`, {
    projectId
  });
}

export async function createProbeTask(
  payload: ProbeTaskCreateInput
): Promise<ProbeTaskDetail> {
  return apiFetch<ProbeTaskDetail>("/api/v2/probe-tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// -- Evaluation V2 --

export async function getEvaluationCatalog(
  projectId?: string | null
): Promise<EvaluationCatalogResponseV2> {
  return apiFetch<EvaluationCatalogResponseV2>("/api/v2/evaluation-catalog", { projectId });
}

export async function getEvaluationSpec(
  name: string,
  projectId?: string | null
): Promise<EvalSpecSummaryV2> {
  return apiFetch<EvalSpecSummaryV2>(`/api/v2/evaluation-catalog/specs/${encodeURIComponent(name)}`, {
    projectId
  });
}

export async function getEvaluationSuite(
  name: string,
  projectId?: string | null
): Promise<EvalSuiteSummaryV2> {
  return apiFetch<EvalSuiteSummaryV2>(`/api/v2/evaluation-catalog/suites/${encodeURIComponent(name)}`, {
    projectId
  });
}

export async function getEvaluationRuns(
  projectId?: string | null
): Promise<EvaluationRunSummaryV2[]> {
  return apiFetch<EvaluationRunSummaryV2[]>("/api/v2/evaluation-runs", { projectId });
}

export async function getEvaluationRun(
  runId: string,
  projectId?: string | null
): Promise<EvaluationRunDetailV2> {
  return apiFetch<EvaluationRunDetailV2>(`/api/v2/evaluation-runs/${runId}`, { projectId });
}

export async function createEvaluationRun(
  payload: EvaluationRunCreateInputV2
): Promise<EvaluationRunSummaryV2> {
  return apiFetch<EvaluationRunSummaryV2>("/api/v2/evaluation-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function createBenchmarkEvaluationRun(
  payload: BenchmarkEvaluationRunCreateInputV2
): Promise<EvaluationRunSummaryV2> {
  return apiFetch<EvaluationRunSummaryV2>("/api/v2/evaluation-runs/benchmark", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function cancelEvaluationRun(
  runId: string
): Promise<EvaluationRunCancelResponseV2> {
  return apiFetch<EvaluationRunCancelResponseV2>(`/api/v2/evaluation-runs/${runId}/cancel`, {
    method: "POST"
  });
}

export async function deleteEvaluationRun(runId: string): Promise<void> {
  return apiFetch<void>(`/api/v2/evaluation-runs/${runId}`, {
    method: "DELETE"
  });
}

export async function getEvaluationLeaderboards(
  projectId?: string | null
): Promise<EvaluationLeaderboardSummaryV2[]> {
  return apiFetch<EvaluationLeaderboardSummaryV2[]>("/api/v2/evaluation-leaderboards", {
    projectId
  });
}

export async function getEvaluationLeaderboard(
  leaderboardId: string,
  projectId?: string | null
): Promise<EvaluationLeaderboardDetailV2> {
  return apiFetch<EvaluationLeaderboardDetailV2>(
    `/api/v2/evaluation-leaderboards/${leaderboardId}`,
    { projectId }
  );
}

export async function getAvailableEvaluationLeaderboardRuns(
  params: {
    kind: "spec" | "suite";
    name: string;
    version: string;
    excludeLeaderboardId?: string | null;
  },
  projectId?: string | null
): Promise<EvaluationLeaderboardRunCandidateV2[]> {
  const searchParams = new URLSearchParams();
  searchParams.set("kind", params.kind);
  searchParams.set("name", params.name);
  searchParams.set("version", params.version);
  if (params.excludeLeaderboardId) {
    searchParams.set("exclude_leaderboard_id", params.excludeLeaderboardId);
  }
  return apiFetch<EvaluationLeaderboardRunCandidateV2[]>(
    `/api/v2/evaluation-leaderboards/available-runs?${searchParams.toString()}`,
    { projectId }
  );
}

export async function createEvaluationLeaderboard(
  payload: EvaluationLeaderboardCreateInputV2
): Promise<EvaluationLeaderboardSummaryV2> {
  return apiFetch<EvaluationLeaderboardSummaryV2>("/api/v2/evaluation-leaderboards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function addEvaluationLeaderboardRuns(
  leaderboardId: string,
  payload: EvaluationLeaderboardAddRunsInputV2
): Promise<EvaluationLeaderboardDetailV2> {
  return apiFetch<EvaluationLeaderboardDetailV2>(
    `/api/v2/evaluation-leaderboards/${leaderboardId}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }
  );
}

export async function removeEvaluationLeaderboardRun(
  leaderboardId: string,
  runId: string
): Promise<void> {
  return apiFetch<void>(
    `/api/v2/evaluation-leaderboards/${leaderboardId}/runs/${encodeURIComponent(runId)}`,
    {
      method: "DELETE"
    }
  );
}

export async function deleteEvaluationLeaderboard(
  leaderboardId: string
): Promise<void> {
  return apiFetch<void>(`/api/v2/evaluation-leaderboards/${leaderboardId}`, {
    method: "DELETE"
  });
}

export async function createTemplateSpec(
  payload: TemplateSpecCreateInputV2
): Promise<TemplateSpecSummaryV2> {
  return apiFetch<TemplateSpecSummaryV2>("/api/v2/evaluation-catalog/templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function createEvalSpec(
  payload: EvalSpecCreateInputV2
): Promise<EvalSpecSummaryV2> {
  return apiFetch<EvalSpecSummaryV2>("/api/v2/evaluation-catalog/specs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateEvalSpec(
  name: string,
  payload: EvalSpecUpdateInputV2
): Promise<EvalSpecSummaryV2> {
  return apiFetch<EvalSpecSummaryV2>(`/api/v2/evaluation-catalog/specs/${encodeURIComponent(name)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteEvalSpec(name: string): Promise<void> {
  return apiFetch<void>(`/api/v2/evaluation-catalog/specs/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

export async function syncEvalSpecVersionDatasets(
  name: string,
  versionId: string
): Promise<EvalSpecSummaryV2> {
  return apiFetch<EvalSpecSummaryV2>(
    `/api/v2/evaluation-catalog/specs/${encodeURIComponent(name)}/versions/${encodeURIComponent(versionId)}/sync-datasets`,
    {
      method: "POST"
    }
  );
}

export async function createEvalSuite(
  payload: EvalSuiteCreateInputV2
): Promise<EvalSuiteSummaryV2> {
  return apiFetch<EvalSuiteSummaryV2>("/api/v2/evaluation-catalog/suites", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateEvalSuite(
  name: string,
  payload: EvalSuiteUpdateInputV2
): Promise<EvalSuiteSummaryV2> {
  return apiFetch<EvalSuiteSummaryV2>(`/api/v2/evaluation-catalog/suites/${encodeURIComponent(name)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteEvalSuite(name: string): Promise<void> {
  return apiFetch<void>(`/api/v2/evaluation-catalog/suites/${encodeURIComponent(name)}`, {
    method: "DELETE"
  });
}

export async function createJudgePolicy(
  payload: JudgePolicyCreateInputV2
): Promise<JudgePolicySummaryV2> {
  return apiFetch<JudgePolicySummaryV2>("/api/v2/evaluation-catalog/judge-policies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
