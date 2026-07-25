import type { ReactNode } from "react";

interface ButtonProps {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  onClick?: () => void;
  type?: "button" | "submit";
  className?: string;
  icon?: ReactNode;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  onClick,
  type = "button",
  className = "",
  icon,
}: ButtonProps) {
  const base = "ui-btn";
  const variantClass = `ui-btn--${variant}`;
  const sizeClass = `ui-btn--${size}`;
  return (
    <button
      type={type}
      className={`${base} ${variantClass} ${sizeClass} ${className}`}
      disabled={disabled}
      onClick={onClick}
    >
      {icon && <span className="ui-btn__icon">{icon}</span>}
      {children}
    </button>
  );
}
