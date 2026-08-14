"use client";

import { Check, ChevronDown, type LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";

export type FriendlySelectOption = { value: string; label: string };

export function FriendlySelect({
  value,
  options,
  onChange,
  icon: Icon,
  ariaLabel,
  className = "",
  disabled = false,
}: {
  value: string;
  options: FriendlySelectOption[];
  onChange: (value: string) => void;
  icon?: LucideIcon;
  ariaLabel: string;
  className?: string;
  disabled?: boolean;
}) {
  const root = useRef<HTMLDetailsElement>(null);
  const current = options.find((option) => option.value === value) || options[0];

  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) root.current.open = false;
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  return (
    <details
      ref={root}
      className={`friendly-select ${className}`}
      onKeyDown={(event) => { if (event.key === "Escape" && root.current) root.current.open = false; }}
    >
      <summary aria-label={ariaLabel} aria-disabled={disabled} onClick={(event) => { if (disabled) event.preventDefault(); }}>
        {Icon && <Icon size={15} />}
        <span>{current?.label}</span>
        <ChevronDown size={13} className="friendly-select-chevron" />
      </summary>
      <div className="friendly-select-menu" role="listbox" aria-label={ariaLabel}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="option"
            aria-selected={option.value === value}
            className={option.value === value ? "active" : ""}
            onClick={() => { onChange(option.value); if (root.current) root.current.open = false; }}
          >
            <span>{option.label}</span>
            {option.value === value && <Check size={14} />}
          </button>
        ))}
      </div>
    </details>
  );
}
