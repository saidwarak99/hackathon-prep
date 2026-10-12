import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = Inbox,
  title,
  description,
  actionText,
  onAction,
  className = '',
}) => {
  return (
    <div
      className={`heritage-card flex flex-col items-center justify-center p-8 text-center ${className}`}
    >
      <div className="w-12 h-12 rounded-2xl bg-terracotta-50 flex items-center justify-center mb-3 text-terracotta-500 border border-sand">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-bold text-maroon-900 mb-1 font-serif">{title}</h3>
      <p className="text-xs text-muted-brown max-w-sm mb-4 leading-relaxed font-sans">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center px-4 py-2 rounded-xl text-xs font-bold bg-terracotta-500 hover:bg-terracotta-600 text-ivory transition-all shadow-md shadow-terracotta-500/20"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
