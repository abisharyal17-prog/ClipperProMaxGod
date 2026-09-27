import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface TooltipProps {
  content: ReactNode;
  side?: "top" | "bottom";
  className?: string;
  children: ReactNode;
}

function mergeDescribedBy(existing: string | undefined, id: string): string {
  return existing ? `${existing} ${id}` : id;
}

/** CSS-driven tooltip: appears on hover and keyboard focus within. */
export function Tooltip({ content, side = "bottom", className, children }: TooltipProps) {
  const id = useId();

  // Put the description on the focusable child, not a non-focusable wrapper, so
  // assistive tech actually announces it.
  const child = isValidElement(children)
    ? cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, {
        "aria-describedby": mergeDescribedBy(
          (children.props as { "aria-describedby"?: string })["aria-describedby"],
          id,
        ),
      })
    : children;

  return (
    <span className="group/tooltip relative inline-flex">
      <span className="inline-flex">{child}</span>
      <span
        role="tooltip"
        id={id}
        className={cn(
          "pointer-events-none absolute left-1/2 z-50 w-max max-w-[16rem] -translate-x-1/2 rounded-sm border border-border bg-surface px-2 py-1 text-label text-text opacity-0 shadow-overlay",
          "transition-opacity duration-150 ease-out",
          "group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100",
          side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5",
          className,
        )}
      >
        {content}
      </span>
    </span>
  );
}
