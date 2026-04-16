import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export const consoleListSearchInputClassName =
  "h-9 min-w-[280px] rounded-lg bg-background/70 pl-8 pr-3 shadow-none";

export const consoleListFilterTriggerClassName =
  "h-9 min-w-[148px] justify-between rounded-lg bg-background/70 px-2.5 text-sm font-normal shadow-none data-[state=open]:bg-accent/70";

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
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description ? <p className="text-sm leading-6 text-muted-foreground">{description}</p> : null}
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
        "flex flex-wrap items-start justify-between gap-x-3 gap-y-2 pb-0",
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
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
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
      <div className="px-0.5 text-[11px] leading-none text-muted-foreground">{label}</div>
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
