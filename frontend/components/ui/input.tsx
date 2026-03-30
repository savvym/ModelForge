import { cn } from "@/lib/utils";

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-[12px] border border-slate-700/80 bg-[rgba(14,19,27,0.84)] px-3.5 py-1.5 text-[13.5px] leading-[1.15] text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] outline-none transition-[border-color,box-shadow,background-color] placeholder:text-slate-500 hover:border-slate-600/85 focus:border-slate-300/85 focus:bg-[rgba(17,23,32,0.96)] focus:ring-[3px] focus:ring-slate-100/10 disabled:cursor-not-allowed disabled:opacity-55",
        className
      )}
      {...props}
    />
  );
}
