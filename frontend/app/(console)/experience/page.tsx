import { ExperienceChatConsole } from "@/features/experience/components/experience-chat-console";
import { getMyDeployments } from "@/features/model-deployments/api";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ExperiencePage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const [models, deployments] = await Promise.all([
    getRegistryModels(projectId).catch(() => []),
    getMyDeployments(projectId).catch(() => [])
  ]);

  return (
    <div className="console-workbench h-full min-h-0">
      <ExperienceChatConsole deployments={deployments} models={models} />
    </div>
  );
}
