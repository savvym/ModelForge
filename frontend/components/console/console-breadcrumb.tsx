import Link from "next/link";
import { ChevronRight } from "lucide-react";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

export function ConsoleBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex flex-wrap items-center gap-1.5 text-[13px] text-slate-500"
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        return (
          <div className="flex items-center gap-1.5" key={`${item.label}-${index}`}>
            {item.href && !isLast ? (
              <Link
                className="transition-colors hover:text-slate-200"
                href={item.href}
              >
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? "text-slate-300" : undefined}>{item.label}</span>
            )}
            {!isLast ? <ChevronRight className="h-3.5 w-3.5 text-slate-600" /> : null}
          </div>
        );
      })}
    </nav>
  );
}
