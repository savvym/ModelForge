import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  ConsoleListToolbar,
  ConsoleListToolbarCluster
} from "@/components/console/list-surface";
import { getEvalCollections } from "@/features/eval/api";
import { EvalCollectionListTable } from "@/features/eval/components/eval-collection-list-table";

export default async function EvalCollectionsPage() {
  const collections = await getEvalCollections().catch(() => []);

  return (
    <div className="space-y-4">
      <ConsoleListToolbar>
        <ConsoleListToolbarCluster>
          <h1 className="text-lg font-semibold">评测套件</h1>
        </ConsoleListToolbarCluster>
        <ConsoleListToolbarCluster>
          <Link href="/model/eval-collections/create">
            <Button size="sm">创建评测套件</Button>
          </Link>
        </ConsoleListToolbarCluster>
      </ConsoleListToolbar>

      <EvalCollectionListTable collections={collections} />
    </div>
  );
}
