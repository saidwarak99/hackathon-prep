import React from 'react';

export type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'purple' | 'synthetic';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
}) => {
  const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-forest-50 text-forest-700 border-forest-200',
    warning: 'bg-saffron-50 text-saffron-700 border-saffron-200',
    error: 'bg-maroon-50 text-maroon-700 border-maroon-200',
    info: 'bg-stone-100 text-stone-700 border-stone-200',
    neutral: 'bg-sand/30 text-ink/80 border-sand',
    purple: 'bg-purple-50 text-purple-800 border-purple-200',
    synthetic: 'bg-saffron-50 text-saffron-700 border-saffron-300 ring-1 ring-saffron-400/20',
  };

  const sizeStyles = {
    sm: 'text-[11px] px-2 py-0.5 tracking-wide font-medium',
    md: 'text-xs px-2.5 py-1 font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border shadow-sm ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  );
};
