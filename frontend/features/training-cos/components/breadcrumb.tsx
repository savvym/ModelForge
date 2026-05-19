import Link from "next/link";
import { ChevronRight, FolderOpen } from "lucide-react";

function buildPrefixHref(prefix: string): string {
  if (!prefix) return "/training-cos";
  const segments = prefix
    .replace(/^\/+/, "")
    .replace(/\/+$/, "")
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment));
  return `/training-cos/${segments.join("/")}`;
}

export function TrainingCosBreadcrumb({
  prefix,
  bucket
}: {
  prefix: string;
  bucket: string | null;
}) {
  const cleaned = prefix.replace(/^\/+/, "").replace(/\/+$/, "");
  const segments = cleaned ? cleaned.split("/") : [];
  return (
    <nav className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
      <Link href="/training-cos" className="inline-flex items-center gap-1 hover:text-foreground">
        <FolderOpen className="size-4" />
        {bucket || "training-cos"}
      </Link>
      {segments.map((segment, index) => {
        const accumulated = segments.slice(0, index + 1).join("/") + "/";
        const isLast = index === segments.length - 1;
        return (
          <span key={accumulated} className="inline-flex items-center gap-1">
            <ChevronRight className="size-3.5" />
            {isLast ? (
              <span className="text-foreground">{segment}</span>
            ) : (
              <Link href={buildPrefixHref(accumulated)} className="hover:text-foreground">
                {segment}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
