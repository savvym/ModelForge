import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  ObjectStoreBrowserResponse,
  ObjectStoreDirectUploadInitResponse,
  ObjectStoreFolderCreateResponse,
  ObjectStoreObjectPreviewResponse,
  ObjectStoreUploadResponse
} from "@/types/api";

export async function browseObjectStore(params?: {
  bucket?: string;
  prefix?: string;
  q?: string;
}): Promise<ObjectStoreBrowserResponse> {
  const query = new URLSearchParams();
  if (params?.bucket) {
    query.set("bucket", params.bucket);
  }
  if (params?.prefix) {
    query.set("prefix", params.prefix);
  }
  if (params?.q?.trim()) {
    query.set("q", params.q.trim());
  }

  const suffix = query.size ? `?${query.toString()}` : "";
  return apiFetch<ObjectStoreBrowserResponse>(`/uploads/browser${suffix}`);
}

async function parseActionError(response: Response): Promise<Error> {
  const fallback = `API request failed: ${response.status} ${response.statusText}`;

  try {
    const payload = (await response.json()) as { detail?: string | null };
    return new Error(payload.detail ? `${fallback} - ${payload.detail}` : fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function uploadManagedFile(payload: {
  file: File;
  bucket?: string;
  prefix?: string;
  relativePath?: string;
}): Promise<ObjectStoreUploadResponse> {
  const formData = new FormData();
  formData.set("file", payload.file);
  if (payload.bucket) {
    formData.set("bucket", payload.bucket);
  }
  if (payload.prefix) {
    formData.set("prefix", payload.prefix);
  }
  if (payload.relativePath) {
    formData.set("relative_path", payload.relativePath);
  }

  const response = await fetch(`${getApiBaseUrl()}/uploads/files`, {
    method: "POST",
    body: formData,
    credentials: "include"
  });

  if (!response.ok) {
    throw await parseActionError(response);
  }

  return response.json() as Promise<ObjectStoreUploadResponse>;
}

export function initiateDirectUpload(payload: {
  bucket?: string;
  prefix?: string;
  fileName: string;
  fileSize: number;
  contentType?: string | null;
  relativePath?: string | null;
}) {
  return apiFetch<ObjectStoreDirectUploadInitResponse>("/uploads/files/direct/init", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      bucket: payload.bucket,
      prefix: payload.prefix,
      file_name: payload.fileName,
      file_size: payload.fileSize,
      content_type: payload.contentType,
      relative_path: payload.relativePath
    })
  });
}

export async function createManagedFolder(payload: {
  name: string;
  bucket?: string;
  prefix?: string;
}): Promise<ObjectStoreFolderCreateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/uploads/folders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    credentials: "include"
  });

  if (!response.ok) {
    throw await parseActionError(response);
  }

  return response.json() as Promise<ObjectStoreFolderCreateResponse>;
}

export async function deleteObjectStoreObject(params: {
  bucket: string;
  key: string;
}): Promise<void> {
  const query = new URLSearchParams();
  query.set("bucket", params.bucket);
  query.set("key", params.key);
  await apiFetch(`/uploads/object?${query.toString()}`, {
    method: "DELETE"
  });
}

export async function deleteObjectStorePrefix(params: {
  bucket: string;
  prefix: string;
}): Promise<void> {
  const query = new URLSearchParams();
  query.set("bucket", params.bucket);
  query.set("prefix", params.prefix);
  await apiFetch(`/uploads/prefix?${query.toString()}`, {
    method: "DELETE"
  });
}

export function getObjectStoreDownloadUrl(params: {
  bucket: string;
  key: string;
  disposition?: "attachment" | "inline";
}): string {
  const query = new URLSearchParams();
  query.set("bucket", params.bucket);
  query.set("key", params.key);
  if (params.disposition) {
    query.set("disposition", params.disposition);
  }
  return `${getApiBaseUrl()}/uploads/object/download?${query.toString()}`;
}

export function getObjectStoreObjectPreview(params: {
  bucket: string;
  key: string;
}) {
  const query = new URLSearchParams();
  query.set("bucket", params.bucket);
  query.set("key", params.key);
  return apiFetch<ObjectStoreObjectPreviewResponse>(`/uploads/object/preview?${query.toString()}`);
}

export function updateObjectStoreTextFile(payload: {
  bucket: string;
  objectKey: string;
  content: string;
  contentType?: string | null;
}) {
  return apiFetch<ObjectStoreUploadResponse>("/uploads/object/text", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      bucket: payload.bucket,
      object_key: payload.objectKey,
      content: payload.content,
      content_type: payload.contentType
    })
  });
}
