import { apiFetch } from "@/lib/api-client/http";
import type {
  RegistryModelChatInput,
  RegistryModelChatResponse,
  ModelProviderCreateInput,
  ModelProviderSummary,
  ModelProviderSyncResult,
  ModelProviderUpdateInput,
  RegistryModelCreateInput,
  RegistryModelSummary,
  RegistryModelTestInput,
  RegistryModelTestResponse,
  RegistryModelUpdateInput
} from "@/types/api";

export async function getModelProviders(
  projectId?: string | null
): Promise<ModelProviderSummary[]> {
  return apiFetch<ModelProviderSummary[]>("/model-providers", { projectId });
}

export async function getModelProvider(
  providerId: string,
  projectId?: string | null
): Promise<ModelProviderSummary> {
  return apiFetch<ModelProviderSummary>(`/model-providers/${providerId}`, { projectId });
}

export async function createModelProvider(
  payload: ModelProviderCreateInput
): Promise<ModelProviderSummary> {
  return apiFetch<ModelProviderSummary>("/model-providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateModelProvider(
  providerId: string,
  payload: ModelProviderUpdateInput
): Promise<ModelProviderSummary> {
  return apiFetch<ModelProviderSummary>(`/model-providers/${providerId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteModelProvider(providerId: string): Promise<void> {
  return apiFetch<void>(`/model-providers/${providerId}`, {
    method: "DELETE"
  });
}

export async function syncModelProvider(providerId: string): Promise<ModelProviderSyncResult> {
  return apiFetch<ModelProviderSyncResult>(`/model-providers/${providerId}/sync-models`, {
    method: "POST"
  });
}

export async function getRegistryModels(
  projectId?: string | null
): Promise<RegistryModelSummary[]> {
  return apiFetch<RegistryModelSummary[]>("/models", { projectId });
}

export async function getRegistryModel(
  modelId: string,
  projectId?: string | null
): Promise<RegistryModelSummary> {
  return apiFetch<RegistryModelSummary>(`/models/${modelId}`, { projectId });
}

export async function createRegistryModel(
  payload: RegistryModelCreateInput
): Promise<RegistryModelSummary> {
  return apiFetch<RegistryModelSummary>("/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function updateRegistryModel(
  modelId: string,
  payload: RegistryModelUpdateInput
): Promise<RegistryModelSummary> {
  return apiFetch<RegistryModelSummary>(`/models/${modelId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteRegistryModel(modelId: string): Promise<void> {
  return apiFetch<void>(`/models/${modelId}`, {
    method: "DELETE"
  });
}

export async function testRegistryModel(
  modelId: string,
  payload: RegistryModelTestInput
): Promise<RegistryModelTestResponse> {
  return apiFetch<RegistryModelTestResponse>(`/models/${modelId}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function chatRegistryModel(
  modelId: string,
  payload: RegistryModelChatInput
): Promise<RegistryModelChatResponse> {
  return apiFetch<RegistryModelChatResponse>(`/models/${modelId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}
