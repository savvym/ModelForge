import { ObjectStoreConsole } from "@/features/object-store/components/object-store-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";

export default async function FilesPage({
  searchParams
}: {
  searchParams: Promise<{ bucket?: string; prefix?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const rootPrefix = projectId ? `projects/${projectId}/files/` : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ObjectStoreConsole
        initialBucket={resolvedSearchParams.bucket}
        initialPrefix={resolvedSearchParams.prefix ?? rootPrefix}
        mode="files"
        rootPrefix={rootPrefix}
      />
    </div>
  );
}
