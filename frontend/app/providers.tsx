"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";
import { DatasetUploadManagerProvider } from "@/features/dataset/components/dataset-upload-manager";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false
          }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <DatasetUploadManagerProvider>
        {children}
        <Toaster richColors position="top-right" />
      </DatasetUploadManagerProvider>
    </QueryClientProvider>
  );
}
