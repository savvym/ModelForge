"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { EvalJobCreateForm } from "@/features/eval/components/eval-job-create-form";
import type { BenchmarkDefinitionSummary, RegistryModelSummary } from "@/types/api";

type EvalJobCreateSheetProps = {
  benchmarks: BenchmarkDefinitionSummary[];
  models: RegistryModelSummary[];
  initialOpen?: boolean;
};

export function EvalJobCreateSheet({
  benchmarks,
  models,
  initialOpen = false
}: EvalJobCreateSheetProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [open, setOpen] = React.useState(initialOpen);

  React.useEffect(() => {
    setOpen(initialOpen);
  }, [initialOpen]);

  function buildHref(nextOpen: boolean) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", "jobs");
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
        创建评测任务
      </Button>

      <Sheet onOpenChange={handleOpenChange} open={open}>
        <SheetContent className="w-full gap-0 overflow-hidden border-l border-slate-800/85 bg-[linear-gradient(180deg,rgba(10,15,22,0.98),rgba(8,12,19,0.95))] px-0 py-0 text-slate-100 shadow-[-30px_0_70px_rgba(2,6,23,0.6)] sm:max-w-[760px] [&>button]:right-4 [&>button]:top-4 [&>button]:rounded-md [&>button]:text-slate-500 [&>button]:hover:bg-slate-800/80 [&>button]:hover:text-slate-100">
          <SheetHeader className="border-b border-slate-800/80 px-6 pb-5 pt-6 pr-12 text-left sm:px-7">
            <SheetTitle className="text-[22px] font-semibold tracking-[0.01em] text-slate-50">
              创建评测任务
            </SheetTitle>
          </SheetHeader>

          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6 sm:px-7">
            <EvalJobCreateForm benchmarks={benchmarks} models={models} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
