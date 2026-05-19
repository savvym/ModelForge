import { apiFetch, getApiBaseUrl } from "@/lib/api-client/http";
import type {
  LakeBatchUploadRequest,
  LakeBatchUploadResponse,
  LakeBranchSummary,
  LakeCommitListResponse,
  LakeFileResponse,
  LakeRepoCreateInput,
  LakeRepoDetail,
  LakeRepoListResponse,
  LakeRepoSummary,
  LakeRepoUpdateInput,
  LakeTreeResponse
} from "@/types/api";

export async function listRepos(
  params: { query?: string; page?: number; pageSize?: number } = {},
  projectId?: string | null
): Promise<LakeRepoListResponse> {
  const qs = new URLSearchParams();
  if (params.query) qs.set("query", params.query);
  if (params.page) qs.set("page", String(params.page));
  if (params.pageSize) qs.set("page_size", String(params.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<LakeRepoListResponse>(`/data-lake/repos${suffix}`, { projectId });
}

export async function getRepo(
  repoId: string,
  projectId?: string | null
): Promise<LakeRepoDetail> {
  return apiFetch<LakeRepoDetail>(`/data-lake/repos/${repoId}`, { projectId });
}

export async function createRepo(
  payload: LakeRepoCreateInput,
  projectId?: string | null
): Promise<LakeRepoSummary> {
  return apiFetch<LakeRepoSummary>(`/data-lake/repos`, {
    projectId,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateRepo(
  repoId: string,
  payload: LakeRepoUpdateInput,
  projectId?: string | null
): Promise<LakeRepoSummary> {
  return apiFetch<LakeRepoSummary>(`/data-lake/repos/${repoId}`, {
    projectId,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteRepo(repoId: string, projectId?: string | null): Promise<void> {
  await apiFetch<void>(`/data-lake/repos/${repoId}`, {
    projectId,
    method: "DELETE"
  });
}

export async function listBranches(
  repoId: string,
  projectId?: string | null
): Promise<LakeBranchSummary[]> {
  return apiFetch<LakeBranchSummary[]>(`/data-lake/repos/${repoId}/branches`, { projectId });
}

export async function getTree(
  repoId: string,
  ref: string,
  path: string = "",
  projectId?: string | null
): Promise<LakeTreeResponse> {
  const qs = path ? `?path=${encodeURIComponent(path)}` : "";
  return apiFetch<LakeTreeResponse>(
    `/data-lake/repos/${repoId}/tree/${encodeURIComponent(ref)}${qs}`,
    { projectId }
  );
}

export async function getFile(
  repoId: string,
  ref: string,
  path: string,
  projectId?: string | null
): Promise<LakeFileResponse> {
  const qs = `?path=${encodeURIComponent(path)}`;
  return apiFetch<LakeFileResponse>(
    `/data-lake/repos/${repoId}/file/${encodeURIComponent(ref)}${qs}`,
    { projectId }
  );
}

export async function uploadFiles(
  repoId: string,
  payload: LakeBatchUploadRequest,
  projectId?: string | null
): Promise<LakeBatchUploadResponse> {
  return apiFetch<LakeBatchUploadResponse>(`/data-lake/repos/${repoId}/commits`, {
    projectId,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function listCommits(
  repoId: string,
  ref: string,
  params: { path?: string; page?: number; pageSize?: number } = {},
  projectId?: string | null
): Promise<LakeCommitListResponse> {
  const qs = new URLSearchParams();
  if (params.path) qs.set("path", params.path);
  if (params.page) qs.set("page", String(params.page));
  if (params.pageSize) qs.set("page_size", String(params.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<LakeCommitListResponse>(
    `/data-lake/repos/${repoId}/commits/${encodeURIComponent(ref)}${suffix}`,
    { projectId }
  );
}

export function buildRawDownloadUrl(repoId: string, ref: string, path: string): string {
  const base = getApiBaseUrl().replace(/\/+$/, "");
  const safePath = path
    .split("/")
    .map((seg) => encodeURIComponent(seg))
    .join("/");
  return `${base}/data-lake/repos/${repoId}/raw/${encodeURIComponent(ref)}/${safePath}`;
}
