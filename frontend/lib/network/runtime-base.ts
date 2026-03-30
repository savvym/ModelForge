"use client";

const LOCAL_DEVELOPMENT_GATEWAY_PORT = 8081;

function isLocalDevelopmentHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

function getLocalDevelopmentGatewayOrigin() {
  return `${window.location.protocol}//${window.location.hostname}:${LOCAL_DEVELOPMENT_GATEWAY_PORT}`;
}

export function getBrowserApiBaseUrl() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  if (isLocalDevelopmentHost(window.location.hostname)) {
    return `${getLocalDevelopmentGatewayOrigin()}/api/v1`;
  }

  return "/api/v1";
}

export function getBrowserSseBaseUrl() {
  if (process.env.NEXT_PUBLIC_SSE_BASE_URL) {
    return process.env.NEXT_PUBLIC_SSE_BASE_URL;
  }

  if (isLocalDevelopmentHost(window.location.hostname)) {
    return `${getLocalDevelopmentGatewayOrigin()}/api/v1/streams`;
  }

  return `${window.location.origin}/api/v1/streams`;
}

export function getBrowserWebSocketBaseUrl() {
  if (process.env.NEXT_PUBLIC_WS_BASE_URL) {
    return process.env.NEXT_PUBLIC_WS_BASE_URL;
  }

  if (isLocalDevelopmentHost(window.location.hostname)) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    return `${protocol}://${window.location.hostname}:${LOCAL_DEVELOPMENT_GATEWAY_PORT}/ws`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws`;
}
