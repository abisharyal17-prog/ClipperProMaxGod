import { createContext, forwardRef, useContext, useId } from "react";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

const FIELD_BASE =
  "w-full rounded-sm border border-border bg-surface-2 px-3 text-body text-text placeholder:text-muted " +
  "transition-colors duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Lets {@link Field} wire its label, hint and error to the control it wraps
 * without the caller having to pass matching ids by hand. Controls read this
 * and apply `id` / `aria-describedby` / `aria-invalid` unless they set their own.
 */
export interface FieldA11y {
  id: string;
  describedBy?: string;
  invalid: boolean;
}

export const FieldContext = createContext<FieldA11y | null>(null);

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, id, "aria-describedby": ariaDescribedBy, ...props },
  ref,
) {
  const field = useContext(FieldContext);
  const isInvalid = invalid ?? field?.invalid ?? false;
  return (
    <input
      ref={ref}
      {...props}
      id={id ?? field?.id}
      aria-describedby={ariaDescribedBy ?? field?.describedBy}
      aria-invalid={isInvalid || undefined}
      className={cn(
        FIELD_BASE,
        "h-9",
        isInvalid && "border-danger focus-visible:ring-danger",
        className,
      )}
    />
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, id, "aria-describedby": ariaDescribedBy, rows = 5, ...props },
  ref,
) {
  const field = useContext(FieldContext);
  const isInvalid = invalid ?? field?.invalid ?? false;
  return (
    <textarea
      ref={ref}
      rows={rows}
      {...props}
      id={id ?? field?.id}
      aria-describedby={ariaDescribedBy ?? field?.describedBy}
      aria-invalid={isInvalid || undefined}
      className={cn(
        FIELD_BASE,
        "py-2 font-mono text-mono leading-relaxed",
        isInvalid && "border-danger focus-visible:ring-danger",
        className,
      )}
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
    <FieldContext.Provider value={{ id, describedBy, invalid: Boolean(error) }}>
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
    </FieldContext.Provider>
  );
}
