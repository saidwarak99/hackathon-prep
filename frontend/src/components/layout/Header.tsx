import React from 'react';
import { Database, Building2, RefreshCw, CheckCircle2, AlertCircle, Store, LogOut } from 'lucide-react';
import { useDataset } from '../../context/DatasetContext';
import { PageId } from './Sidebar';

interface HeaderProps {
  activePage: PageId;
}

const pageTitles: Record<PageId, { title: string; subtitle: string }> = {
  overview: {
    title: 'Executive Overview',
    subtitle: 'Daily operational health, financial turnover, and autonomous intelligence.',
  },
  workspace: {
    title: 'AI Multi-Agent Workspace',
    subtitle: 'Cross-functional orchestration across Sales, Menu, Feedback, and Inventory agents.',
  },
  sales: {
    title: 'Sales Intelligence',
    subtitle: 'Shift turnover, average ticket size, rush hours, and settlement channels.',
  },
  menu: {
    title: 'Menu Intelligence',
    subtitle: 'Active recipe catalog, category performance, pricing, and dietary classification.',
  },
  feedback: {
    title: 'Customer Feedback Intelligence',
    subtitle: 'Guest reviews sentiment distribution and operational satisfaction drivers.',
  },
  inventory: {
    title: 'Inventory & Waste Intelligence',
    subtitle: 'Stock counts, safety replenishment levels, unit measures, and waste variance.',
  },
  recommendations: {
    title: 'Strategic Recommendations',
    subtitle: 'Data-driven business decisions for restaurant margin and service optimization.',
  },
  knowledge: {
    title: 'Knowledge Base & SOP Retrieval',
    subtitle: 'Semantic search over culinary SOPs, opening checklists, and operational manuals.',
  },
  datasets: {
    title: 'Dataset Ingestion & Management',
    subtitle: 'Dry-run preview and atomic ingestion for CSV and ZIP restaurant records.',
  },
};

export const Header: React.FC<HeaderProps> = ({ activePage }) => {
  const {
    selectedDatasetId,
    setSelectedDatasetId,
    restaurantId,
    setRestaurantId,
    restaurantName,
    exitDemoWorkspace,
    datasets,
    refreshDatasets,
    loadingDatasets,
    isBackendConnected,
  } = useDataset();

  const currentMeta = pageTitles[activePage] || {
    title: 'Restaurant Intelligence',
    subtitle: 'Hospitality Decision Platform',
  };

  return (
    <header className="h-20 px-8 border-b border-sand/80 bg-ivory/90 backdrop-blur-md flex items-center justify-between sticky top-0 z-10 shadow-heritage-sm">
      {/* Title & Subtitle */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-maroon-900 font-serif flex items-center gap-2">
          {currentMeta.title}
        </h1>
        <p className="text-xs text-muted-brown mt-0.5 font-sans">{currentMeta.subtitle}</p>
      </div>

      {/* Controls & Selectors */}
      <div className="flex items-center gap-3">
        {/* Active Restaurant Name & Switch Option */}
        <div className="flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-xl bg-gradient-to-r from-sandalwood via-ivory to-sandalwood border border-sand text-xs shadow-sm">
          <div className="w-5 h-5 rounded-lg bg-terracotta-100 text-terracotta-700 flex items-center justify-center">
            <Store className="w-3 h-3" />
          </div>
          <div className="flex flex-col">
            <span className="text-[9px] font-bold text-muted-brown uppercase tracking-wider leading-none">
              Restaurant
            </span>
            <span
              className="text-xs font-bold text-maroon-900 font-serif leading-tight max-w-[140px] truncate"
              title={restaurantName}
            >
              {restaurantName || 'Dakshin Heritage Cafe'}
            </span>
          </div>
          <button
            onClick={() => exitDemoWorkspace()}
            title="Switch Restaurant (Return to Demo Welcome Screen)"
            className="ml-1 p-1 rounded-lg text-muted-brown hover:text-maroon-900 hover:bg-sand/60 transition-colors flex items-center gap-1 text-[10px] font-bold cursor-pointer"
          >
            <LogOut className="w-3 h-3 text-terracotta-500" />
            <span className="hidden xl:inline text-muted-brown">Switch</span>
          </button>
        </div>

        {/* Restaurant Tenant Selector */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-sandalwood/70 border border-sand text-xs text-ink">
          <Building2 className="w-3.5 h-3.5 text-muted-brown" />
          <span className="text-[11px] font-semibold text-muted-brown">Tenant:</span>
          <input
            type="text"
            value={restaurantId}
            onChange={(e) => setRestaurantId(e.target.value)}
            className="bg-transparent text-maroon-900 font-bold text-xs focus:outline-none w-28 border-b border-dashed border-sand focus:border-terracotta-500"
            title="Restaurant Tenant ID"
          />
        </div>

        {/* Global Dataset Selector */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-sandalwood/70 border border-sand text-xs">
          <Database className="w-3.5 h-3.5 text-terracotta-500" />
          <span className="text-[11px] font-semibold text-muted-brown">Dataset:</span>
          <select
            value={selectedDatasetId || ''}
            onChange={(e) => setSelectedDatasetId(e.target.value || null)}
            className="bg-transparent text-maroon-900 font-bold text-xs focus:outline-none cursor-pointer pr-1"
          >
            <option value="" className="bg-ivory text-ink">
              Baseline (Default)
            </option>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id} className="bg-ivory text-maroon-800">
                {d.dataset_name || d.original_filename} ({d.row_count} rows)
              </option>
            ))}
          </select>
          <button
            onClick={() => refreshDatasets()}
            disabled={loadingDatasets}
            title="Refresh datasets"
            className="text-muted-brown hover:text-maroon-800 p-1 hover:bg-sand/40 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${loadingDatasets ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Live Connectivity Badge */}
        <div
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold border flex items-center gap-2 shadow-heritage-sm ${
            isBackendConnected
              ? 'bg-forest-50 border-forest-200 text-forest-700'
              : 'bg-maroon-50 border-maroon-200 text-maroon-700'
          }`}
        >
          {isBackendConnected ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-forest-600" />
          ) : (
            <AlertCircle className="w-3.5 h-3.5 text-maroon-600" />
          )}
          <span className="font-mono text-[11px]">
            {isBackendConnected ? 'API Connected' : 'API Offline'}
          </span>
        </div>
      </div>
    </header>
  );
};
