import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Retrieving restaurant intelligence...',
  size = 'md',
  className = '',
}) => {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
  };

  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
      <div className="relative mb-3">
        <Loader2 className={`${sizeMap[size]} text-terracotta-500 animate-spin`} />
      </div>
      {message && (
        <p className="text-xs font-semibold text-muted-brown tracking-wide font-sans">{message}</p>
      )}
    </div>
  );
};
