"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ProbeTaskCreateForm } from "@/features/eval/components/probe-task-create-form";
import type { ModelProviderSummary, ProbeSummary } from "@/types/api";

type ProbeTaskCreateSheetProps = {
  initialOpen?: boolean;
  probes: ProbeSummary[];
  providers: ModelProviderSummary[];
};

export function ProbeTaskCreateSheet({
  initialOpen = false,
  probes,
  providers
}: ProbeTaskCreateSheetProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [open, setOpen] = React.useState(initialOpen);

  React.useEffect(() => {
    setOpen(initialOpen);
  }, [initialOpen]);

  function buildHref(nextOpen: boolean) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", "tasks");
    if (nextOpen) {
      params.set("create", "1");
    } else {
      params.delete("create");
    }
    const query = params.toString();
    return query ? `${pathname}?${query}` : pathname;
  }

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    router.replace(buildHref(nextOpen), { scroll: false });
  }

  return (
    <>
      <Button onClick={() => handleOpenChange(true)} size="sm" type="button">
        创建 Probe 任务
      </Button>

      <Sheet onOpenChange={handleOpenChange} open={open}>
        <SheetContent className="w-full gap-0 overflow-hidden border-l border-border bg-card px-0 py-0 text-foreground shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-[860px] [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-muted-foreground [&>button]:hover:bg-card/80 [&>button]:hover:text-foreground">
          <SheetHeader className="border-b border-border px-6 pb-5 pt-6 pr-12 text-left sm:px-7">
            <SheetTitle className="text-[22px] font-semibold tracking-[0.01em] text-foreground">
              创建 Probe 任务
            </SheetTitle>
          </SheetHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6 sm:px-7">
            <ProbeTaskCreateForm
              onCreated={() => handleOpenChange(false)}
              probes={probes}
              providers={providers}
            />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
