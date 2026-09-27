import type { HTMLAttributes, ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { cn } from "../../lib/cn";

export type AlertTone = "info" | "success" | "warning" | "danger";

export interface AlertProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  tone?: AlertTone;
  title?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

const TONES: Record<AlertTone, { wrap: string; icon: ReactNode }> = {
  info: {
    wrap: "border-border bg-surface-2 text-text",
    icon: <Info className="h-4 w-4 text-muted" aria-hidden="true" />,
  },
  success: {
    wrap: "border-success/30 bg-success/10 text-text",
    icon: <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />,
  },
  warning: {
    wrap: "border-warning/30 bg-warning/10 text-text",
    icon: <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />,
  },
  danger: {
    wrap: "border-danger/30 bg-danger/10 text-text",
    icon: <XCircle className="h-4 w-4 text-danger" aria-hidden="true" />,
  },
};

export function Alert({ tone = "info", title, actions, children, className, ...props }: AlertProps) {
  const config = TONES[tone];
  const role = tone === "danger" || tone === "warning" ? "alert" : "status";
  return (
    <div
      role={role}
      className={cn("flex items-start gap-3 rounded-md border px-3.5 py-3", config.wrap, className)}
      {...props}
    >
      <span className="mt-0.5 shrink-0">{config.icon}</span>
      <div className="min-w-0 flex-1 space-y-1">
        {title ? <p className="text-body font-medium text-text">{title}</p> : null}
        {children ? <div className="text-label text-muted">{children}</div> : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  );
}
