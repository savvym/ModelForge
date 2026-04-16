"use client";

import { useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

type RouteTabItem = {
  href: string;
  label: string;
  value: string;
};

export function RouteTabs({
  items,
  value,
  className,
  listClassName
}: {
  items: RouteTabItem[];
  value: string;
  className?: string;
  listClassName?: string;
}) {
  const router = useRouter();

  function handleValueChange(nextValue: string) {
    const nextItem = items.find((item) => item.value === nextValue);
    if (!nextItem || nextItem.value === value) {
      return;
    }
    router.push(nextItem.href);
  }

  return (
    <Tabs className={className} onValueChange={handleValueChange} value={value}>
      <TabsList
        className={cn(
          "h-auto w-full justify-start gap-1 rounded-lg border border-border/60 bg-card/60 p-1",
          listClassName
        )}
      >
        {items.map((item) => (
          <TabsTrigger
            className="rounded-md px-3 py-1.5 text-sm data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-none"
            key={item.value}
            value={item.value}
          >
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
