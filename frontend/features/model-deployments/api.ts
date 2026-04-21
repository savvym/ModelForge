import { apiFetch } from "@/lib/api-client/http";
import type {
  DeployModelInput,
  ModelDeploymentEvent,
  ModelDeploymentSummary
} from "@/types/api";

export async function getModelDeployments(
  projectId?: string | null
): Promise<ModelDeploymentSummary[]> {
  return apiFetch<ModelDeploymentSummary[]>("/model-deployments", { projectId });
}

export async function createDeploymentFromModel(
  modelId: string,
  payload: DeployModelInput = {}
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(`/model-deployments/from-model/${modelId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function refreshModelDeployment(
  deploymentId: string
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(`/model-deployments/${deploymentId}/refresh`, {
    method: "POST"
  });
}

export async function getModelDeploymentEvents(
  deploymentId: string
): Promise<ModelDeploymentEvent[]> {
  return apiFetch<ModelDeploymentEvent[]>(`/model-deployments/${deploymentId}/events`);
}
