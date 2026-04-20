"use client";

import Link from "next/link";

type ModelRegistryBreadcrumbProps = {
  current: string;
};

export function ModelRegistryBreadcrumb({ current }: ModelRegistryBreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className="flex items-center gap-2 text-sm text-muted-foreground">
      <Link
        className="transition-colors hover:text-foreground"
        href="/model-square"
      >
        模型广场
      </Link>
      <span className="text-foreground">&gt;</span>
      <span className="font-medium text-foreground">{current}</span>
    </nav>
  );
}
