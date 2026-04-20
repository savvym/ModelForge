"use client";

import { Check, Copy } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const CodeBlockContext = createContext<{ code: string }>({ code: "" });

type AiCodeBlockProps = {
  className?: string;
  code: string;
  isIncomplete?: boolean;
  language?: string;
};

type CodeBlockProps = HTMLAttributes<HTMLDivElement> & {
  children?: ReactNode;
  code: string;
  isIncomplete?: boolean;
  language?: string;
};

function formatLanguageLabel(language?: string) {
  const value = (language || "").trim().toLowerCase();
  if (!value) {
    return "text";
  }
  return value;
}

export function CodeBlock({
  children,
  className,
  code,
  isIncomplete = false,
  language,
  ...props
}: CodeBlockProps) {
  const contextValue = useMemo(() => ({ code }), [code]);

  return (
    <CodeBlockContext.Provider value={contextValue}>
      <div
        className={cn(
          "group relative w-full overflow-hidden rounded-lg border border-border bg-card/80 text-foreground",
          className
        )}
        data-language={formatLanguageLabel(language)}
        {...props}
      >
        {children}
        <div className="overflow-x-auto">
          <pre className="m-0 p-4">
            <code
              className={cn(
                "block min-w-full whitespace-pre font-mono text-[14px] leading-7 text-foreground [overflow-wrap:normal] break-normal"
              )}
            >
              {code}
              {isIncomplete ? "\n" : ""}
            </code>
          </pre>
        </div>
      </div>
    </CodeBlockContext.Provider>
  );
}

export function CodeBlockHeader({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-b border-border bg-muted/40 px-3.5 py-2 text-xs text-muted-foreground",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CodeBlockTitle({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center gap-2", className)} {...props}>
      {children}
    </div>
  );
}

export function CodeBlockFilename({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn("font-mono uppercase tracking-[0.12em]", className)} {...props}>
      {children}
    </span>
  );
}

export function CodeBlockActions({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center gap-1", className)} {...props}>
      {children}
    </div>
  );
}

export function CodeBlockCopyButton({
  className,
}: {
  className?: string;
}) {
  const { code } = useContext(CodeBlockContext);
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number>(0);

  useEffect(() => {
    return () => window.clearTimeout(timeoutRef.current);
  }, []);

  async function copyCode() {
    try {
      if (!copied) {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        timeoutRef.current = window.setTimeout(() => setCopied(false), 1500);
      }
    } catch {
      setCopied(false);
    }
  }

  const Icon = copied ? Check : Copy;

  return (
    <Button
      className={cn(
        "h-7 w-7 shrink-0 rounded-full border border-transparent bg-transparent p-0 text-muted-foreground shadow-none hover:bg-muted/40 hover:text-foreground",
        className
      )}
      onClick={copyCode}
      type="button"
      variant="ghost"
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="sr-only">{copied ? "已复制" : "复制代码"}</span>
    </Button>
  );
}

export function AiCodeBlock({
  className,
  code,
  isIncomplete = false,
  language,
}: AiCodeBlockProps) {
  return (
    <CodeBlock
      className={className}
      code={code}
      isIncomplete={isIncomplete}
      language={formatLanguageLabel(language)}
    >
      <CodeBlockHeader>
        <CodeBlockTitle>
          <CodeBlockFilename>{formatLanguageLabel(language)}</CodeBlockFilename>
        </CodeBlockTitle>
        <CodeBlockActions>
          <CodeBlockCopyButton />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>
  );
}
