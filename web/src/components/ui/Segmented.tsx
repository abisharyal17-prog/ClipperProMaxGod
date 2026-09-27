import { useRef } from "react";
import type { KeyboardEvent } from "react";

import { cn } from "../../lib/cn";

export interface SegmentedOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SegmentedProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  size?: "sm" | "md";
  className?: string;
  "aria-label"?: string;
}

const NAV_KEYS = new Set(["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "Home", "End"]);

/** A compact segmented control for mutually exclusive, low-stakes choices. */
export function Segmented({
  options,
  value,
  onChange,
  size = "md",
  className,
  "aria-label": ariaLabel,
}: SegmentedProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!NAV_KEYS.has(event.key)) return;
    const enabled = options.filter((option) => !option.disabled);
    if (enabled.length === 0) return;
    const currentIndex = enabled.findIndex((option) => option.value === value);
    const from = currentIndex === -1 ? 0 : currentIndex;
    let nextIndex = from;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = (from + 1) % enabled.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = (from - 1 + enabled.length) % enabled.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else {
      nextIndex = enabled.length - 1;
    }
    event.preventDefault();
    const next = enabled[nextIndex];
    onChange(next.value);
    listRef.current
      ?.querySelector<HTMLButtonElement>(`[data-value="${CSS.escape(next.value)}"]`)
      ?.focus();
  };

  return (
    <div
      ref={listRef}
      role="radiogroup"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-sm border border-border bg-surface-2 p-0.5",
        className,
      )}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            data-value={option.value}
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            disabled={option.disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex items-center justify-center rounded-sm font-medium transition-colors duration-150 ease-out",
              "disabled:cursor-not-allowed disabled:opacity-50",
              size === "sm" ? "h-7 px-2.5 text-label" : "h-8 px-3 text-body",
              active ? "bg-surface text-text" : "text-muted hover:text-text",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
