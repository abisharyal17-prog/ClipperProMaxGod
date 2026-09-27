import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

import { cn } from "../../lib/cn";

export type ToastTone = "info" | "success" | "error" | "warning";

export interface ToastOptions {
  tone?: ToastTone;
  description?: string;
  duration?: number;
}

interface ToastItem extends Required<Pick<ToastOptions, "tone" | "duration">> {
  id: number;
  message: string;
  description?: string;
}

export interface ToastApi {
  push: (message: string, options?: ToastOptions) => void;
  success: (message: string, options?: Omit<ToastOptions, "tone">) => void;
  error: (message: string, options?: Omit<ToastOptions, "tone">) => void;
  info: (message: string, options?: Omit<ToastOptions, "tone">) => void;
  warning: (message: string, options?: Omit<ToastOptions, "tone">) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONES: Record<ToastTone, { color: string; icon: ReactNode }> = {
  info: { color: "text-muted", icon: <Info className="h-4 w-4" aria-hidden="true" /> },
  success: { color: "text-success", icon: <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> },
  error: { color: "text-danger", icon: <XCircle className="h-4 w-4" aria-hidden="true" /> },
  warning: { color: "text-warning", icon: <AlertTriangle className="h-4 w-4" aria-hidden="true" /> },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (message: string, options?: ToastOptions) => {
      counter.current += 1;
      const id = counter.current;
      const item: ToastItem = {
        id,
        message,
        description: options?.description,
        tone: options?.tone ?? "info",
        duration: options?.duration ?? 4000,
      };
      setToasts((prev) => [...prev, item].slice(-4));
      if (item.duration > 0) {
        window.setTimeout(() => remove(id), item.duration);
      }
    },
    [remove],
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (message, options) => push(message, { ...options, tone: "success" }),
      error: (message, options) => push(message, { ...options, tone: "error" }),
      info: (message, options) => push(message, { ...options, tone: "info" }),
      warning: (message, options) => push(message, { ...options, tone: "warning" }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => {
          const tone = TONES[toast.tone];
          return (
            <div
              key={toast.id}
              role="status"
              className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-surface p-3 shadow-overlay motion-safe:animate-pop-in"
            >
              <span className={cn("mt-0.5", tone.color)}>{tone.icon}</span>
              <div className="min-w-0 flex-1">
                <p className="text-body font-medium text-text">{toast.message}</p>
                {toast.description ? (
                  <p className="mt-0.5 break-words text-label text-muted">{toast.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => remove(toast.id)}
                aria-label="Dismiss notification"
                className="text-muted transition-colors duration-150 hover:text-text"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
