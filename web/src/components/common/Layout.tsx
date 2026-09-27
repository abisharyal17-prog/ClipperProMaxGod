import { Link, NavLink, Outlet } from "react-router-dom";
import { Moon, Scissors, Sun } from "lucide-react";

import { cn } from "../../lib/cn";
import { useTheme } from "../../hooks/useTheme";
import { useCookieStatus } from "../../hooks/useCookieStatus";
import { Button, Tooltip } from "../ui";
import { JobIndicator } from "./JobIndicator";
import { CookieHealthDot } from "./CookieHealthDot";
import type { AlertTone } from "../ui";

const NAV = [
  { to: "/", label: "Projects", end: true },
  { to: "/settings", label: "Settings", end: false },
];

interface CookieBanner {
  tone: AlertTone;
  message: string;
}

export function Layout() {
  const { theme, toggle } = useTheme();
  const cookieQuery = useCookieStatus();
  const cookies = cookieQuery.data;

  let banner: CookieBanner | null = null;
  if (cookies) {
    if (cookies.present && cookies.expired) {
      banner = { tone: "danger", message: "Cookies have expired — re-import them in Settings." };
    } else if (cookies.present && !cookies.authenticated) {
      banner = { tone: "danger", message: "Cookies look unauthenticated — sign in and re-export." };
    } else if (!cookies.present) {
      banner = { tone: "warning", message: "No cookies configured — gated videos may fail." };
    } else if (cookies.expiring_soon) {
      banner = { tone: "warning", message: `Cookies expire in ${cookies.days_left?.toFixed(1)} days.` };
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-sm focus:border focus:border-border focus:bg-surface focus:px-3 focus:py-2 focus:text-body focus:text-text focus:shadow-overlay"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-surface">
        <div className="mx-auto flex h-14 w-full max-w-[1200px] items-center gap-6 px-6">
          <Link
            to="/"
            className="flex items-center gap-2 text-text"
            aria-label="Clipper home"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-sm bg-accent text-white">
              <Scissors className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="text-body font-semibold tracking-tight">Clipper</span>
          </Link>

          <nav className="flex items-center gap-1" aria-label="Primary">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "inline-flex h-8 items-center rounded-sm px-2.5 text-body font-medium transition-colors duration-150 ease-out",
                    isActive
                      ? "bg-surface-2 text-text"
                      : "text-muted hover:bg-surface-2 hover:text-text",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1.5">
            <JobIndicator />
            <CookieHealthDot />
            <Tooltip content={theme === "dark" ? "Light mode" : "Dark mode"} side="bottom">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggle}
                aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              >
                {theme === "dark" ? (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            </Tooltip>
          </div>
        </div>

        {banner ? (
          <div
            role="alert"
            className={cn(
              "border-t px-6 py-2 text-label",
              banner.tone === "danger"
                ? "border-danger/30 bg-danger/10 text-danger"
                : "border-warning/30 bg-warning/10 text-warning",
            )}
          >
            <div className="mx-auto flex max-w-[1200px] items-center gap-2">
              <span className="min-w-0 flex-1 truncate">{banner.message}</span>
              <Link to="/settings" className="font-medium underline underline-offset-2">
                Open Settings
              </Link>
            </div>
          </div>
        ) : null}
      </header>

      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
