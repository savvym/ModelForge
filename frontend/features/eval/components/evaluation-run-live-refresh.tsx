"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

const LIVE_STATUSES = new Set(["queued", "running", "cancelling"]);

type EvaluationRunLiveRefreshProps = {
  statuses: string[];
  intervalMs?: number;
};

export function EvaluationRunLiveRefresh({
  statuses,
  intervalMs = 5000
}: EvaluationRunLiveRefreshProps) {
  const router = useRouter();
  const shouldRefresh = statuses.some((status) => LIVE_STATUSES.has(status));

  React.useEffect(() => {
    if (!shouldRefresh) {
      return;
    }

    const interval = window.setInterval(() => {
      router.refresh();
    }, intervalMs);

    return () => {
      window.clearInterval(interval);
    };
  }, [intervalMs, router, shouldRefresh]);

  return null;
}
