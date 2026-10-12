import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'Service Notice',
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`rounded-2xl border border-maroon-200 bg-maroon-50/90 p-4 text-maroon-900 shadow-heritage-sm ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-terracotta-500 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h4 className="text-xs font-bold text-maroon-900 font-serif tracking-normal">{title}</h4>
          <p className="mt-1 text-xs text-maroon-800/90 whitespace-pre-line break-words leading-relaxed font-sans">
            {message}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-maroon-700 hover:bg-maroon-800 text-ivory transition-colors shadow-sm"
            >
              <RefreshCw className="w-3 h-3" />
              Retry Connection
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
