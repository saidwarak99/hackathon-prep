import React, { useState, useEffect } from 'react';
import {
  UtensilsCrossed,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Bot,
  Filter,
  Search,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { MenuResponse, MenuItem } from '../api/types';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { AgentChatBox } from '../components/agents/AgentChatBox';
import { formatINR } from '../utils/formatters';

export const MenuPage: React.FC = () => {
  const [menu, setMenu] = useState<MenuResponse | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMenuAgent, setShowMenuAgent] = useState(false);

  const fetchMenu = async (categoryFilter?: string) => {
    setLoading(true);
    setError(null);
    try {
      const catParam = categoryFilter && categoryFilter !== 'All' ? categoryFilter : undefined;
      const res = await apiClient.getMenu(catParam);
      setMenu(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch restaurant menu catalogue.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMenu(selectedCategory);
  }, [selectedCategory]);

  const categories = ['All', ...(menu?.categories?.map((c) => c.category_name) || [])];
  const uniqueCategories = Array.from(new Set(categories));

  const allItems: Array<MenuItem & { category: string }> = [];
  menu?.categories?.forEach((cat) => {
    cat.items.forEach((item) => {
      allItems.push({ ...item, category: cat.category_name });
    });
  });

  const filteredItems = allItems.filter((item) => {
    return (
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.description && item.description.toLowerCase().includes(searchQuery.toLowerCase()))
    );
  });

  return (
    <div className="space-y-6">
      {/* Header & Category Filters */}
      <div className="p-5 rounded-2xl heritage-card space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-2.5 rounded-xl bg-purple-50 text-purple-700 border border-purple-200">
              <UtensilsCrossed className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
                Menu Engineering & Culinary Catalog
                <Badge variant="synthetic" size="sm">
                  Synthetic Baseline
                </Badge>
              </h2>
              <p className="text-xs text-muted-brown">
                {menu?.total_items ?? 0} active dishes and beverages across culinary categories
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchMenu(selectedCategory)}
              disabled={loading}
              className="p-2.5 rounded-xl bg-ivory hover:bg-sandalwood text-maroon-800 border border-sand transition-colors shadow-heritage-sm"
              title="Refresh menu catalog"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={() => setShowMenuAgent(!showMenuAgent)}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md ${
                showMenuAgent
                  ? 'bg-maroon-800 text-ivory shadow-maroon-900/20'
                  : 'bg-purple-700 text-ivory hover:bg-purple-800 shadow-purple-700/20'
              }`}
            >
              <Bot className="w-4 h-4" />
              {showMenuAgent ? 'Hide Menu Agent' : 'Ask Menu Agent'}
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-sand">
          <div className="flex flex-wrap items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-muted-brown mr-1" />
            {uniqueCategories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  selectedCategory === cat
                    ? 'bg-maroon-800 text-ivory shadow-sm'
                    : 'bg-sandalwood/70 text-muted-brown hover:text-maroon-900 hover:bg-sandalwood border border-sand'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-brown absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search recipe or ingredients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3.5 py-1.5 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink placeholder-muted-brown focus:outline-none focus:border-terracotta-500 w-64"
            />
          </div>
        </div>
      </div>

      {error && <ErrorAlert title="Menu Notice" message={error} onRetry={() => fetchMenu(selectedCategory)} />}

      {/* Embedded Menu Agent Drawer */}
      {showMenuAgent && (
        <div className="h-96">
          <AgentChatBox
            initialMode="menu"
            allowAgentSwitch={false}
            placeholder="Ask Menu Intelligence Agent about dish popularity, ingredient cost, or dietary balance..."
            suggestedPrompts={[
              'Which menu category produces the highest sales volume?',
              'List all vegetarian items and their current price points.',
              'Which items should we consider reformulating or promoting?',
            ]}
          />
        </div>
      )}

      {loading && !menu ? (
        <LoadingSpinner message="Auditing menu items, dietary specs, and price margins..." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((item) => (
            <div
              key={item.menu_item_id}
              className="p-5 rounded-2xl heritage-card heritage-card-hover flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-sm font-bold text-maroon-900 font-serif leading-snug">{item.name}</h3>
                  <span className="font-mono text-sm font-extrabold text-forest-700 shrink-0">
                    {formatINR(item.price)}
                  </span>
                </div>

                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[10px] font-bold text-muted-brown uppercase tracking-wider">
                    {item.category}
                  </span>
                  {item.is_available ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-forest-600">
                      <CheckCircle2 className="w-3 h-3" /> Available
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-maroon-600">
                      <XCircle className="w-3 h-3" /> Out of Stock
                    </span>
                  )}
                </div>

                {item.description && (
                  <p className="text-xs text-muted-brown line-clamp-2 leading-relaxed mb-4 font-sans">
                    {item.description}
                  </p>
                )}
              </div>

              {/* Dietary Tags */}
              <div className="pt-3 border-t border-sand/70 flex flex-wrap gap-1.5 items-center">
                {item.dietary && item.dietary.length > 0 ? (
                  item.dietary.map((d, didx) => (
                    <Badge key={didx} variant="purple" size="sm">
                      {d}
                    </Badge>
                  ))
                ) : (
                  <span className="text-[10px] text-muted-brown font-mono">Standard</span>
                )}
                <span className="ml-auto text-[10px] text-muted-brown font-mono">#{item.menu_item_id}</span>
              </div>
            </div>
          ))}

          {filteredItems.length === 0 && (
            <div className="col-span-3 py-12 text-center text-muted-brown text-xs heritage-card">
              No menu items match your search filter.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
