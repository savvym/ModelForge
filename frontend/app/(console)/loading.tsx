import { Skeleton } from "@/components/ui/skeleton";

export default function ConsoleLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-sm space-y-3 px-4">
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-24 w-full" />
      </div>
    </div>
  );
}
