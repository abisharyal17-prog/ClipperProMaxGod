import { Link } from "react-router-dom";

import { cn } from "../../lib/cn";
import { cookieHealth, useCookieStatus } from "../../hooks/useCookieStatus";
import type { CookieHealth } from "../../hooks/useCookieStatus";
import { StatusDot, Tooltip } from "../ui";
import type { BadgeVariant } from "../ui";

const TONE: Record<CookieHealth, BadgeVariant> = {
  unknown: "neutral",
  ok: "success",
  warning: "warning",
  danger: "danger",
};

function summary(health: CookieHealth): string {
  switch (health) {
    case "ok":
      return "Cookies look healthy";
    case "warning":
      return "Cookies need attention";
    case "danger":
      return "Cookies expired or unauthenticated";
    default:
      return "Cookies: unknown";
  }
}

/** Small status dot linking to Settings. Status is dot + text, never colour alone. */
export function CookieHealthDot() {
  const query = useCookieStatus();
  const health = cookieHealth(query.data);
  const label = summary(health);

  return (
    <Tooltip content={label} side="bottom">
      <Link
        to="/settings"
        className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-transparent px-2 text-label text-muted transition-colors duration-150 ease-out hover:bg-surface-2 hover:text-text"
        aria-label={`Cookies status: ${label}. Open settings.`}
      >
        <StatusDot tone={TONE[health]} className={cn(health === "ok" && "bg-success")} />
        <span className="hidden md:inline">Cookies</span>
      </Link>
    </Tooltip>
  );
}
