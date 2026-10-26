import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?:
    | "default"
    | "secondary"
    | "destructive"
    | "outline"
    | "success"
    | "warning"
    | "info";
}

function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  const baseStyles =
    "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";

  const variantStyles: Record<string, string> = {
    default:
      "border-transparent bg-primary text-primary-foreground",
    secondary:
      "border-transparent bg-secondary text-secondary-foreground",
    destructive:
      "border-red-200 bg-red-50 text-red-700",
    warning:
      "border-amber-200 bg-amber-50 text-amber-700",
    success:
      "border-emerald-200 bg-emerald-50 text-emerald-700",
    info:
      "border-blue-200 bg-blue-50 text-blue-700",
    outline: "border-border text-foreground",
  };

  return (
    <div
      className={cn(baseStyles, variantStyles[variant], className)}
      {...props}
    />
  );
}

export { Badge };
