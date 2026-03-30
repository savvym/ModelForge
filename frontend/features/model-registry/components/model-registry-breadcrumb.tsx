"use client";

import Link from "next/link";

type ModelRegistryBreadcrumbProps = {
  current: string;
};

export function ModelRegistryBreadcrumb({ current }: ModelRegistryBreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className="flex items-center gap-2 text-sm text-zinc-500">
      <Link
        className="transition-colors hover:text-zinc-900"
        href="/model-square"
      >
        模型广场
      </Link>
      <span className="text-zinc-300">&gt;</span>
      <span className="font-medium text-zinc-900">{current}</span>
    </nav>
  );
}
