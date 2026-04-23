import { CURRENT_PROJECT_COOKIE, CURRENT_PROJECT_HEADER } from "@/features/project/constants";
import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  BronzeArtifactSignedUrl,
  BronzeAssetDetail,
  BronzeAssetPatchInput,
  BronzeAssetSummary,
  BronzeImportCreateInput,
  BronzeImportCreateResponse,
  BronzeJobSummary,
  BronzeSnapshotSummary,
  LakeAssetDirectUploadInitInput,
  LakeAssetDirectUploadInitResponse,
  LakeAssetSummary,
  LakeBatchCreateInput,
  LakeBatchSummary,
  ObjectStoreUploadResponse
} from "@/types/api";

export async function getLakeBatches(projectId?: string | null): Promise<LakeBatchSummary[]> {
  return apiFetch<LakeBatchSummary[]>("/lake/batches", { projectId });
}

export async function getLakeAssets(
  params?: { stage?: string; projectId?: string | null }
): Promise<LakeAssetSummary[]> {
  const query = new URLSearchParams();
  if (params?.stage) {
    query.set("stage", params.stage);
  }
  const suffix = query.size ? `?${query.toString()}` : "";
  return apiFetch<LakeAssetSummary[]>(`/lake/assets${suffix}`, { projectId: params?.projectId });
}

export async function createLakeBatch(payload: LakeBatchCreateInput): Promise<LakeBatchSummary> {
  return apiFetch<LakeBatchSummary>("/lake/batches", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function prepareLakeAssetDirectUpload(
  payload: LakeAssetDirectUploadInitInput
): Promise<LakeAssetDirectUploadInitResponse> {
  return apiFetch<LakeAssetDirectUploadInitResponse>("/lake/assets/direct-upload/init", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function completeLakeAssetDirectUpload(
  assetId: string,
  payload: { upload: ObjectStoreUploadResponse }
): Promise<LakeAssetSummary> {
  return apiFetch<LakeAssetSummary>(`/lake/assets/${assetId}/direct-upload/complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function failLakeAssetDirectUpload(
  assetId: string,
  payload: { reason?: string | null }
): Promise<void> {
  await apiFetch<void>(`/lake/assets/${assetId}/direct-upload/fail`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function deleteLakeAsset(assetId: string): Promise<void> {
  await apiFetch<void>(`/lake/assets/${assetId}`, {
    method: "DELETE"
  });
}

export async function createBronzeImport(
  payload: BronzeImportCreateInput
): Promise<BronzeImportCreateResponse> {
  return apiFetch<BronzeImportCreateResponse>("/bronze/imports", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function getBronzeAssets(projectId?: string | null): Promise<BronzeAssetSummary[]> {
  return apiFetch<BronzeAssetSummary[]>("/bronze/assets", { projectId });
}

export async function getBronzeAsset(
  assetId: string,
  projectId?: string | null
): Promise<BronzeAssetDetail> {
  return apiFetch<BronzeAssetDetail>(`/bronze/assets/${assetId}`, { projectId });
}

export async function updateBronzeAsset(
  assetId: string,
  payload: BronzeAssetPatchInput
): Promise<BronzeAssetDetail> {
  return apiFetch<BronzeAssetDetail>(`/bronze/assets/${assetId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function refreshBronzeAsset(assetId: string): Promise<BronzeJobSummary> {
  return apiFetch<BronzeJobSummary>(`/bronze/assets/${assetId}/refresh`, {
    method: "POST"
  });
}

export async function archiveBronzeAsset(assetId: string): Promise<BronzeAssetDetail> {
  return apiFetch<BronzeAssetDetail>(`/bronze/assets/${assetId}/archive`, {
    method: "POST"
  });
}

export async function deleteBronzeAsset(assetId: string): Promise<void> {
  await apiFetch<void>(`/bronze/assets/${assetId}`, {
    method: "DELETE"
  });
}

export async function getBronzeAssetSnapshots(
  assetId: string,
  projectId?: string | null
): Promise<BronzeSnapshotSummary[]> {
  return apiFetch<BronzeSnapshotSummary[]>(`/bronze/assets/${assetId}/snapshots`, {
    projectId
  });
}

export async function getBronzeJobs(projectId?: string | null): Promise<BronzeJobSummary[]> {
  return apiFetch<BronzeJobSummary[]>("/bronze/jobs", { projectId });
}

export async function cancelBronzeJob(jobId: string): Promise<BronzeJobSummary> {
  return apiFetch<BronzeJobSummary>(`/bronze/jobs/${jobId}/cancel`, {
    method: "POST"
  });
}

export async function getBronzeArtifactSignedUrl(
  artifactId: string
): Promise<BronzeArtifactSignedUrl> {
  return apiFetch<BronzeArtifactSignedUrl>(`/bronze/artifacts/${artifactId}/signed-url`);
}

export function abortLakeUploadsKeepalive(payload: {
  batchId?: string | null;
  assetIds: string[];
  reason?: string | null;
}) {
  if (typeof window === "undefined") {
    return;
  }

  const projectId = getBrowserProjectId();
  void fetch(`${getApiBaseUrl()}/lake/uploads/abort`, {
    method: "POST",
    credentials: "include",
    keepalive: true,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(projectId ? { [CURRENT_PROJECT_HEADER]: projectId } : {})
    },
    body: JSON.stringify({
      batch_id: payload.batchId ?? null,
      asset_ids: payload.assetIds,
      reason: payload.reason ?? null
    })
  });
}

function getBrowserProjectId() {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${CURRENT_PROJECT_COOKIE}=`;
  for (const entry of document.cookie.split(";")) {
    const trimmed = entry.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }

  return null;
}
