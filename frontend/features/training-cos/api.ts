import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  TrainingCosHuggingFaceFolderFilesResponse,
  TrainingCosHuggingFaceRepoSearchResponse,
  TrainingCosHuggingFaceRepoType,
  TrainingCosHuggingFaceSyncCreateInput,
  TrainingCosHuggingFaceSyncJob,
  TrainingCosHuggingFaceSyncJobListResponse,
  TrainingCosListResponse,
  TrainingCosPreviewResponse,
  TrainingCosStatus
} from "@/types/api";

export async function getTrainingCosStatus(): Promise<TrainingCosStatus> {
  return apiFetch<TrainingCosStatus>("/training-cos/status");
}

export async function listTrainingCosEntries(params: {
  prefix?: string;
  nextToken?: string;
  pageSize?: number;
}): Promise<TrainingCosListResponse> {
  const qs = new URLSearchParams();
  if (params.prefix) qs.set("prefix", params.prefix);
  if (params.nextToken) qs.set("next_token", params.nextToken);
  if (params.pageSize) qs.set("page_size", String(params.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TrainingCosListResponse>(`/training-cos/entries${suffix}`);
}

export async function previewTrainingCosObject(key: string): Promise<TrainingCosPreviewResponse> {
  return apiFetch<TrainingCosPreviewResponse>(
    `/training-cos/object/preview?key=${encodeURIComponent(key)}`
  );
}

export function buildTrainingCosDownloadUrl(key: string): string {
  const base = getApiBaseUrl().replace(/\/+$/, "");
  return `${base}/training-cos/object/raw?key=${encodeURIComponent(key)}`;
}

export async function searchTrainingCosHuggingFaceRepos(params: {
  query?: string;
  repoType: TrainingCosHuggingFaceRepoType;
  limit?: number;
}): Promise<TrainingCosHuggingFaceRepoSearchResponse> {
  const qs = new URLSearchParams();
  if (params.query) qs.set("query", params.query);
  qs.set("repo_type", params.repoType);
  if (params.limit) qs.set("limit", String(params.limit));
  return apiFetch<TrainingCosHuggingFaceRepoSearchResponse>(
    `/training-cos/huggingface/repos?${qs.toString()}`
  );
}

export async function listTrainingCosHuggingFaceFolderFiles(params: {
  prefix: string;
  limit?: number;
}): Promise<TrainingCosHuggingFaceFolderFilesResponse> {
  const qs = new URLSearchParams();
  qs.set("prefix", params.prefix);
  if (params.limit) qs.set("limit", String(params.limit));
  return apiFetch<TrainingCosHuggingFaceFolderFilesResponse>(
    `/training-cos/huggingface/folder-files?${qs.toString()}`
  );
}

export async function createTrainingCosHuggingFaceSyncJob(
  payload: TrainingCosHuggingFaceSyncCreateInput
): Promise<TrainingCosHuggingFaceSyncJob> {
  return apiFetch<TrainingCosHuggingFaceSyncJob>("/training-cos/huggingface/sync-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function listTrainingCosHuggingFaceSyncJobs(params: {
  prefix?: string;
  limit?: number;
}): Promise<TrainingCosHuggingFaceSyncJobListResponse> {
  const qs = new URLSearchParams();
  if (params.prefix) qs.set("prefix", params.prefix);
  if (params.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TrainingCosHuggingFaceSyncJobListResponse>(
    `/training-cos/huggingface/sync-jobs${suffix}`
  );
}

export async function getTrainingCosHuggingFaceSyncJob(
  jobId: string
): Promise<TrainingCosHuggingFaceSyncJob> {
  return apiFetch<TrainingCosHuggingFaceSyncJob>(
    `/training-cos/huggingface/sync-jobs/${jobId}`
  );
}

export async function retryTrainingCosHuggingFaceSyncJob(
  jobId: string
): Promise<TrainingCosHuggingFaceSyncJob> {
  return apiFetch<TrainingCosHuggingFaceSyncJob>(
    `/training-cos/huggingface/sync-jobs/${jobId}/retry`,
    { method: "POST" }
  );
}
