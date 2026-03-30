import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#8fffcf] text-[#10161f] shadow-none hover:bg-[#79f5c1]",
        secondary: "border border-[rgba(249,249,251,0.18)] bg-[rgba(255,255,255,0.04)] text-slate-100 shadow-none hover:bg-[rgba(255,255,255,0.08)]",
        ghost: "text-slate-300 hover:bg-[rgba(255,255,255,0.05)] hover:text-white",
        outline:
          "border border-[rgba(249,249,251,0.24)] bg-transparent text-slate-100 shadow-[rgba(249,249,251,0.08)_0_0_0_1px_inset] hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
      },
      size: {
        default: "h-[30px] px-3 py-1.5",
        sm: "h-7 px-2.5 text-[13px]",
        lg: "h-9 px-4"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  )
);

Button.displayName = "Button";

export { Button, buttonVariants };
