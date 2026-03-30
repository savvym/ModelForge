import { notFound } from "next/navigation";
import { getModelProvider } from "@/features/model-registry/api";
import { ProviderEditorForm } from "@/features/model-registry/components/provider-editor-form";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function EditProviderPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const projectId = await getCurrentProjectIdFromCookie();

  try {
    const provider = await getModelProvider(id, projectId);
    return <ProviderEditorForm initialProvider={provider} mode="edit" />;
  } catch {
    notFound();
  }
}
