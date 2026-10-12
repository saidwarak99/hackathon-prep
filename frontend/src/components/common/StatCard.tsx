import React from 'react';
import { LucideIcon, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { Badge } from './Badge';

interface StatCardProps {
  title: string;
  value: string | number;
  subvalue?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  isSynthetic?: boolean;
  isPlaceholder?: boolean;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subvalue,
  trend,
  trendValue,
  icon: Icon,
  iconColor = 'text-terracotta-600',
  iconBg = 'bg-terracotta-50',
  isSynthetic = false,
  isPlaceholder = false,
  className = '',
}) => {
  return (
    <div
      className={`relative overflow-hidden heritage-card heritage-card-hover engraved-border-top p-5 flex flex-col justify-between ${className}`}
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-muted-brown">
            {title}
          </span>
          <div className={`p-2.5 rounded-xl border border-sand/80 shadow-sm ${iconBg} ${iconColor}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>

        <div className="mt-3">
          <div className="text-2xl lg:text-3xl font-extrabold tracking-tight text-maroon-900 font-mono tabular-nums">
            {value}
          </div>
          {(subvalue || trendValue) && (
            <div className="mt-2 flex items-center gap-2 text-xs">
              {trend && trendValue && (
                <span
                  className={`inline-flex items-center gap-0.5 font-bold ${
                    trend === 'up'
                      ? 'text-forest-600'
                      : trend === 'down'
                      ? 'text-maroon-600'
                      : 'text-muted-brown'
                  }`}
                >
                  {trend === 'up' && <ArrowUpRight className="w-3.5 h-3.5" />}
                  {trend === 'down' && <ArrowDownRight className="w-3.5 h-3.5" />}
                  {trendValue}
                </span>
              )}
              {subvalue && <span className="text-muted-brown truncate">{subvalue}</span>}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-sand/60 flex items-center justify-between">
        {isSynthetic && (
          <Badge variant="synthetic" size="sm">
            Synthetic Baseline
          </Badge>
        )}
        {isPlaceholder && (
          <Badge variant="warning" size="sm">
            Design Placeholder
          </Badge>
        )}
      </div>
    </div>
  );
};
