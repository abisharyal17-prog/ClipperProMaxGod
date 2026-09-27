import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "../ui";
import type { ButtonSize } from "../ui";
import { useToast } from "../ui";

export interface CopyButtonProps {
  text: string;
  label?: string;
  size?: ButtonSize;
  disabled?: boolean;
}

export function CopyButton({ text, label = "Copy", size = "sm", disabled = false }: CopyButtonProps) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Copied to clipboard");
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Clipboard is unavailable");
    }
  };

  return (
    <Button
      variant="secondary"
      size={size}
      disabled={disabled}
      onClick={() => void copy()}
      leftIcon={
        copied ? (
          <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" />
        ) : (
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
        )
      }
    >
      {copied ? "Copied" : label}
    </Button>
  );
}
