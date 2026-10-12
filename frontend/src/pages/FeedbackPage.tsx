import React from 'react';
import {
  MessageSquareHeart,
  Star,
  ThumbsUp,
  AlertCircle,
  TrendingDown,
  Sparkles,
} from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { StatCard } from '../components/common/StatCard';
import { AgentChatBox } from '../components/agents/AgentChatBox';

export const FeedbackPage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-5 rounded-2xl heritage-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-maroon-50 text-maroon-700 border border-maroon-200">
            <MessageSquareHeart className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
              Guest Experience & Sentiment Intelligence
              <Badge variant="synthetic" size="sm">
                Synthetic Baseline
              </Badge>
            </h2>
            <p className="text-xs text-muted-brown">
              Aggregated guest feedback, rating trends, and operational complaint root-causes
            </p>
          </div>
        </div>
      </div>

      {/* Sentiment Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Average Rating"
          value="4.2 / 5.0"
          subvalue="Grounded in dining room reviews"
          icon={Star}
          iconColor="text-saffron-600"
          iconBg="bg-saffron-50"
          trend="up"
          trendValue="+0.3 MoM"
          isSynthetic={true}
        />
        <StatCard
          title="Positive Sentiment"
          value="78%"
          subvalue="Praising spice blend, hospitality, & ambiance"
          icon={ThumbsUp}
          iconColor="text-forest-600"
          iconBg="bg-forest-50"
          trend="up"
          trendValue="Healthy"
          isSynthetic={true}
        />
        <StatCard
          title="Service Variance"
          value="14% Delays"
          subvalue="Table turn & billing during 1-2 PM rush"
          icon={TrendingDown}
          iconColor="text-maroon-600"
          iconBg="bg-maroon-50"
          trend="down"
          trendValue="Needs Attention"
          isSynthetic={true}
        />
        <StatCard
          title="Culinary Inquiries"
          value="Jain & Vegan"
          subvalue="High guest demand for specialty dietary prep"
          icon={Sparkles}
          iconColor="text-terracotta-600"
          iconBg="bg-terracotta-50"
          isSynthetic={true}
        />
      </div>

      {/* Main Analysis Split: AI Agent Inquiry + Theme Highlights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Qualitative Themes & Sentiment Highlights */}
        <div className="space-y-4">
          <div className="p-6 rounded-2xl heritage-card space-y-3">
            <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
              <Star className="w-4 h-4 text-saffron-500 fill-saffron-500" />
              Star Rating Distribution
            </h3>
            <div className="space-y-2.5 text-xs">
              {[
                { stars: 5, pct: 55, color: 'bg-forest-600' },
                { stars: 4, pct: 28, color: 'bg-forest-500' },
                { stars: 3, pct: 10, color: 'bg-saffron-500' },
                { stars: 2, pct: 4, color: 'bg-terracotta-400' },
                { stars: 1, pct: 3, color: 'bg-maroon-600' },
              ].map((r) => (
                <div key={r.stars} className="flex items-center gap-2">
                  <span className="w-14 text-muted-brown font-mono text-[11px] font-bold">{r.stars} Stars</span>
                  <div className="flex-1 h-2 rounded-full bg-sandalwood overflow-hidden border border-sand/80">
                    <div className={`h-full ${r.color} rounded-full`} style={{ width: `${r.pct}%` }} />
                  </div>
                  <span className="w-8 text-right font-mono text-ink font-bold text-[11px]">{r.pct}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 rounded-2xl heritage-card space-y-3">
            <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-terracotta-600" />
              Recurring Operational Feedback
            </h3>
            <div className="space-y-2.5">
              <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                <span className="font-bold text-maroon-800">Lunch Counter Waiting Times:</span>
                <p className="text-[11px] text-muted-brown mt-1 leading-relaxed">
                  12:30 PM to 1:30 PM billing and checkout bottlenecks cited in multiple guest reviews.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                <span className="font-bold text-forest-700">Specialty Beverage Praise:</span>
                <p className="text-[11px] text-muted-brown mt-1 leading-relaxed">
                  Filter Coffee and Masala Chai receive consistent 5-star mentions for authenticity.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                <span className="font-bold text-saffron-700">Evening Pastry Freshness:</span>
                <p className="text-[11px] text-muted-brown mt-1 leading-relaxed">
                  Afternoon tea snacks and samosas sell out early before 4:00 PM tea time.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Live Feedback Intelligence Agent Chat */}
        <div className="lg:col-span-2 h-[560px]">
          <AgentChatBox
            initialMode="feedback"
            allowAgentSwitch={false}
            placeholder="Ask Feedback Agent to analyze sentiment trends, guest ratings, or specific complaints..."
            suggestedPrompts={[
              'What are the most frequent customer complaints this week?',
              'Summarize guest reviews regarding beverage quality.',
              'What do reviews say about wait times during lunch hour?',
            ]}
          />
        </div>
      </div>
    </div>
  );
};
