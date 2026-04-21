import {
  getInferenceMachines,
  getModelDeployments
} from "@/features/model-deployments/api";
import { ModelDeploymentsConsole } from "@/features/model-deployments/components/model-deployments-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EndpointPage({
  searchParams
}: {
  searchParams: Promise<{ deploymentId?: string }>;
}) {
  const projectId = await getCurrentProjectIdFromCookie();
  const resolvedSearchParams = await searchParams;
  const deployments = await getModelDeployments(projectId).catch(() => []);
  const machines = await getInferenceMachines(projectId).catch(() => []);

  return (
    <ModelDeploymentsConsole
      initialDeployments={deployments}
      initialMachines={machines}
      selectedDeploymentId={resolvedSearchParams.deploymentId}
    />
  );
}
