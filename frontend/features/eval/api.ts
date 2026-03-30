import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  BenchmarkDefinitionCreateInput,
  BenchmarkDefinitionDetail,
  BenchmarkDefinitionSummary,
  BenchmarkVersionCreateInput,
  CollectionRunInput,
  CollectionRunResponse,
  EvalCollectionCreateInput,
  EvalCollectionDetail,
  EvalCollectionSummary,
  EvalJobCreateInput,
  EvalJobDetail,
  EvalJobSummary,
  BenchmarkVersionSummary,
  BenchmarkVersionUpdateInput
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

// -- Eval Collections --

export async function getEvalCollections(): Promise<EvalCollectionSummary[]> {
  return apiFetch<EvalCollectionSummary[]>("/eval-collections");
}

export async function getEvalCollection(collectionId: string): Promise<EvalCollectionDetail> {
  return apiFetch<EvalCollectionDetail>(`/eval-collections/${collectionId}`);
}

export async function createEvalCollection(
  payload: EvalCollectionCreateInput
): Promise<EvalCollectionSummary> {
  return apiFetch<EvalCollectionSummary>("/eval-collections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function runEvalCollection(
  collectionId: string,
  payload: CollectionRunInput
): Promise<CollectionRunResponse> {
  return apiFetch<CollectionRunResponse>(`/eval-collections/${collectionId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteEvalCollection(collectionId: string): Promise<void> {
  return apiFetch<void>(`/eval-collections/${collectionId}`, {
    method: "DELETE"
  });
}
