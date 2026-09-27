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
}

export function Tabs({ items, value, onChange, className }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const enabled = items.filter((item) => !item.disabled);
    if (enabled.length === 0) return;
    const currentIndex = enabled.findIndex((item) => item.value === value);
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (currentIndex + delta + enabled.length) % enabled.length;
    event.preventDefault();
    onChange(enabled[nextIndex].value);
    const next = listRef.current?.querySelector<HTMLButtonElement>(
      `[data-tab="${CSS.escape(enabled[nextIndex].value)}"]`,
    );
    next?.focus();
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
            data-tab={item.value}
            role="tab"
            type="button"
            aria-selected={active}
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
