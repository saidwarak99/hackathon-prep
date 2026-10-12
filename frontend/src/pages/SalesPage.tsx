import React, { useState, useEffect } from 'react';
import {
  ShoppingBag,
  TrendingUp,
  Clock,
  CreditCard,
  Calendar,
  RefreshCw,
  Bot,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { SalesResponse } from '../api/types';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { AgentChatBox } from '../components/agents/AgentChatBox';
import { formatINR, formatIndianNumber } from '../utils/formatters';

export const SalesPage: React.FC = () => {
  const [sales, setSales] = useState<SalesResponse | null>(null);
  const [date, setDate] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSalesAgent, setShowSalesAgent] = useState(false);

  const fetchSales = async (dateStr?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getSales(dateStr || undefined);
      setSales(res);
      if (res.date && res.date !== 'N/A' && !date) {
        setDate(res.date);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load sales intelligence data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSales();
  }, []);

  const totalRev = sales?.summary?.total_revenue || 0;

  return (
    <div className="space-y-6">
      {/* Date Filter & Control Bar */}
      <div className="p-5 rounded-2xl heritage-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-forest-50 text-forest-700 border border-forest-200">
            <Calendar className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
              Sales Performance Analysis
              <Badge variant="synthetic" size="sm">
                Synthetic Baseline
              </Badge>
            </h2>
            <p className="text-xs text-muted-brown">
              Shift Status:{' '}
              <span className="text-forest-600 font-bold">{sales?.shift_status || 'Active'}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-sandalwood/80 px-3.5 py-2 rounded-xl border border-sand text-xs text-ink shadow-inner">
            <span className="text-muted-brown font-semibold">Date:</span>
            <input
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                fetchSales(e.target.value);
              }}
              className="bg-transparent text-maroon-900 font-mono font-bold focus:outline-none cursor-pointer"
            />
          </div>

          <button
            onClick={() => fetchSales(date)}
            disabled={loading}
            className="p-2.5 rounded-xl bg-ivory hover:bg-sandalwood text-maroon-800 border border-sand transition-colors shadow-heritage-sm"
            title="Refresh sales ledger"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setShowSalesAgent(!showSalesAgent)}
            className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md ${
              showSalesAgent
                ? 'bg-maroon-800 text-ivory shadow-maroon-900/20'
                : 'bg-terracotta-500 text-ivory hover:bg-terracotta-600 shadow-terracotta-500/20'
            }`}
          >
            <Bot className="w-4 h-4" />
            {showSalesAgent ? 'Hide Sales Agent' : 'Ask Sales Agent'}
          </button>
        </div>
      </div>

      {error && <ErrorAlert title="Sales Query Notice" message={error} onRetry={() => fetchSales(date)} />}

      {/* Embedded Sales Agent Drawer if toggled */}
      {showSalesAgent && (
        <div className="h-96">
          <AgentChatBox
            initialMode="sales"
            allowAgentSwitch={false}
            placeholder="Ask Sales Agent about turnover trends, hourly velocity, or ticket breakdown..."
            suggestedPrompts={[
              'What was the hourly order volume during peak hours?',
              'Compare beverage sales vs food items.',
              'What percentage of total revenue came from credit cards?',
            ]}
          />
        </div>
      )}

      {loading && !sales ? (
        <LoadingSpinner message="Calculating shift turnover and payment channel breakdown..." />
      ) : (
        <>
          {/* Sales Metric KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Gross Turnover"
              value={formatINR(sales?.summary?.total_revenue)}
              subvalue={`Date: ${sales?.date || 'Today'}`}
              icon={TrendingUp}
              iconColor="text-forest-600"
              iconBg="bg-forest-50"
              trend="up"
              trendValue="POS Verified"
              isSynthetic={true}
            />
            <StatCard
              title="Total Transactions"
              value={formatIndianNumber(sales?.summary?.total_orders ?? 0)}
              subvalue="Completed POS bills"
              icon={ShoppingBag}
              iconColor="text-maroon-700"
              iconBg="bg-maroon-50"
              trend="neutral"
              trendValue="Shift Total"
              isSynthetic={true}
            />
            <StatCard
              title="Average Order Value"
              value={formatINR(sales?.summary?.average_order_value)}
              subvalue="Ticket size per transaction"
              icon={TrendingUp}
              iconColor="text-terracotta-600"
              iconBg="bg-terracotta-50"
              isSynthetic={true}
            />
            <StatCard
              title="Peak Rush Period"
              value={sales?.summary?.busiest_hour || 'N/A'}
              subvalue="Highest transaction velocity"
              icon={Clock}
              iconColor="text-saffron-600"
              iconBg="bg-saffron-50"
              isSynthetic={true}
            />
          </div>

          {/* Breakdown Section: Top Items & Payment Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Top Selling Items Table */}
            <div className="lg:col-span-2 heritage-card p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-maroon-900 font-serif">Dishes & Beverage Performance</h3>
                  <p className="text-xs text-muted-brown">Item sales volumes ranked with gross revenue contribution</p>
                </div>
                <Badge variant="neutral" size="sm">
                  {sales?.top_selling_items?.length || 0} Items Recorded
                </Badge>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-sand text-muted-brown font-bold uppercase tracking-wider text-[10px]">
                      <th className="pb-3 pl-2">Rank</th>
                      <th className="pb-3">Menu Offering</th>
                      <th className="pb-3 text-right">Units Sold</th>
                      <th className="pb-3 text-right">Gross Turnover</th>
                      <th className="pb-3 text-right pr-2">Share</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sand/60">
                    {sales?.top_selling_items && sales.top_selling_items.length > 0 ? (
                      sales.top_selling_items.map((item, idx) => {
                        const share = totalRev > 0 ? ((item.revenue / totalRev) * 100).toFixed(1) : '0';
                        return (
                          <tr key={idx} className="hover:bg-sandalwood/40 transition-colors">
                            <td className="py-3.5 pl-2 font-mono text-muted-brown font-bold">#{idx + 1}</td>
                            <td className="py-3.5 font-bold text-ink">{item.item}</td>
                            <td className="py-3.5 text-right font-mono text-muted-brown">{formatIndianNumber(item.quantity_sold)}</td>
                            <td className="py-3.5 text-right font-mono text-forest-700 font-bold">
                              {formatINR(item.revenue)}
                            </td>
                            <td className="py-3.5 text-right pr-2 font-mono text-muted-brown">{share}%</td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-muted-brown">
                          No item records returned for this date.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Payment Method Breakdown */}
            <div className="heritage-card p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
                      Settlement Channels
                      <CreditCard className="w-4 h-4 text-terracotta-500" />
                    </h3>
                    <p className="text-xs text-muted-brown">Tender type volume distribution</p>
                  </div>
                </div>

                <div className="space-y-4">
                  {sales?.payment_breakdown && Object.keys(sales.payment_breakdown).length > 0 ? (
                    Object.entries(sales.payment_breakdown).map(([method, amount], idx) => {
                      const pct = totalRev > 0 ? (amount / totalRev) * 100 : 0;
                      return (
                        <div key={idx} className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="capitalize font-bold text-ink">{method}</span>
                            <span className="font-mono text-forest-700 font-bold">
                              {formatINR(amount)} <span className="text-muted-brown font-normal">({pct.toFixed(0)}%)</span>
                            </span>
                          </div>
                          <div className="w-full h-2 rounded-full bg-sandalwood overflow-hidden border border-sand">
                            <div
                              className="h-full bg-gradient-to-r from-terracotta-500 to-saffron-500 rounded-full transition-all"
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-xs text-muted-brown py-6 text-center">No payment breakdown recorded.</p>
                  )}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-sand text-xs text-muted-brown flex items-center justify-between">
                <span className="font-semibold">Total Reconciled:</span>
                <span className="font-mono text-maroon-900 font-extrabold text-sm">{formatINR(totalRev)}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
