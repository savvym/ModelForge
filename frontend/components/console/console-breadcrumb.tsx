import Link from "next/link";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "@/components/ui/breadcrumb";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

export function ConsoleBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <Breadcrumb>
      <BreadcrumbList className="text-[13px] text-muted-foreground">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        return (
          <BreadcrumbItem key={`${item.label}-${index}`}>
            {item.href && !isLast ? (
              <BreadcrumbLink asChild className="hover:text-foreground">
                <Link href={item.href}>{item.label}</Link>
              </BreadcrumbLink>
            ) : (
              <BreadcrumbPage className={isLast ? "text-foreground" : "text-muted-foreground"}>
                {item.label}
              </BreadcrumbPage>
            )}
            {!isLast ? <BreadcrumbSeparator className="text-muted-foreground" /> : null}
          </BreadcrumbItem>
        );
      })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
