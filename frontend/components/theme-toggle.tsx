"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted ? resolvedTheme === "dark" : true;
  const label = mounted ? (isDark ? "切换到日间模式" : "切换到夜间模式") : "切换主题";

  return (
    <Button
      aria-label={label}
      className="relative size-8 rounded-md text-muted-foreground"
      onClick={() => {
        if (!mounted) {
          return;
        }

        setTheme(isDark ? "light" : "dark");
      }}
      size="icon"
      title={label}
      type="button"
      variant="ghost"
    >
      <Sun className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">切换主题</span>
    </Button>
  );
}
