import { forwardRef, useContext } from "react";
import type { SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "../../lib/cn";
import { FieldContext } from "./Input";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options?: SelectOption[];
  invalid?: boolean;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    className,
    options,
    invalid,
    placeholder,
    children,
    id,
    "aria-describedby": ariaDescribedBy,
    ...props
  },
  ref,
) {
  const field = useContext(FieldContext);
  const isInvalid = invalid ?? field?.invalid ?? false;
  return (
    <div className="relative">
      <select
        ref={ref}
        id={id ?? field?.id}
        aria-describedby={ariaDescribedBy ?? field?.describedBy}
        className={cn(
          "h-9 w-full appearance-none rounded-sm border border-border bg-surface-2 pl-3 pr-8 text-body text-text",
          "transition-colors duration-150 ease-out",
          "disabled:cursor-not-allowed disabled:opacity-50",
          isInvalid && "border-danger focus-visible:ring-danger",
          className,
        )}
        aria-invalid={isInvalid || undefined}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options?.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
        aria-hidden="true"
      />
    </div>
  );
});
