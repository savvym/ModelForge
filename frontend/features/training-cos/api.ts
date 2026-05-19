import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
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
