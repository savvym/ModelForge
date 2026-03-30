"use client";

import type { ChatStatus } from "ai";
import { CornerDownLeft, Square, Sparkles } from "lucide-react";
import type {
  ChangeEvent,
  ComponentProps,
  FormEvent,
  HTMLAttributes,
  KeyboardEvent,
  PropsWithChildren,
} from "react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

type PromptInputControllerValue = {
  clear: () => void;
  setInput: (value: string) => void;
  value: string;
};

const PromptInputControllerContext =
  createContext<PromptInputControllerValue | null>(null);

function useOptionalPromptInputController() {
  return useContext(PromptInputControllerContext);
}

export function usePromptInputController() {
  const context = useOptionalPromptInputController();
  if (!context) {
    throw new Error(
      "PromptInput components must be used within PromptInputProvider"
    );
  }
  return context;
}

export function PromptInputProvider({
  children,
  initialInput = "",
}: PropsWithChildren<{ initialInput?: string }>) {
  const [value, setValue] = useState(initialInput);

  const controller = useMemo(
    () => ({
      clear: () => setValue(""),
      setInput: setValue,
      value,
    }),
    [value]
  );

  return (
    <PromptInputControllerContext.Provider value={controller}>
      {children}
    </PromptInputControllerContext.Provider>
  );
}

export type PromptInputProps = Omit<
  HTMLAttributes<HTMLFormElement>,
  "onSubmit"
> & {
  onSubmit: (
    message: { text: string },
    event: FormEvent<HTMLFormElement>
  ) => void | Promise<void>;
};

export function PromptInput({
  children,
  className,
  onSubmit,
  ...props
}: PromptInputProps) {
  const controller = useOptionalPromptInputController();
  const [localValue, setLocalValue] = useState("");
  const value = controller?.value ?? localValue;
  const setInput = controller?.setInput ?? setLocalValue;
  const clear = controller?.clear ?? (() => setLocalValue(""));

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      const nextValue = value.trim();
      if (!nextValue) {
        return;
      }

      try {
        await onSubmit({ text: nextValue }, event);
        clear();
      } catch {
        // Keep the current value when submit fails so users can retry.
      }
    },
    [clear, onSubmit, value]
  );

  return (
    <form
      className={cn("w-full", className)}
      onSubmit={handleSubmit}
      {...props}
    >
      <InputGroup>{children}</InputGroup>
    </form>
  );
}

export function PromptInputBody({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("contents", className)} {...props} />;
}

export function PromptInputTextarea({
  className,
  onChange,
  onKeyDown,
  placeholder = "输入你的问题，支持多行。",
  ...props
}: ComponentProps<typeof InputGroupTextarea>) {
  const controller = useOptionalPromptInputController();
  const [isComposing, setIsComposing] = useState(false);

  const handleChange = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      controller?.setInput(event.target.value);
      onChange?.(event);
    },
    [controller, onChange]
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      onKeyDown?.(event);
      if (event.defaultPrevented) {
        return;
      }

      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !isComposing &&
        !event.nativeEvent.isComposing
      ) {
        event.preventDefault();
        const form = event.currentTarget.form;
        const submitButton = form?.querySelector(
          'button[type="submit"]'
        ) as HTMLButtonElement | null;

        if (!submitButton?.disabled) {
          form?.requestSubmit();
        }
      }
    },
    [isComposing, onKeyDown]
  );

  return (
    <InputGroupTextarea
      className={cn("field-sizing-content max-h-48 min-h-16", className)}
      onChange={handleChange}
      onCompositionEnd={() => setIsComposing(false)}
      onCompositionStart={() => setIsComposing(true)}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      value={controller?.value}
      {...props}
    />
  );
}

export function PromptInputHeader({
  className,
  ...props
}: Omit<ComponentProps<typeof InputGroupAddon>, "align">) {
  return (
    <InputGroupAddon
      align="block-start"
      className={cn("order-first flex-wrap gap-1", className)}
      {...props}
    />
  );
}

export function PromptInputFooter({
  className,
  ...props
}: Omit<ComponentProps<typeof InputGroupAddon>, "align">) {
  return (
    <InputGroupAddon
      align="block-end"
      className={cn("justify-between gap-1", className)}
      {...props}
    />
  );
}

export function PromptInputTools({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex min-w-0 items-center gap-1", className)}
      {...props}
    />
  );
}

export function PromptInputButton({
  className,
  variant = "ghost",
  ...props
}: ComponentProps<typeof InputGroupButton>) {
  const size = props.size ?? (props.children ? "sm" : "icon-sm");

  return (
    <InputGroupButton
      className={cn(className)}
      size={size}
      type="button"
      variant={variant}
      {...props}
    />
  );
}

export type PromptInputSubmitProps = ComponentProps<
  typeof InputGroupButton
> & {
  onStop?: () => void;
  status?: ChatStatus;
};

export function PromptInputSubmit({
  children,
  className,
  onClick,
  onStop,
  size = "icon-sm",
  status,
  ...props
}: PromptInputSubmitProps) {
  const isGenerating = status === "submitted" || status === "streaming";

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      if (isGenerating && onStop) {
        event.preventDefault();
        onStop();
        return;
      }
      onClick?.(event);
    },
    [isGenerating, onClick, onStop]
  );

  let icon = <CornerDownLeft className="h-4 w-4" />;
  if (status === "submitted") {
    icon = <Spinner />;
  } else if (status === "streaming") {
    icon = <Square className="h-3.5 w-3.5 fill-current" />;
  } else if (status === "error") {
    icon = <Sparkles className="h-4 w-4" />;
  }

  return (
    <InputGroupButton
      aria-label={isGenerating ? "停止生成" : "发送消息"}
      className={cn(className)}
      onClick={handleClick}
      size={size}
      type={isGenerating && onStop ? "button" : "submit"}
      variant="default"
      {...props}
    >
      {children ?? icon}
    </InputGroupButton>
  );
}

export function PromptInputSelect(
  props: ComponentProps<typeof Select>
) {
  return <Select {...props} />;
}

export function PromptInputSelectTrigger({
  className,
  ...props
}: ComponentProps<typeof SelectTrigger>) {
  return (
    <SelectTrigger
      className={cn(
        "h-8 min-w-0 rounded-full border-white/10 bg-[rgba(255,255,255,0.03)] px-3 text-sm text-slate-100 shadow-none hover:bg-[rgba(255,255,255,0.05)] focus:bg-[rgba(255,255,255,0.06)]",
        className
      )}
      {...props}
    />
  );
}

export function PromptInputSelectContent({
  className,
  ...props
}: ComponentProps<typeof SelectContent>) {
  return <SelectContent className={cn(className)} {...props} />;
}

export function PromptInputSelectItem({
  className,
  ...props
}: ComponentProps<typeof SelectItem>) {
  return <SelectItem className={cn(className)} {...props} />;
}

export function PromptInputSelectValue({
  className,
  ...props
}: ComponentProps<typeof SelectValue>) {
  return <SelectValue className={cn(className)} {...props} />;
}
