"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const inputGroupAddonVariants = cva("flex w-full items-center gap-2", {
  variants: {
    align: {
      "block-start": "order-first flex-wrap px-4 pt-4",
      "block-end": "order-last justify-between px-3 pb-3 pt-2",
    },
  },
  defaultVariants: {
    align: "block-start",
  },
});

type InputGroupButtonSize = "xs" | "sm" | "icon-sm";

const inputGroupButtonSizeClassName: Record<InputGroupButtonSize, string> = {
  xs: "h-7 rounded-full px-2.5 text-[12.5px]",
  sm: "h-8 rounded-full px-3 text-[13px]",
  "icon-sm": "h-8 w-8 rounded-full p-0",
};

export function InputGroup({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "group flex w-full flex-col rounded-[24px] border border-white/8 bg-[rgba(10,14,21,0.9)] shadow-[0_12px_28px_rgba(2,6,23,0.14)] backdrop-blur-md transition-[border-color,box-shadow]",
        "focus-within:border-white/12 focus-within:shadow-[0_16px_36px_rgba(2,6,23,0.18)]",
        className
      )}
      data-slot="input-group"
      role="group"
      {...props}
    />
  );
}

export function InputGroupAddon({
  className,
  align,
  ...props
}: React.ComponentProps<"div"> &
  VariantProps<typeof inputGroupAddonVariants>) {
  return (
    <div
      className={cn(inputGroupAddonVariants({ align }), className)}
      data-align={align}
      data-slot="input-group-addon"
      role="group"
      {...props}
    />
  );
}

export function InputGroupButton({
  className,
  size = "xs",
  variant = "ghost",
  ...props
}: Omit<ButtonProps, "size"> & {
  size?: InputGroupButtonSize;
}) {
  return (
    <Button
      className={cn(
        "gap-1.5 border border-transparent shadow-none",
        inputGroupButtonSizeClassName[size],
        variant === "ghost" &&
          "bg-transparent text-slate-500 hover:bg-[rgba(255,255,255,0.05)] hover:text-slate-100",
        variant === "secondary" &&
          "border-white/8 bg-[rgba(255,255,255,0.04)] text-slate-100 hover:bg-[rgba(255,255,255,0.08)]",
        variant === "default" &&
          "bg-slate-100 text-slate-950 hover:bg-white",
        variant === "outline" &&
          "border-white/8 bg-transparent text-slate-200 hover:bg-[rgba(255,255,255,0.04)]",
        className
      )}
      variant={variant}
      {...props}
    />
  );
}

export function InputGroupTextarea({
  className,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <Textarea
      className={cn(
        "field-sizing-content min-h-16 max-h-48 w-full resize-none rounded-none !border-0 !bg-transparent px-4 pb-0 pt-4 text-[15px] leading-7 text-slate-100 shadow-none outline-none placeholder:text-slate-500 hover:!border-transparent focus:!border-transparent focus:!bg-transparent focus:!ring-0",
        className
      )}
      data-slot="input-group-control"
      {...props}
    />
  );
}
