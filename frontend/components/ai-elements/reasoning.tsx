"use client";

import { useControllableState } from "@radix-ui/react-use-controllable-state";
import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import { Brain, ChevronDown } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import {
  createContext,
  memo,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { Streamdown } from "streamdown";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

const streamdownPlugins = { cjk, code, math, mermaid };
const MS_IN_S = 1000;

type ReasoningContextValue = {
  duration: number | undefined;
  isOpen: boolean;
  isStreaming: boolean;
  setIsOpen: (open: boolean) => void;
};

const ReasoningContext = createContext<ReasoningContextValue | null>(null);

function useReasoning() {
  const context = useContext(ReasoningContext);
  if (!context) {
    throw new Error("Reasoning components must be used within Reasoning");
  }
  return context;
}

export type ReasoningProps = ComponentProps<typeof Collapsible> & {
  defaultOpen?: boolean;
  duration?: number;
  isStreaming?: boolean;
  onOpenChange?: (open: boolean) => void;
  open?: boolean;
};

export const Reasoning = memo(
  ({
    children,
    className,
    defaultOpen,
    duration: durationProp,
    isStreaming = false,
    onOpenChange,
    open,
    ...props
  }: ReasoningProps) => {
    const [isOpen, setIsOpen] = useControllableState<boolean>({
      defaultProp: defaultOpen ?? false,
      onChange: onOpenChange,
      prop: open,
    });
    const [duration, setDuration] = useControllableState<number | undefined>({
      defaultProp: undefined,
      prop: durationProp,
    });
    const startTimeRef = useRef<number | null>(null);

    useEffect(() => {
      if (isStreaming) {
        if (startTimeRef.current === null) {
          startTimeRef.current = Date.now();
        }
      } else if (startTimeRef.current !== null) {
        setDuration(Math.ceil((Date.now() - startTimeRef.current) / MS_IN_S));
        startTimeRef.current = null;
      }
    }, [isStreaming, setDuration]);

    const handleOpenChange = useCallback(
      (nextOpen: boolean) => {
        setIsOpen(nextOpen);
      },
      [setIsOpen]
    );

    const contextValue = useMemo(
      () => ({ duration, isOpen, isStreaming, setIsOpen }),
      [duration, isOpen, isStreaming, setIsOpen]
    );

    return (
      <ReasoningContext.Provider value={contextValue}>
        <Collapsible
          className={cn("mb-3 flex max-w-full flex-col items-start", className)}
          onOpenChange={handleOpenChange}
          open={isOpen}
          {...props}
        >
          {children}
        </Collapsible>
      </ReasoningContext.Provider>
    );
  }
);

export type ReasoningTriggerProps = ComponentProps<
  typeof CollapsibleTrigger
> & {
  getThinkingMessage?: (isStreaming: boolean, duration?: number) => ReactNode;
};

function defaultThinkingMessage(isStreaming: boolean, duration?: number) {
  if (isStreaming || duration === 0) {
    return (
      <span className="animate-pulse text-foreground">思考中</span>
    );
  }
  if (duration === undefined) {
    return <span>已完成思考</span>;
  }
  return <span>已思考 {duration} 秒</span>;
}

export const ReasoningTrigger = memo(
  ({
    children,
    className,
    getThinkingMessage = defaultThinkingMessage,
    ...props
  }: ReasoningTriggerProps) => {
    const { duration, isOpen, isStreaming } = useReasoning();

    return (
      <CollapsibleTrigger
        className={cn(
          "inline-flex h-8 max-w-full items-center gap-1.5 rounded-full border border-border/60 bg-muted/35 px-2.5 text-xs text-muted-foreground shadow-sm transition-colors hover:border-border hover:bg-muted/55 hover:text-foreground data-[state=open]:bg-muted/55",
          className
        )}
        {...props}
      >
        {children ?? (
          <>
            <Brain className="size-3.5" />
            <span className="truncate">
              {getThinkingMessage(isStreaming, duration)}
            </span>
            <ChevronDown
              className={cn(
                "size-3.5 shrink-0 transition-transform",
                isOpen ? "rotate-180" : "rotate-0"
              )}
            />
          </>
        )}
      </CollapsibleTrigger>
    );
  }
);

export type ReasoningContentProps = ComponentProps<
  typeof CollapsibleContent
> & {
  children: string;
};

export const ReasoningContent = memo(
  ({ children, className, ...props }: ReasoningContentProps) => (
    <CollapsibleContent
      className={cn(
        "ml-3 mt-2 max-w-full overflow-hidden border-l border-border/70 pl-4 text-[13px] leading-6 text-muted-foreground data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in",
        className
      )}
      {...props}
    >
      <Streamdown
        className="[&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-border [&_pre]:bg-card/80 [&_pre]:p-4"
        plugins={streamdownPlugins}
      >
        {children}
      </Streamdown>
    </CollapsibleContent>
  )
);

Reasoning.displayName = "Reasoning";
ReasoningTrigger.displayName = "ReasoningTrigger";
ReasoningContent.displayName = "ReasoningContent";
