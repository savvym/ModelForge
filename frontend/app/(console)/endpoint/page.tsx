import {
  getInferenceMachines,
  getModelDeployments,
  getMyDeployments
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
  const [deployments, myDeployments, machines] = await Promise.all([
    getModelDeployments(projectId).catch(() => []),
    getMyDeployments(projectId).catch(() => []),
    getInferenceMachines(projectId).catch(() => [])
  ]);

  return (
    <ModelDeploymentsConsole
      initialDeployments={deployments}
      initialMyDeployments={myDeployments}
      initialMachines={machines}
      selectedDeploymentId={resolvedSearchParams.deploymentId}
    />
  );
}
