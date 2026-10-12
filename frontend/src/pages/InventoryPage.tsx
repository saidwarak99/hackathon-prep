import React, { useState, useEffect } from 'react';
import {
  PackageCheck,
  AlertTriangle,
  Boxes,
  RefreshCw,
  Bot,
  Search,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { InventoryResponse, InventoryItem } from '../api/types';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { AgentChatBox } from '../components/agents/AgentChatBox';
import { formatIndianNumber } from '../utils/formatters';

export const InventoryPage: React.FC = () => {
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [lowStockOnly, setLowStockOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showInventoryAgent, setShowInventoryAgent] = useState<boolean>(false);

  const fetchInventory = async (lowOnly: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getInventory(lowOnly);
      setInventory(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load inventory stock records.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory(lowStockOnly);
  }, [lowStockOnly]);

  const itemsList: Array<{ id: string; data: InventoryItem }> = inventory
    ? Object.entries(inventory.items).map(([id, data]) => ({ id, data }))
    : [];

  const filteredItems = itemsList.filter(({ data }) =>
    data.item_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    data.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Top Controls & Banner */}
      <div className="p-5 rounded-2xl heritage-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-xl bg-saffron-50 text-saffron-700 border border-saffron-200">
              <PackageCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
                Pantry Inventory & Waste Variance
                <Badge variant="synthetic" size="sm">
                  Synthetic Baseline
                </Badge>
              </h2>
              <p className="text-xs text-muted-brown">
                Live ingredient stock counts and automated replenishment reorder thresholds
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchInventory(lowStockOnly)}
              disabled={loading}
              className="p-2.5 rounded-xl bg-ivory hover:bg-sandalwood text-maroon-800 border border-sand transition-colors shadow-heritage-sm"
              title="Refresh stock levels"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={() => setShowInventoryAgent(!showInventoryAgent)}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md ${
                showInventoryAgent
                  ? 'bg-maroon-800 text-ivory shadow-maroon-900/20'
                  : 'bg-terracotta-500 text-ivory hover:bg-terracotta-600 shadow-terracotta-500/20'
              }`}
            >
              <Bot className="w-4 h-4" />
              {showInventoryAgent ? 'Hide Inventory Agent' : 'Ask Inventory Agent'}
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-sand">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setLowStockOnly(false)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                !lowStockOnly
                  ? 'bg-maroon-800 text-ivory shadow-sm'
                  : 'bg-sandalwood/70 text-muted-brown hover:text-maroon-900 border border-sand'
              }`}
            >
              All Pantry Items ({inventory?.total_items ?? 0})
            </button>
            <button
              onClick={() => setLowStockOnly(true)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
                lowStockOnly
                  ? 'bg-maroon-700 text-ivory shadow-sm'
                  : 'bg-maroon-50 text-maroon-700 hover:bg-maroon-100 border border-maroon-200'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Low Stock Only ({inventory?.low_stock_items_count ?? 0})
            </button>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-brown absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search ingredient or pantry category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3.5 py-1.5 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink placeholder-muted-brown focus:outline-none focus:border-terracotta-500 w-64"
            />
          </div>
        </div>
      </div>

      {error && <ErrorAlert title="Inventory Notice" message={error} onRetry={() => fetchInventory(lowStockOnly)} />}

      {/* Embedded Inventory Agent Drawer */}
      {showInventoryAgent && (
        <div className="h-96">
          <AgentChatBox
            initialMode="inventory"
            allowAgentSwitch={false}
            placeholder="Ask Inventory Agent about stock levels, burn rate, dairy expiration, or waste variance..."
            suggestedPrompts={[
              'Which ingredients need to be reordered today?',
              'What is the stock burn rate for dairy and dry spices?',
              'Calculate potential waste variance for perishable items.',
            ]}
          />
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Tracked Pantry Items"
          value={formatIndianNumber(inventory?.total_items ?? 0)}
          subvalue="Active raw materials & ingredients"
          icon={Boxes}
          iconColor="text-maroon-700"
          iconBg="bg-maroon-50"
          isSynthetic={true}
        />
        <StatCard
          title="Low Stock Alerts"
          value={formatIndianNumber(inventory?.low_stock_items_count ?? 0)}
          subvalue="Below minimum reorder threshold"
          icon={AlertTriangle}
          iconColor={inventory?.low_stock_items_count ? 'text-maroon-600' : 'text-forest-600'}
          iconBg={inventory?.low_stock_items_count ? 'bg-maroon-50' : 'bg-forest-50'}
          trend={inventory?.low_stock_items_count ? 'down' : 'up'}
          trendValue={inventory?.low_stock_items_count ? 'Restock Needed' : 'Nominal'}
          isSynthetic={true}
        />
        <StatCard
          title="Replenishment Status"
          value={inventory?.low_stock_items_count === 0 ? 'Adequately Stocked' : 'PO Pending'}
          subvalue="Verified via inventory ledger"
          icon={PackageCheck}
          iconColor="text-forest-600"
          iconBg="bg-forest-50"
          isSynthetic={true}
        />
      </div>

      {/* Stock Levels Table */}
      {loading && !inventory ? (
        <LoadingSpinner message="Auditing ingredient stock levels and unit measures..." />
      ) : (
        <div className="heritage-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-maroon-900 font-serif">Pantry Stock Ledger</h3>
              <p className="text-xs text-muted-brown">Current on-hand balances vs minimum reorder thresholds</p>
            </div>
            <Badge variant="neutral" size="sm">
              Showing {filteredItems.length} items
            </Badge>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-sand text-muted-brown font-bold uppercase tracking-wider text-[10px]">
                  <th className="pb-3 pl-2">Ingredient Name</th>
                  <th className="pb-3">Category</th>
                  <th className="pb-3 text-right">Current Stock</th>
                  <th className="pb-3 text-right">Min Reorder Level</th>
                  <th className="pb-3 text-center">Health Status</th>
                  <th className="pb-3 text-right pr-2">Last Audit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand/60">
                {filteredItems.length > 0 ? (
                  filteredItems.map(({ id, data }) => {
                    const isLow = data.current_stock <= data.min_reorder_level;
                    return (
                      <tr key={id} className="hover:bg-sandalwood/40 transition-colors">
                        <td className="py-3.5 pl-2 font-bold text-ink">
                          {data.item_name}
                          <span className="block text-[10px] text-muted-brown font-mono">ID: {id}</span>
                        </td>
                        <td className="py-3.5 text-muted-brown font-medium">{data.category}</td>
                        <td className="py-3.5 text-right font-mono font-bold">
                          <span className={isLow ? 'text-maroon-600 font-extrabold' : 'text-forest-700'}>
                            {data.current_stock}
                          </span>{' '}
                          <span className="text-muted-brown text-[10px] font-normal">{data.unit}</span>
                        </td>
                        <td className="py-3.5 text-right font-mono text-muted-brown">
                          {data.min_reorder_level} {data.unit}
                        </td>
                        <td className="py-3.5 text-center">
                          {isLow ? (
                            <Badge variant="error" size="sm">
                              Low Stock
                            </Badge>
                          ) : (
                            <Badge variant="success" size="sm">
                              Adequate
                            </Badge>
                          )}
                        </td>
                        <td className="py-3.5 text-right pr-2 text-muted-brown font-mono text-[11px]">
                          {data.last_count_date || 'N/A'}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-brown">
                      No pantry records match the selected filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
