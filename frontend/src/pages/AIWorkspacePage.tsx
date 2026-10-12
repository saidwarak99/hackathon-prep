import React, { useState } from 'react';
import {
  TrendingUp,
  UtensilsCrossed,
  MessageSquareHeart,
  PackageCheck,
  Lightbulb,
  Sparkles,
  Database,
  Info,
} from 'lucide-react';
import { AgentChatBox, AgentMode } from '../components/agents/AgentChatBox';
import { useDataset } from '../context/DatasetContext';
import { Badge } from '../components/common/Badge';

export const AIWorkspacePage: React.FC = () => {
  const { selectedDatasetId, restaurantId } = useDataset();
  const [activeMode, setActiveMode] = useState<AgentMode>('unified');

  const agentsList: Array<{
    mode: AgentMode;
    name: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    accentColor: string;
    endpoint: string;
    datasetSupported: boolean;
  }> = [
    {
      mode: 'unified',
      name: 'Unified Orchestrator',
      description: 'Routes queries dynamically across all 6 specialized agents, cross-referencing multi-domain evidence.',
      icon: Sparkles,
      accentColor: 'text-terracotta-600 bg-terracotta-50 border-sand',
      endpoint: 'POST /api/chat',
      datasetSupported: true,
    },
    {
      mode: 'sales',
      name: 'Sales Intelligence',
      description: 'Shift sales, period-over-period comparisons, average order values, and hourly order velocity.',
      icon: TrendingUp,
      accentColor: 'text-forest-700 bg-forest-50 border-forest-200',
      endpoint: 'POST /api/agents/sales/chat',
      datasetSupported: false,
    },
    {
      mode: 'menu',
      name: 'Menu Intelligence',
      description: 'Item sales volumes, bottom sellers, category breakdown, dietary classification, and price analysis.',
      icon: UtensilsCrossed,
      accentColor: 'text-purple-700 bg-purple-50 border-purple-200',
      endpoint: 'POST /api/agents/menu/chat',
      datasetSupported: false,
    },
    {
      mode: 'feedback',
      name: 'Feedback Intelligence',
      description: 'Customer review sentiment analysis, star rating distribution, and recurring operational complaints.',
      icon: MessageSquareHeart,
      accentColor: 'text-maroon-700 bg-maroon-50 border-maroon-200',
      endpoint: 'POST /api/agents/feedback/chat',
      datasetSupported: false,
    },
    {
      mode: 'inventory',
      name: 'Inventory & Waste',
      description: 'Stock health checks, safety reorder alerts, ingredient movement, and waste variance tracking.',
      icon: PackageCheck,
      accentColor: 'text-saffron-700 bg-saffron-50 border-saffron-200',
      endpoint: 'POST /api/agents/inventory/chat',
      datasetSupported: false,
    },
    {
      mode: 'recommendations',
      name: 'Decision & Recommendation',
      description: 'Cross-functional synthesis generating prioritized business recommendations based on real data.',
      icon: Lightbulb,
      accentColor: 'text-terracotta-700 bg-terracotta-50 border-sand',
      endpoint: 'POST /api/agents/recommendations/chat',
      datasetSupported: false,
    },
  ];

  return (
    <div className="space-y-6 h-[calc(100vh-140px)] flex flex-col">
      {/* Top Agent Grid Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 shrink-0">
        {agentsList.map((ag) => {
          const Icon = ag.icon;
          const isSelected = activeMode === ag.mode;
          return (
            <button
              key={ag.mode}
              onClick={() => setActiveMode(ag.mode)}
              className={`p-3.5 rounded-2xl text-left border transition-all heritage-card flex flex-col justify-between ${
                isSelected
                  ? 'border-terracotta-500 bg-ivory ring-2 ring-terracotta-500/20 shadow-heritage-lg'
                  : 'hover:border-saffron-300 hover:bg-sandalwood/30'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`p-1.5 rounded-xl border ${ag.accentColor}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                {ag.datasetSupported ? (
                  <Badge variant="purple" size="sm">Dataset Scoped</Badge>
                ) : (
                  <span className="text-[10px] text-muted-brown font-mono font-medium">Baseline Only</span>
                )}
              </div>
              <div>
                <h4 className="text-xs font-bold text-maroon-900 font-serif truncate">{ag.name}</h4>
                <p className="text-[10px] text-muted-brown font-mono mt-0.5 truncate">{ag.endpoint}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Dataset Context Bar */}
      <div className="px-5 py-3 rounded-2xl heritage-card flex items-center justify-between text-xs shrink-0">
        <div className="flex items-center gap-2.5">
          <Database className="w-4 h-4 text-terracotta-500" />
          <span className="text-ink font-semibold">Active Scoping Context:</span>
          {selectedDatasetId ? (
            <Badge variant="purple" size="sm">
              Dataset ID: {selectedDatasetId} (Scoped to Unified Router)
            </Badge>
          ) : (
            <Badge variant="synthetic" size="sm">
              Synthetic Baseline Database (Default Restaurant)
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-muted-brown text-[11px]">
          <Info className="w-3.5 h-3.5 text-muted-brown" />
          <span>Tenant: <strong className="text-maroon-900 font-mono">{restaurantId}</strong></span>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="flex-1 min-h-0">
        <AgentChatBox
          key={activeMode}
          initialMode={activeMode}
          allowAgentSwitch={true}
          placeholder={`Inquire with ${
            agentsList.find((a) => a.mode === activeMode)?.name || 'Agent'
          }...`}
        />
      </div>
    </div>
  );
};
