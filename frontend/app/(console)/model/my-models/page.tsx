import { getRegistryModels } from "@/features/model-registry/api";
import { MyModelsConsole } from "@/features/model-registry/components/my-models-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function MyModelsPage() {
  const projectId = await getCurrentProjectIdFromCookie();
  const models = await getRegistryModels(projectId).catch(() => []);

  return <MyModelsConsole initialModels={models} />;
}
