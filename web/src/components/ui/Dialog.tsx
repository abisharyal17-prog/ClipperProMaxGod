import { useCallback, useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";

import { cn } from "../../lib/cn";
import { Button } from "./Button";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, description, children, footer, className }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Keep the latest onClose without re-running the focus trap on every render.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const focusables = useCallback((): HTMLElement[] => {
    if (!panelRef.current) return [];
    return Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    );
  }, []);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const frame = window.requestAnimationFrame(() => {
      const items = focusables();
      // Prefer an explicit opt-in, then the first form control, then any
      // focusable — never the header Close button by default.
      const preferred =
        panelRef.current?.querySelector<HTMLElement>("[data-autofocus]") ??
        items.find((el) => ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)) ??
        items[0] ??
        panelRef.current;
      preferred?.focus();
    });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey && (active === first || !panelRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus?.();
    };
  }, [open, focusables]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center">
      <div
        className="fixed inset-0 bg-black/50 motion-safe:animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cn(
          "relative z-10 my-8 w-full max-w-lg rounded-lg border border-border bg-surface shadow-overlay outline-none motion-safe:animate-pop-in",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="space-y-1">
            <h2 id={titleId} className="text-title text-text">
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="text-body text-muted">
                {description}
              </p>
            ) : null}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close dialog">
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
