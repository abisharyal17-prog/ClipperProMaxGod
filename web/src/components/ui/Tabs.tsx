import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface TabItem {
  value: string;
  label: string;
  icon?: ReactNode;
  badge?: ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
  /** Id prefix so the tab list and its panel can reference each other. */
  idPrefix?: string;
}

export function Tabs({ items, value, onChange, className, idPrefix = "tab" }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const focusTab = (tabValue: string) => {
    listRef.current
      ?.querySelector<HTMLButtonElement>(`[data-tab="${CSS.escape(tabValue)}"]`)
      ?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const keys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const enabled = items.filter((item) => !item.disabled);
    if (enabled.length === 0) return;
    const currentIndex = enabled.findIndex((item) => item.value === value);
    const from = currentIndex === -1 ? 0 : currentIndex;
    let nextIndex = from;
    if (event.key === "ArrowRight") nextIndex = (from + 1) % enabled.length;
    else if (event.key === "ArrowLeft") nextIndex = (from - 1 + enabled.length) % enabled.length;
    else if (event.key === "Home") nextIndex = 0;
    else nextIndex = enabled.length - 1;
    event.preventDefault();
    const next = enabled[nextIndex];
    onChange(next.value);
    focusTab(next.value);
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      onKeyDown={onKeyDown}
      className={cn("flex items-center gap-1 border-b border-border", className)}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            id={`${idPrefix}-${item.value}`}
            data-tab={item.value}
            role="tab"
            type="button"
            aria-selected={active}
            aria-controls={active ? `${idPrefix}-${item.value}-panel` : undefined}
            tabIndex={active ? 0 : -1}
            disabled={item.disabled}
            onClick={() => onChange(item.value)}
            className={cn(
              "relative -mb-px inline-flex h-10 items-center gap-2 border-b-2 px-3.5 text-body font-medium",
              "transition-colors duration-150 ease-out",
              active
                ? "border-accent text-text"
                : "border-transparent text-muted hover:border-border hover:text-text",
              item.disabled && "cursor-not-allowed opacity-50",
            )}
          >
            {item.icon}
            {item.label}
            {item.badge}
          </button>
        );
      })}
    </div>
  );
}
