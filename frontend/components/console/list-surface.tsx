import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export const consoleListSearchInputClassName =
  "h-8 min-w-[280px] rounded-[9px] border-slate-700/80 bg-[rgba(14,19,27,0.84)] pl-8 pr-3 text-[13px] text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] placeholder:text-slate-500 hover:border-slate-600/85 focus:border-slate-300/80 focus:bg-[rgba(17,23,32,0.96)] focus:ring-[3px] focus:ring-slate-100/10";

export const consoleListFilterTriggerClassName =
  "h-[30px] min-w-[148px] justify-between rounded-md border border-slate-800/80 bg-[rgba(10,15,22,0.72)] px-2.5 text-[12.5px] font-normal text-slate-200 shadow-none hover:bg-[rgba(14,20,29,0.84)] hover:text-white focus:border-slate-700 focus:ring-1 focus:ring-slate-700/40 data-[state=open]:bg-[rgba(16,23,33,0.9)]";

export function ConsoleListHeader({
  title,
  description,
  actions,
  className
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="space-y-1">
        <h1 className="text-[24px] font-semibold tracking-tight text-slate-50">{title}</h1>
        {description ? <p className="text-[13px] leading-5 text-slate-400">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </section>
  );
}

export function ConsoleListToolbar({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-x-3 gap-y-1 pb-0",
        className
      )}
    >
      {children}
    </div>
  );
}

export function ConsoleListToolbarCluster({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-wrap items-end gap-2", className)}>{children}</div>;
}

export function ConsoleListSearchForm({
  action,
  name = "q",
  defaultValue,
  placeholder,
  children,
  className,
  inputClassName
}: {
  action: string;
  name?: string;
  defaultValue?: string;
  placeholder: string;
  children?: React.ReactNode;
  className?: string;
  inputClassName?: string;
}) {
  return (
    <form action={action} className={cn("flex min-w-0 flex-1 flex-wrap items-end gap-2.5", className)}>
      {children}
      <div className="relative min-w-[260px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <Input
          className={cn(consoleListSearchInputClassName, "w-full", inputClassName)}
          defaultValue={defaultValue}
          name={name}
          placeholder={placeholder}
          type="search"
        />
      </div>
    </form>
  );
}

export function ConsoleListFilterField({
  label,
  children,
  className
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-[148px] flex-col gap-0.5", className)}>
      <div className="px-0.5 text-[11px] leading-none text-slate-500">{label}</div>
      {children}
    </div>
  );
}

export function ConsoleListTableSurface({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("overflow-hidden", className)}>{children}</div>;
}
