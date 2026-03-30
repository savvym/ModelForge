import { notFound } from "next/navigation";
import { getModelProviders, getRegistryModel } from "@/features/model-registry/api";
import { ModelCreateForm } from "@/features/model-registry/components/model-create-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditModelPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();
  const [providers, model] = await Promise.all([
    getModelProviders(projectId).catch(() => []),
    getRegistryModel(id, projectId).catch(() => null)
  ]);

  if (!model) {
    notFound();
  }

  return <ModelCreateForm initialModel={model} mode="edit" providers={providers} />;
}
