import type { ModelDeploymentSummary, RegistryModelSummary } from "@/types/api";

const PREFERRED_PROVIDER_NAME = "ai.zhanghd.com";
const PREFERRED_MODEL_NAME = "GPT-5.4";

export type EvalModelTargetOption = {
  id: string;
  modelId?: string | null;
  name: string;
  providerName: string;
  source: "registry" | "deployment";
  targetId: string;
};

export function buildEvalModelTargetOptions(
  models: RegistryModelSummary[],
  deployments: ModelDeploymentSummary[] = []
): EvalModelTargetOption[] {
  const registryOptions = models
    .filter((model) => model.status === "active" && Boolean(model.provider_id))
    .map((model) => ({
      id: `registry:${model.id}`,
      modelId: model.id,
      name: model.name,
      providerName: model.provider_name?.trim() || "Unknown Provider",
      source: "registry" as const,
      targetId: model.id
    }));

  const deploymentOptions = deployments
    .filter(isReadyDeployment)
    .map((deployment) => ({
      id: `deployment:${deployment.id}`,
      modelId: deployment.model_id,
      name: deployment.served_model_name ?? deployment.model_name ?? deployment.name,
      providerName: deployment.machine_name?.trim() || "我的部署",
      source: "deployment" as const,
      targetId: deployment.id
    }));

  return [...registryOptions, ...deploymentOptions];
}

export function pickDefaultEvalModelTarget(options: EvalModelTargetOption[]) {
  return (
    options.find(
      (option) =>
        option.source === "registry" &&
        option.name === PREFERRED_MODEL_NAME &&
        option.providerName.toLowerCase().includes(PREFERRED_PROVIDER_NAME)
    ) ??
    options.find((option) => option.source === "registry" && option.name === PREFERRED_MODEL_NAME) ??
    options[0] ??
    null
  );
}

export function describeEvalModelTarget(option: EvalModelTargetOption): string {
  if (option.source === "deployment") {
    return `${option.providerName} / ${option.targetId}`;
  }
  return option.providerName;
}

export function formatEvalModelTargetOption(option: EvalModelTargetOption): string {
  const sourceLabel = option.source === "deployment" ? "我的部署" : "模型广场";
  return `${sourceLabel} · ${option.name} · ${option.providerName}`;
}

export function buildEvalModelTargetPayload(option: EvalModelTargetOption) {
  if (option.source === "deployment") {
    return {
      model_id: option.modelId ?? null,
      model_deployment_id: option.targetId
    };
  }
  return {
    model_id: option.targetId,
    model_deployment_id: null
  };
}

function isReadyDeployment(deployment: ModelDeploymentSummary) {
  return (deployment.phase ?? deployment.status) === "ready" && Boolean(deployment.endpoint_url);
}
