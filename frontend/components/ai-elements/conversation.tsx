"use client";

import { ArrowDownIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useCallback } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ConversationProps = ComponentProps<typeof StickToBottom>;

export function Conversation({
  className,
  ...props
}: ConversationProps) {
  return (
    <StickToBottom
      className={cn("relative flex-1 min-h-0 overflow-hidden", className)}
      initial="smooth"
      resize="smooth"
      role="log"
      {...props}
    />
  );
}

export type ConversationContentProps = ComponentProps<
  typeof StickToBottom.Content
>;

export function ConversationContent({
  className,
  scrollClassName,
  ...props
}: ConversationContentProps) {
  return (
    <StickToBottom.Content
      scrollClassName={cn(
        "h-full overflow-y-auto overscroll-y-contain",
        scrollClassName
      )}
      className={cn("flex min-h-full flex-col gap-8 p-4", className)}
      {...props}
    />
  );
}

export type ConversationEmptyStateProps = ComponentProps<"div"> & {
  title?: string;
  description?: string;
  icon?: ReactNode;
};

export function ConversationEmptyState({
  children,
  className,
  description = "从一个简短问题开始。",
  icon,
  title = "开始一段新对话",
  ...props
}: ConversationEmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-[360px] w-full flex-col items-center justify-center gap-4 px-6 py-10 text-center",
        className
      )}
      {...props}
    >
      {children ?? (
        <>
          {icon ? <div className="text-muted-foreground">{icon}</div> : null}
          <div className="space-y-2">
            <h3 className="text-lg font-medium text-foreground">{title}</h3>
            {description ? (
              <p className="text-sm leading-6 text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

export type ConversationScrollButtonProps = ComponentProps<typeof Button>;

export function ConversationScrollButton({
  className,
  ...props
}: ConversationScrollButtonProps) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  const handleScrollToBottom = useCallback(() => {
    scrollToBottom();
  }, [scrollToBottom]);

  if (isAtBottom) {
    return null;
  }

  return (
    <Button
      className={cn(
        "absolute bottom-4 left-1/2 h-9 w-9 -translate-x-1/2 rounded-full border border-border bg-card/90 p-0 text-foreground shadow-lg hover:bg-accent hover:text-accent-foreground",
        className
      )}
      onClick={handleScrollToBottom}
      type="button"
      variant="outline"
      {...props}
    >
      <ArrowDownIcon className="h-4 w-4" />
      <span className="sr-only">滚动到底部</span>
    </Button>
  );
}
