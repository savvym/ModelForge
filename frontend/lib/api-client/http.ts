import { getBrowserApiBaseUrl } from "@/lib/network/runtime-base";
import { CURRENT_PROJECT_COOKIE, CURRENT_PROJECT_HEADER } from "@/features/project/constants";

export function getApiBaseUrl() {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://127.0.0.1:8081/api/v1"
    );
  }

  return getBrowserApiBaseUrl();
}

export function getApiRootUrl() {
  const baseUrl = getApiBaseUrl().replace(/\/+$/, "");
  if (baseUrl.endsWith("/api/v1")) {
    return baseUrl.slice(0, -"/api/v1".length);
  }
  return baseUrl;
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

const API_DETAIL_MESSAGES: Record<string, string> = {
  "Deployment not found": "部署不存在或已被清理。",
  "Inference machine not found": "推理机器不存在或已被删除。",
  "Model or inference machine not found": "模型或推理机器不存在。"
};

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly statusText: string,
    readonly detail: string | null
  ) {
    super(message);
    this.name = "ApiRequestError";
    Object.setPrototypeOf(this, ApiRequestError.prototype);
  }
}

function formatApiErrorMessage(response: Response, detail: string | null) {
  if (detail) {
    return API_DETAIL_MESSAGES[detail] ?? detail;
  }
  return `请求失败：${response.status} ${response.statusText}`;
}

export async function buildApiError(response: Response): Promise<ApiRequestError> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { detail?: string } | null;
    };
    const detail =
      typeof payload.detail === "string"
        ? payload.detail
        : typeof payload.detail?.detail === "string"
          ? payload.detail.detail
          : null;

    return new ApiRequestError(
      formatApiErrorMessage(response, detail),
      response.status,
      response.statusText,
      detail
    );
  } catch {
    return new ApiRequestError(
      formatApiErrorMessage(response, null),
      response.status,
      response.statusText,
      null
    );
  }
}

type ApiFetchOptions = RequestInit & {
  projectId?: string | null;
};

function resolveApiRequest(path: string, init?: ApiFetchOptions) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const { projectId: explicitProjectId, ...requestInit } = init ?? {};
  const projectId =
    explicitProjectId ?? (typeof window !== "undefined" ? getBrowserProjectId() : null);
  const baseUrl = normalizedPath.startsWith("/api/") ? getApiRootUrl() : getApiBaseUrl();
  return {
    url: `${baseUrl}${normalizedPath}`,
    init: {
      cache: "no-store",
      ...requestInit,
      credentials:
        typeof window !== "undefined" ? "include" : requestInit.credentials,
      headers: {
        Accept: "application/json",
        ...(projectId ? { [CURRENT_PROJECT_HEADER]: projectId } : {}),
        ...(requestInit.headers ?? {})
      }
    } satisfies RequestInit
  };
}

export async function apiFetch<T>(path: string, init?: ApiFetchOptions): Promise<T> {
  const request = resolveApiRequest(path, init);
  const response = await fetch(request.url, request.init);

  if (!response.ok) {
    throw await buildApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiFetchBlob(
  path: string,
  init?: ApiFetchOptions
): Promise<{ blob: Blob; fileName: string | null }> {
  const request = resolveApiRequest(path, init);
  const response = await fetch(request.url, request.init);

  if (!response.ok) {
    throw await buildApiError(response);
  }

  const disposition = response.headers.get("Content-Disposition");
  const fileNameMatch = disposition?.match(/filename=\"([^\"]+)\"/);
  return {
    blob: await response.blob(),
    fileName: fileNameMatch?.[1] ?? null
  };
}
