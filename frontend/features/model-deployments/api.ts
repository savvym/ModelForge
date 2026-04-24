import { apiFetch } from "@/lib/api-client/http";
import type {
  DeployModelInput,
  InferenceMachineCreateInput,
  InferenceMachineHealth,
  InferenceMachineRuntimeMetrics,
  InferenceMachineSummary,
  ModelDeploymentEvent,
  ModelDeploymentPassiveHealth,
  ModelDeploymentSummary
} from "@/types/api";

export async function getModelDeployments(
  projectId?: string | null
): Promise<ModelDeploymentSummary[]> {
  return apiFetch<ModelDeploymentSummary[]>("/model-deployments", { projectId });
}

export async function getMyDeployments(
  projectId?: string | null
): Promise<ModelDeploymentSummary[]> {
  return apiFetch<ModelDeploymentSummary[]>("/model-deployments/my", { projectId });
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

export async function stopModelDeployment(
  deploymentId: string
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(`/model-deployments/${deploymentId}/stop`, {
    method: "POST"
  });
}

export async function startModelDeployment(
  deploymentId: string
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(`/model-deployments/${deploymentId}/start`, {
    method: "POST"
  });
}

export async function unloadModelDeployment(
  deploymentId: string
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(`/model-deployments/${deploymentId}/unload`, {
    method: "POST"
  });
}

export async function deleteModelDeploymentTask(
  deploymentId: string,
  taskKind: "deployment" | "unload"
): Promise<ModelDeploymentSummary> {
  return apiFetch<ModelDeploymentSummary>(
    `/model-deployments/${deploymentId}/tasks/${taskKind}`,
    {
      method: "DELETE"
    }
  );
}

export async function checkModelDeploymentPassiveHealth(
  deploymentId: string
): Promise<ModelDeploymentPassiveHealth> {
  return apiFetch<ModelDeploymentPassiveHealth>(
    `/model-deployments/${deploymentId}/passive-health`,
    {
      method: "POST"
    }
  );
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

export async function getInferenceMachineRuntimeMetrics(
  machineId: string
): Promise<InferenceMachineRuntimeMetrics> {
  return apiFetch<InferenceMachineRuntimeMetrics>(
    `/model-deployments/machines/${machineId}/runtime-metrics`
  );
}
