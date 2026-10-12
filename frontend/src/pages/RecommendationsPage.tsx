import React, { useState } from 'react';
import {
  Lightbulb,
  Bot,
} from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { AgentChatBox } from '../components/agents/AgentChatBox';

export const RecommendationsPage: React.FC = () => {
  const [activeFilter, setActiveFilter] = useState<'all' | 'critical' | 'high' | 'medium'>('all');

  const recommendationCards = [
    {
      id: 'rec-1',
      priority: 'critical',
      title: 'Restock Full Cream Milk & Specialty Tea Leaves Immediately',
      domain: 'Inventory & Beverage Sales',
      impact: 'Prevent ₹14,500+ daily lost beverage revenue',
      rationale:
        'Milk and tea leaf stock are below safety replenishment thresholds while Chai & Filter Coffee generate over 62% of morning shift transaction volume.',
      suggestedAction: 'Issue immediate emergency purchase order to local dairy vendor before 6:30 AM morning shift.',
      dataPoints: ['Milk inventory <= 5L', 'Chai/Coffee turnover 62%', 'Peak velocity at 12:00 PM'],
    },
    {
      id: 'rec-2',
      priority: 'high',
      title: 'Deploy Second POS Register / QSR Tablet During 12:30-1:30 PM Rush',
      domain: 'Operations & Dining Service',
      impact: 'Eliminate 74% of negative guest reviews regarding billing delays',
      rationale:
        'Customer feedback analysis identifies 12:30 PM - 1:30 PM checkout counter bottlenecks as the leading factor in 3-star and below ratings.',
      suggestedAction: 'Assign a floor captain to take table orders via handheld POS terminal during peak lunch hour.',
      dataPoints: ['Peak rush hour: 12:00 PM', '14% negative feedback relates to billing queue'],
    },
    {
      id: 'rec-3',
      priority: 'high',
      title: 'Capitalize on Filter Coffee & Masala Chai Price Elasticity',
      domain: 'Menu Engineering & Margins',
      impact: 'Estimated +₹18,000 monthly contribution margin gain',
      rationale:
        'Specialty beverages maintain highest order rankings with zero guest price resistance and 94% positive sentiment.',
      suggestedAction: 'Introduce a curated Traditional Snack & Beverage combo pairing at ₹120 price point.',
      dataPoints: ['#1 seller by units', '4.9/5 sentiment score', 'High contribution margin'],
    },
    {
      id: 'rec-4',
      priority: 'medium',
      title: 'Shift Afternoon Samosa & Snack Baking Schedule to 2:00 PM',
      domain: 'Kitchen Prep & Food Waste',
      impact: 'Capture teatime rush foot traffic while curtailing evening scrap',
      rationale:
        'Guest reviews cite afternoon snack stockouts before 4:00 PM tea time, yet morning over-prep creates end-of-day shrinkage.',
      suggestedAction: 'Divide kitchen baking schedule into a 7:30 AM breakfast batch and a 2:00 PM teatime refreshment batch.',
      dataPoints: ['Afternoon stockouts cited in 6 reviews', 'Zero evening carryover policy'],
    },
  ];

  const filteredRecs =
    activeFilter === 'all'
      ? recommendationCards
      : recommendationCards.filter((r) => r.priority === activeFilter);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-5 rounded-2xl heritage-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-terracotta-50 text-terracotta-600 border border-sand">
            <Lightbulb className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
              Actionable Restaurant Intelligence Recommendations
              <Badge variant="synthetic" size="sm">
                Synthetic Baseline
              </Badge>
            </h2>
            <p className="text-xs text-muted-brown">
              Cross-functional synthesis reconciling sales turnover, inventory buffer, and guest satisfaction
            </p>
          </div>
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-1.5 bg-sandalwood/70 p-1 rounded-xl border border-sand text-xs">
          {(['all', 'critical', 'high', 'medium'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setActiveFilter(p)}
              className={`px-3 py-1.5 rounded-lg capitalize transition-all font-semibold ${
                activeFilter === p
                  ? 'bg-maroon-800 text-ivory shadow-sm'
                  : 'text-muted-brown hover:text-maroon-900 hover:bg-sand/30'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Grid of Recommendation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredRecs.map((rec) => (
          <div
            key={rec.id}
            className="p-6 rounded-2xl heritage-card heritage-card-hover flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-3 mb-2">
                <span className="text-[10px] font-bold text-muted-brown uppercase tracking-wider">
                  {rec.domain}
                </span>
                <Badge
                  variant={
                    rec.priority === 'critical'
                      ? 'error'
                      : rec.priority === 'high'
                      ? 'warning'
                      : 'info'
                  }
                  size="sm"
                >
                  {rec.priority.toUpperCase()} PRIORITY
                </Badge>
              </div>

              <h3 className="text-sm font-bold text-maroon-900 font-serif mb-2 leading-snug">{rec.title}</h3>
              <p className="text-xs text-muted-brown mb-3 leading-relaxed font-sans">{rec.rationale}</p>

              <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs space-y-1 mb-3">
                <span className="font-bold text-terracotta-700">Action Plan:</span>
                <p className="text-ink text-[11px] leading-relaxed font-sans">{rec.suggestedAction}</p>
              </div>
            </div>

            <div className="pt-3 border-t border-sand/70 flex flex-wrap items-center justify-between gap-2 text-[11px]">
              <span className="text-muted-brown font-semibold">
                Projected Impact: <strong className="text-forest-700 font-mono">{rec.impact}</strong>
              </span>
              <div className="flex gap-1.5">
                {rec.dataPoints.map((pt, pidx) => (
                  <span key={pidx} className="px-2 py-0.5 rounded-md bg-ivory text-[10px] text-muted-brown font-mono border border-sand">
                    {pt}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Live Recommendation Agent Chat Session */}
      <div className="heritage-card p-6">
        <h3 className="text-sm font-bold text-maroon-900 font-serif mb-1 flex items-center gap-2">
          <Bot className="w-4 h-4 text-terracotta-600" />
          Interactive Advisory Consultation
        </h3>
        <p className="text-xs text-muted-brown mb-4 font-sans">
          Query the Decision & Recommendation Agent for dynamic strategic analysis, promotions, or cost simulations.
        </p>

        <div className="h-[460px]">
          <AgentChatBox
            initialMode="recommendations"
            allowAgentSwitch={false}
            placeholder="Ask the Decision & Recommendation Agent for strategic initiatives..."
            suggestedPrompts={[
              'Synthesize sales, feedback, and inventory into our top 3 priorities.',
              'How can we reduce afternoon pastry waste without angering customers?',
              'What promotions should we run to boost slow Tuesday afternoon shifts?',
            ]}
          />
        </div>
      </div>
    </div>
  );
};
