import { getBrowserWebSocketBaseUrl } from "@/lib/network/runtime-base";

export function createWebSocket(path: string) {
  const base = getBrowserWebSocketBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return new WebSocket(`${base}${normalizedPath}`);
}
