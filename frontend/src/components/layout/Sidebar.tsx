import React from 'react';
import {
  LayoutDashboard,
  Bot,
  TrendingUp,
  UtensilsCrossed,
  MessageSquareHeart,
  PackageCheck,
  Lightbulb,
  BookOpen,
  Database,
  ShieldCheck,
  AlertCircle,
} from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';

export type PageId =
  | 'overview'
  | 'workspace'
  | 'sales'
  | 'menu'
  | 'feedback'
  | 'inventory'
  | 'recommendations'
  | 'knowledge'
  | 'datasets';

interface SidebarProps {
  activePage: PageId;
  onSelectPage: (page: PageId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activePage, onSelectPage }) => {
  const { isBackendConnected, backendHealth } = useDataset();

  const navItems: Array<{
    id: PageId;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    tag?: string;
  }> = [
    { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
    { id: 'workspace', label: 'AI Workspace', icon: Bot, tag: '6 Agents' },
    { id: 'sales', label: 'Sales Intelligence', icon: TrendingUp },
    { id: 'menu', label: 'Menu Intelligence', icon: UtensilsCrossed },
    { id: 'feedback', label: 'Customer Feedback', icon: MessageSquareHeart },
    { id: 'inventory', label: 'Inventory & Waste', icon: PackageCheck },
    { id: 'recommendations', label: 'Recommendations', icon: Lightbulb, tag: 'Actionable' },
    { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen, tag: 'RAG' },
    { id: 'datasets', label: 'Dataset Ingestion', icon: Database },
  ];

  return (
    <aside className="w-64 shrink-0 flex flex-col h-screen sticky top-0 bg-[#4D151A] text-ivory border-r border-[#380E13] z-20 shadow-heritage-lg">
      {/* Brand Header */}
      <div className="h-20 px-6 flex items-center gap-3 border-b border-[#380E13]/80 bg-[#401115]">
        <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-saffron-400 to-terracotta-500 flex items-center justify-center shadow-md text-maroon-900 font-serif font-black text-xl border border-saffron-200">
          <svg className="w-5 h-5 text-maroon-900" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L14.4 7.2L20 8.3L16 12.2L17 17.8L12 15.2L7 17.8L8 12.2L4 8.3L9.6 7.2L12 2Z" />
          </svg>
        </div>
        <div>
          <div className="font-serif font-extrabold text-base tracking-tight text-ivory flex items-center gap-1">
            RASA<span className="text-saffron-400 font-sans font-black text-sm">IQ</span>
          </div>
          <p className="text-[10px] text-sand/80 font-medium tracking-wider uppercase">
            Hospitality Intelligence
          </p>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto px-3 py-5 space-y-1">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-sand/60">
          Core Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectPage(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all group ${
                isActive
                  ? 'bg-sandalwood text-maroon-900 font-bold shadow-heritage border border-sand/80'
                  : 'text-[#F8E4E5]/80 hover:text-white hover:bg-white/10'
              }`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <Icon
                  className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? 'text-terracotta-500' : 'text-[#F8E4E5]/70 group-hover:text-saffron-400'
                  }`}
                />
                <span className="truncate">{item.label}</span>
              </div>
              {item.tag && (
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-md font-semibold shrink-0 ${
                    isActive
                      ? 'bg-terracotta-100 text-terracotta-700'
                      : 'bg-white/10 text-saffron-200'
                  }`}
                >
                  {item.tag}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Database & System Health Badge */}
      <div className="p-4 border-t border-[#380E13] bg-[#3B0F13]">
        <div className="p-3 rounded-xl bg-[#2D0A0E] border border-white/5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-medium text-sand/90">FastAPI & Supabase</span>
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  isBackendConnected ? 'bg-forest-500 animate-pulse' : 'bg-terracotta-400'
                }`}
              />
              <span className="text-[10px] font-bold uppercase tracking-wider text-sand/80">
                {isBackendConnected ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-sand/70 truncate">
            {isBackendConnected ? (
              <>
                <ShieldCheck className="w-3.5 h-3.5 text-forest-400 shrink-0" />
                <span className="truncate">{backendHealth?.server_version || 'PostgreSQL connected'}</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-3.5 h-3.5 text-terracotta-400 shrink-0" />
                <span>Backend unreachable</span>
              </>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
};
