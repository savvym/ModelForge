import { getModelProviders, getRegistryModels } from "@/features/model-registry/api";
import { ModelRegistryConsole } from "@/features/model-registry/components/model-registry-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function ModelSquarePage({
  searchParams
}: {
  searchParams: Promise<{ provider?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const [providers, models] = await Promise.all([
    getModelProviders(projectId).catch(() => []),
    getRegistryModels(projectId).catch(() => [])
  ]);
  const initialSelectedProviderId = providers.some(
    (provider) => provider.id === resolvedSearchParams.provider
  )
    ? resolvedSearchParams.provider ?? null
    : null;

  return (
    <ModelRegistryConsole
      initialModels={models}
      initialProviders={providers}
      initialSelectedProviderId={initialSelectedProviderId}
      title="模型广场"
    />
  );
}
