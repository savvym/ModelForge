import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  BenchmarkLeaderboardAddJobsInput,
  BenchmarkLeaderboardDetail,
  BenchmarkLeaderboardJobCandidate,
  BenchmarkLeaderboardSummary,
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
  ObjectStoreObjectPreviewResponse
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

export async function getBenchmarkLeaderboards(
  projectId?: string | null
): Promise<BenchmarkLeaderboardSummary[]> {
  return apiFetch<BenchmarkLeaderboardSummary[]>("/benchmark-leaderboards", { projectId });
}

export async function getBenchmarkLeaderboard(
  leaderboardId: string,
  projectId?: string | null
): Promise<BenchmarkLeaderboardDetail> {
  return apiFetch<BenchmarkLeaderboardDetail>(`/benchmark-leaderboards/${leaderboardId}`, {
    projectId
  });
}

export async function getAvailableBenchmarkLeaderboardJobs(
  params: {
    benchmarkName: string;
    benchmarkVersionId: string;
    excludeLeaderboardId?: string | null;
  },
  projectId?: string | null
): Promise<BenchmarkLeaderboardJobCandidate[]> {
  const searchParams = new URLSearchParams();
  searchParams.set("benchmark_name", params.benchmarkName);
  searchParams.set("benchmark_version_id", params.benchmarkVersionId);
  if (params.excludeLeaderboardId) {
    searchParams.set("exclude_leaderboard_id", params.excludeLeaderboardId);
  }
  return apiFetch<BenchmarkLeaderboardJobCandidate[]>(
    `/benchmark-leaderboards/available-jobs?${searchParams.toString()}`,
    { projectId }
  );
}

export async function createBenchmarkLeaderboard(
  payload: {
    name: string;
    benchmark_name: string;
    benchmark_version_id: string;
    eval_job_ids?: string[];
  }
): Promise<BenchmarkLeaderboardSummary> {
  return apiFetch<BenchmarkLeaderboardSummary>("/benchmark-leaderboards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function addBenchmarkLeaderboardJobs(
  leaderboardId: string,
  payload: BenchmarkLeaderboardAddJobsInput
): Promise<BenchmarkLeaderboardDetail> {
  return apiFetch<BenchmarkLeaderboardDetail>(`/benchmark-leaderboards/${leaderboardId}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function removeBenchmarkLeaderboardJob(
  leaderboardId: string,
  evalJobId: string
): Promise<void> {
  return apiFetch<void>(
    `/benchmark-leaderboards/${leaderboardId}/jobs/${encodeURIComponent(evalJobId)}`,
    {
      method: "DELETE"
    }
  );
}

export async function deleteBenchmarkLeaderboard(
  leaderboardId: string
): Promise<void> {
  return apiFetch<void>(`/benchmark-leaderboards/${leaderboardId}`, {
    method: "DELETE"
  });
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
