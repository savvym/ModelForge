import { apiFetch } from "@/lib/api-client/http";
import type {
  DeployModelInput,
  InferenceMachineCreateInput,
  InferenceMachineHealth,
  InferenceMachineSummary,
  ModelDeploymentEvent,
  ModelDeploymentSummary,
  RegistryModelSummary
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

export async function publishDeploymentToExperience(
  deploymentId: string
): Promise<RegistryModelSummary> {
  return apiFetch<RegistryModelSummary>(`/model-deployments/${deploymentId}/publish`, {
    method: "POST"
  });
}

export async function getModelDeploymentEvents(
  deploymentId: string
): Promise<ModelDeploymentEvent[]> {
  return apiFetch<ModelDeploymentEvent[]>(`/model-deployments/${deploymentId}/events`);
}

export async function getInferenceMachines(
  projectId?: string | null
): Promise<InferenceMachineSummary[]> {
  return apiFetch<InferenceMachineSummary[]>("/model-deployments/machines", { projectId });
}

export async function createInferenceMachine(
  payload: InferenceMachineCreateInput
): Promise<InferenceMachineSummary> {
  return apiFetch<InferenceMachineSummary>("/model-deployments/machines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function deleteInferenceMachine(machineId: string): Promise<void> {
  return apiFetch<void>(`/model-deployments/machines/${machineId}`, {
    method: "DELETE"
  });
}

export async function checkInferenceMachineHealth(
  machineId: string
): Promise<InferenceMachineHealth> {
  return apiFetch<InferenceMachineHealth>(`/model-deployments/machines/${machineId}/health`, {
    method: "POST"
  });
}
