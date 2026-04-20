import { ObjectStoreConsole } from "@/features/object-store/components/object-store-console";
import { getCurrentProjectIdFromCookie } from "@/features/project/server";
import { buildProjectPrefix } from "@/lib/object-store-layout";

export default async function DataPage({
  searchParams
}: {
  searchParams: Promise<{ bucket?: string; prefix?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const projectId = await getCurrentProjectIdFromCookie();
  const rootPrefix = projectId ? buildProjectPrefix(projectId) : undefined;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ObjectStoreConsole
        initialBucket={resolvedSearchParams.bucket}
        initialPrefix={resolvedSearchParams.prefix ?? rootPrefix}
        allowMutations={false}
        mode="files"
        presentation="rustfs"
        rootPrefix={rootPrefix}
      />
    </div>
  );
}
