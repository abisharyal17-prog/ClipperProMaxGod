import { useQuery } from "@tanstack/react-query";

import { api, queryKeys } from "../lib/api";
import type { CookieStatus } from "../lib/types";

export type CookieHealth = "unknown" | "ok" | "warning" | "danger";

export function cookieHealth(status: CookieStatus | undefined): CookieHealth {
  if (!status) return "unknown";
  if (!status.present) return "warning";
  if (status.expired || !status.authenticated) return "danger";
  if (status.expiring_soon) return "warning";
  return "ok";
}

/** Shared cookie status query used by the shell dot and the settings panel. */
export function useCookieStatus() {
  return useQuery({
    queryKey: queryKeys.cookies,
    queryFn: api.cookies,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
