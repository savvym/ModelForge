import { getModelProviders } from "@/features/model-registry/api";
import { ModelCreateForm } from "@/features/model-registry/components/model-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function CreateModelPage({
  searchParams
}: {
  searchParams: Promise<{ providerId?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const providers = await getModelProviders(projectId).catch(() => []);
  const initialProviderId = providers.some((provider) => provider.id === resolvedSearchParams.providerId)
    ? resolvedSearchParams.providerId
    : null;

  return <ModelCreateForm initialProviderId={initialProviderId} providers={providers} />;
}
