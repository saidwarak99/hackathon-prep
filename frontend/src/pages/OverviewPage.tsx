import React, { useEffect, useState } from 'react';
import {
  ShoppingBag,
  TrendingUp,
  Clock,
  AlertTriangle,
  Utensils,
  ChevronRight,
  RefreshCw,
  Sparkles,
  Award,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { SalesResponse, MenuResponse, InventoryResponse } from '../api/types';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { PageId } from '../components/layout/Sidebar';
import { formatINR, formatIndianNumber } from '../utils/formatters';

interface OverviewPageProps {
  onNavigate: (page: PageId) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [sales, setSales] = useState<SalesResponse | null>(null);
  const [menu, setMenu] = useState<MenuResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOverviewData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [salesData, menuData, inventoryData] = await Promise.all([
        apiClient.getSales().catch(() => null),
        apiClient.getMenu().catch(() => null),
        apiClient.getInventory(false).catch(() => null),
      ]);

      setSales(salesData);
      setMenu(menuData);
      setInventory(inventoryData);

      if (!salesData && !menuData && !inventoryData) {
        setError('Could not connect to backend restaurant API. Please verify FastAPI is running at http://localhost:8000.');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch overview data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverviewData();
  }, []);

  if (loading) {
    return <LoadingSpinner message="Synthesizing restaurant operational intelligence..." />;
  }

  const lowStockItems = inventory
    ? Object.entries(inventory.items).filter(([_, item]) => item.current_stock <= item.min_reorder_level)
    : [];

  const totalRev = sales?.summary?.total_revenue || 0;

  return (
    <div className="space-y-6">
      {/* Heritage Welcome Banner with subtle Jali Pattern */}
      <div className="p-6 rounded-2xl heritage-card engraved-border-top relative overflow-hidden bg-gradient-to-r from-ivory via-sandalwood/60 to-ivory flex flex-wrap items-center justify-between gap-4">
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-terracotta-50 border border-sand flex items-center justify-center text-terracotta-600 shadow-heritage-sm">
            <Award className="w-6 h-6 text-terracotta-600" />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-maroon-900 font-serif">
                Autonomous Restaurant Intelligence
              </h2>
              <Badge variant="synthetic" size="sm">
                Synthetic Baseline
              </Badge>
            </div>
            <p className="text-xs text-muted-brown">
              Active Shift Date: <span className="font-mono font-bold text-maroon-800">{sales?.date || 'Today'}</span> &bull; Shift Status: <span className="text-forest-600 font-bold">{sales?.shift_status || 'Active'}</span>
            </p>
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-2">
          <button
            onClick={fetchOverviewData}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-ivory hover:bg-sandalwood text-maroon-800 border border-sand transition-colors shadow-heritage-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={() => onNavigate('workspace')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-terracotta-500 hover:bg-terracotta-600 text-ivory shadow-md shadow-terracotta-500/20 transition-all"
          >
            Consult AI Workspace
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && <ErrorAlert title="Connection Notice" message={error} onRetry={fetchOverviewData} />}

      {/* Primary KPI Grid (Indian Rupee formatted) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Today's Revenue"
          value={formatINR(sales?.summary?.total_revenue)}
          subvalue="Grounded in completed orders"
          icon={TrendingUp}
          iconColor="text-forest-600"
          iconBg="bg-forest-50"
          trend="up"
          trendValue="Live POS"
          isSynthetic={true}
        />
        <StatCard
          title="Total Orders"
          value={formatIndianNumber(sales?.summary?.total_orders ?? 0)}
          subvalue={`AOV: ${formatINR(sales?.summary?.average_order_value)}`}
          icon={ShoppingBag}
          iconColor="text-maroon-700"
          iconBg="bg-maroon-50"
          trend="neutral"
          trendValue="Shift Total"
          isSynthetic={true}
        />
        <StatCard
          title="Peak Rush Hour"
          value={sales?.summary?.busiest_hour || '12:00 PM'}
          subvalue="Highest hourly order volume"
          icon={Clock}
          iconColor="text-saffron-600"
          iconBg="bg-saffron-50"
          isSynthetic={true}
        />
        <StatCard
          title="Stock Health"
          value={`${lowStockItems.length} Low Items`}
          subvalue={lowStockItems.length > 0 ? 'Requires immediate restock' : 'All levels adequate'}
          icon={AlertTriangle}
          iconColor={lowStockItems.length > 0 ? 'text-maroon-600' : 'text-forest-600'}
          iconBg={lowStockItems.length > 0 ? 'bg-maroon-50' : 'bg-forest-50'}
          trend={lowStockItems.length > 0 ? 'down' : 'up'}
          trendValue={lowStockItems.length > 0 ? 'Urgent' : 'Optimal'}
          isSynthetic={true}
        />
      </div>

      {/* Main Content Split: Top Sellers & Inventory Reorder Priority */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Selling Items */}
        <div className="heritage-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
                  Top Selling Items
                  <Badge variant="neutral" size="sm">Quantity Ranked</Badge>
                </h3>
                <p className="text-xs text-muted-brown">Highest volume items from completed register transactions</p>
              </div>
              <button
                onClick={() => onNavigate('sales')}
                className="text-xs text-terracotta-600 hover:text-terracotta-700 font-bold flex items-center gap-1"
              >
                View Sales
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-2.5">
              {sales?.top_selling_items && sales.top_selling_items.length > 0 ? (
                sales.top_selling_items.slice(0, 5).map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-xl bg-sandalwood/50 border border-sand hover:border-saffron-300 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-lg bg-terracotta-100 text-terracotta-700 flex items-center justify-center font-bold text-xs">
                        #{idx + 1}
                      </span>
                      <div>
                        <h4 className="text-xs font-bold text-ink">{item.item}</h4>
                        <p className="text-[11px] text-muted-brown font-mono">{formatIndianNumber(item.quantity_sold)} units sold</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold text-forest-700 font-mono">
                        {formatINR(item.revenue)}
                      </span>
                      <p className="text-[10px] text-muted-brown">Turnover</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-muted-brown text-center py-6">No order records recorded for this shift.</p>
              )}
            </div>
          </div>
        </div>

        {/* Low Stock Alerts & Critical Reorders */}
        <div className="heritage-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
                  Inventory Alerts
                  {lowStockItems.length > 0 ? (
                    <Badge variant="error" size="sm">{lowStockItems.length} Critical</Badge>
                  ) : (
                    <Badge variant="success" size="sm">Optimal</Badge>
                  )}
                </h3>
                <p className="text-xs text-muted-brown">Ingredients at or below safety reorder threshold</p>
              </div>
              <button
                onClick={() => onNavigate('inventory')}
                className="text-xs text-terracotta-600 hover:text-terracotta-700 font-bold flex items-center gap-1"
              >
                Inventory
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="space-y-2.5">
              {lowStockItems.length > 0 ? (
                lowStockItems.slice(0, 5).map(([id, item]) => (
                  <div
                    key={id}
                    className="flex items-center justify-between p-3 rounded-xl bg-maroon-50/70 border border-maroon-200"
                  >
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="w-4 h-4 text-maroon-700 shrink-0" />
                      <div>
                        <h4 className="text-xs font-bold text-maroon-900">{item.item_name}</h4>
                        <p className="text-[11px] text-maroon-800/80">Category: {item.category}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-bold text-maroon-700 font-mono">
                        {item.current_stock} {item.unit}
                      </span>
                      <p className="text-[10px] text-muted-brown">Threshold: {item.min_reorder_level} {item.unit}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-xs text-muted-brown">
                  <p className="text-forest-700 font-bold mb-1">✓ All ingredient levels are above safety reorder thresholds</p>
                  <span>Stock levels verified from Supabase inventory ledger.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Menu & Category Overview */}
      <div className="heritage-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
              Menu Offerings Breakdown
              <Badge variant="purple" size="sm">
                {menu?.total_items ?? 0} Live Items
              </Badge>
            </h3>
            <p className="text-xs text-muted-brown">Active cafe and restaurant catalog organized by culinary section</p>
          </div>
          <button
            onClick={() => onNavigate('menu')}
            className="text-xs text-terracotta-600 hover:text-terracotta-700 font-bold flex items-center gap-1"
          >
            Explore Menu
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {menu?.categories && menu.categories.length > 0 ? (
            menu.categories.map((cat, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand flex items-center justify-between hover:border-saffron-300 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <Utensils className="w-4 h-4 text-terracotta-500" />
                  <span className="text-xs font-bold text-ink">{cat.category_name}</span>
                </div>
                <span className="text-xs font-mono font-bold text-muted-brown">
                  {cat.items.length} items
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-brown py-4 col-span-4 text-center">No categories loaded.</p>
          )}
        </div>
      </div>
    </div>
  );
};
