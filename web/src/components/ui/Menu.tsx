import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

import { cn } from "../../lib/cn";

export interface MenuItem {
  label: string;
  onSelect: () => void;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
}

export interface MenuProps {
  items: MenuItem[];
  ariaLabel: string;
  triggerIcon?: ReactNode;
  align?: "left" | "right";
  className?: string;
}

export function Menu({ items, ariaLabel, triggerIcon, align = "right", className }: MenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    window.requestAnimationFrame(() => {
      menuItems()[0]?.focus();
    });
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const menuItems = (): HTMLButtonElement[] => {
    if (!menuRef.current) return [];
    return Array.from(
      menuRef.current.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not([disabled])'),
    );
  };

  const onMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (
      event.key !== "ArrowDown" &&
      event.key !== "ArrowUp" &&
      event.key !== "Home" &&
      event.key !== "End"
    ) {
      return;
    }
    const items = menuItems();
    if (items.length === 0) return;
    event.preventDefault();
    const active = document.activeElement;
    const index = items.findIndex((item) => item === active);
    let nextIndex: number;
    if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = items.length - 1;
    else if (event.key === "ArrowUp") nextIndex = index <= 0 ? items.length - 1 : index - 1;
    else nextIndex = index === -1 || index === items.length - 1 ? 0 : index + 1;
    items[nextIndex]?.focus();
  };

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-7 w-7 items-center justify-center rounded-sm border border-transparent text-muted transition-colors duration-150 ease-out hover:bg-surface-2 hover:text-text"
      >
        {triggerIcon ?? <MoreHorizontal className="h-4 w-4" aria-hidden="true" />}
      </button>
      {open ? (
        <div
          ref={menuRef}
          role="menu"
          onKeyDown={onMenuKeyDown}
          className={cn(
            "absolute z-30 mt-1 min-w-[10rem] rounded-lg border border-border bg-surface p-1 shadow-overlay motion-safe:animate-pop-in",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className={cn(
                "flex w-full items-center gap-2 rounded-sm px-2.5 py-1.5 text-left text-body transition-colors duration-150 ease-out",
                "disabled:cursor-not-allowed disabled:opacity-50",
                item.danger
                  ? "text-danger hover:bg-danger/10"
                  : "text-text hover:bg-surface-2",
              )}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
