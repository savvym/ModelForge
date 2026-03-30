import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  DatasetCreateInput,
  DatasetCreateResponse,
  DatasetDirectUploadCompleteInput,
  DatasetDirectUploadFailedInput,
  DatasetDirectUploadInitInput,
  DatasetDirectUploadInitResponse,
  DatasetDetail,
  DatasetSummary
} from "@/types/api";
import type {
  DatasetVersionCreateInput,
  DatasetVersionDirectUploadInitInput,
  DatasetVersionPreview
} from "@/types/api";

async function parseActionError(response: Response): Promise<Error> {
  const fallback = `API request failed: ${response.status} ${response.statusText}`;

  try {
    const payload = (await response.json()) as { detail?: string | null };
    return new Error(payload.detail ? `${fallback} - ${payload.detail}` : fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function getDatasets(
  scope?: string,
  projectId?: string | null
): Promise<DatasetSummary[]> {
  const query = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  return apiFetch<DatasetSummary[]>(`/datasets${query}`, { projectId });
}

export async function getDataset(
  datasetId: string,
  projectId?: string | null
): Promise<DatasetDetail> {
  return apiFetch<DatasetDetail>(`/datasets/${datasetId}`, { projectId });
}

export async function getDatasetVersionPreview(
  datasetId: string,
  versionId: string,
  fileId?: string,
  projectId?: string | null
): Promise<DatasetVersionPreview> {
  const query = fileId ? `?file_id=${encodeURIComponent(fileId)}` : "";
  return apiFetch<DatasetVersionPreview>(
    `/datasets/${datasetId}/versions/${versionId}/preview${query}`,
    { projectId }
  );
}

export async function createDataset(
  payload: DatasetCreateInput
): Promise<DatasetCreateResponse> {
  return apiFetch<DatasetCreateResponse>("/datasets", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function prepareDatasetDirectUpload(
  payload: DatasetDirectUploadInitInput
): Promise<DatasetDirectUploadInitResponse> {
  return apiFetch<DatasetDirectUploadInitResponse>("/datasets/direct-upload/init", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function createDatasetUpload(formData: FormData): Promise<DatasetCreateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/datasets/upload`, {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  if (!response.ok) {
    throw await parseActionError(response);
  }

  return response.json() as Promise<DatasetCreateResponse>;
}

export async function createDatasetVersion(
  datasetId: string,
  payload: DatasetVersionCreateInput
): Promise<DatasetCreateResponse> {
  return apiFetch<DatasetCreateResponse>(`/datasets/${datasetId}/versions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function prepareDatasetVersionDirectUpload(
  datasetId: string,
  payload: DatasetVersionDirectUploadInitInput
): Promise<DatasetDirectUploadInitResponse> {
  return apiFetch<DatasetDirectUploadInitResponse>(
    `/datasets/${datasetId}/versions/direct-upload/init`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function createDatasetVersionUpload(
  datasetId: string,
  formData: FormData
): Promise<DatasetCreateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/datasets/${datasetId}/versions/upload`, {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  if (!response.ok) {
    throw await parseActionError(response);
  }

  return response.json() as Promise<DatasetCreateResponse>;
}

export async function completeDatasetDirectUpload(
  datasetId: string,
  versionId: string,
  payload: DatasetDirectUploadCompleteInput
): Promise<DatasetCreateResponse> {
  return apiFetch<DatasetCreateResponse>(
    `/datasets/${datasetId}/versions/${versionId}/direct-upload/complete`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function failDatasetDirectUpload(
  datasetId: string,
  versionId: string,
  payload: DatasetDirectUploadFailedInput
): Promise<void> {
  await apiFetch<void>(`/datasets/${datasetId}/versions/${versionId}/direct-upload/fail`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function deleteDataset(datasetId: string): Promise<void> {
  await apiFetch(`/datasets/${datasetId}`, {
    method: "DELETE"
  });
}

export async function deleteDatasetVersion(datasetId: string, versionId: string): Promise<void> {
  await apiFetch(`/datasets/${datasetId}/versions/${versionId}`, {
    method: "DELETE"
  });
}

export function getDatasetVersionDownloadUrl(
  datasetId: string,
  versionId: string,
  fileId?: string
): string {
  const query = fileId ? `?file_id=${encodeURIComponent(fileId)}` : "";
  return `${getApiBaseUrl()}/datasets/${datasetId}/versions/${versionId}/download${query}`;
}
