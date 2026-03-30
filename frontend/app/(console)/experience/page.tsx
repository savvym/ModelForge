import { ExperienceChatConsole } from "@/features/experience/components/experience-chat-console";
import { getRegistryModels } from "@/features/model-registry/api";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ExperiencePage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const models = await getRegistryModels(projectId).catch(() => []);

  return (
    <div className="console-workbench h-full min-h-0">
      <ExperienceChatConsole models={models} />
    </div>
  );
}
