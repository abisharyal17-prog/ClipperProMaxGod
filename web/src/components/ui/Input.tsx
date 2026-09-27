import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

const FIELD_BASE =
  "w-full rounded-sm border border-border bg-surface-2 px-3 text-body text-text placeholder:text-muted " +
  "transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid = false, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        FIELD_BASE,
        "h-9",
        invalid && "border-danger focus-visible:ring-danger",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid = false, rows = 5, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        FIELD_BASE,
        "py-2 font-mono text-mono leading-relaxed",
        invalid && "border-danger focus-visible:ring-danger",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
});

export interface FieldProps {
  label?: string;
  hint?: string;
  error?: string;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

export function Field({ label, hint, error, htmlFor, className, children }: FieldProps) {
  const generated = useId();
  const id = htmlFor ?? generated;
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={cn("space-y-1.5", className)}>
      {label ? (
        <label htmlFor={id} className="block text-label text-muted">
          {label}
        </label>
      ) : null}
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-label text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={describedBy} className="text-label text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
