import { getBrowserSseBaseUrl } from "@/lib/network/runtime-base";

export function createEventSource(path: string) {
  const base = getBrowserSseBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return new EventSource(`${base}${normalizedPath}`, {
    withCredentials: true
  });
}
