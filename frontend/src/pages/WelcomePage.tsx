import React, { useState } from 'react';
import {
  Sparkles,
  ArrowRight,
  Store,
  Compass,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  UtensilsCrossed,
  Bot,
  Info,
} from 'lucide-react';
import { useDataset } from '../context/DatasetContext';

export const WelcomePage: React.FC = () => {
  const { enterDemoWorkspace, isBackendConnected } = useDataset();
  const [restaurantInput, setRestaurantInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleEnterWorkspace = (nameToUse?: string) => {
    const finalName = (nameToUse !== undefined ? nameToUse : restaurantInput).trim();
    if (!finalName) {
      setError('Please enter a restaurant or cafe name to enter the demo workspace.');
      return;
    }
    setError(null);
    setIsSubmitting(true);
    // Smooth transition
    setTimeout(() => {
      enterDemoWorkspace(finalName);
      setIsSubmitting(false);
    }, 200);
  };

  const handleSampleRestaurantClick = () => {
    handleEnterWorkspace('Dakshin Heritage Cafe');
  };

  return (
    <div className="min-h-screen w-full bg-sandalwood text-ink flex flex-col justify-between relative overflow-x-hidden selection:bg-terracotta-100 selection:text-terracotta-700">
      {/* Subtle Indian Heritage Radial Glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[450px] bg-gradient-to-b from-saffron-100/40 via-terracotta-50/20 to-transparent blur-3xl pointer-events-none -z-0" />

      {/* Top Navigation Bar */}
      <header className="w-full px-6 sm:px-12 py-5 flex items-center justify-between border-b border-sand/70 bg-ivory/80 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-saffron-400 to-terracotta-500 flex items-center justify-center shadow-md text-maroon-900 border border-saffron-200">
            <svg className="w-5 h-5 text-maroon-900" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L14.4 7.2L20 8.3L16 12.2L17 17.8L12 15.2L7 17.8L8 12.2L4 8.3L9.6 7.2L12 2Z" />
            </svg>
          </div>
          <div>
            <div className="font-serif font-extrabold text-lg tracking-tight text-maroon-900 flex items-center gap-1">
              RASA<span className="text-terracotta-500 font-sans font-black text-sm">IQ</span>
            </div>
            <p className="text-[10px] text-muted-brown font-medium tracking-wider uppercase">
              Hospitality Intelligence
            </p>
          </div>
        </div>

        {/* Live System Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-sandalwood border border-sand text-xs font-mono text-muted-brown">
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendConnected ? 'bg-forest-500 animate-pulse' : 'bg-terracotta-500'
            }`}
          />
          <span className="text-[11px] font-semibold text-maroon-900">
            {isBackendConnected ? 'FastAPI & Database Online' : 'Connecting to Backend...'}
          </span>
        </div>
      </header>

      {/* Hero & Onboarding Section */}
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-12 relative z-10">
        <div className="w-full max-w-2xl">
          {/* Main Welcome Card with Guilloche Engraved Top Border */}
          <div className="heritage-card engraved-border-top p-8 sm:p-12 shadow-heritage-lg relative overflow-hidden bg-ivory">
            {/* Subtle Watermark Glyph */}
            <div className="absolute top-4 right-4 text-saffron-200/40 pointer-events-none select-none">
              <svg className="w-32 h-32 opacity-20" viewBox="0 0 100 100" fill="currentColor">
                <circle cx="50" cy="50" r="45" stroke="#D9A441" strokeWidth="1" fill="none" />
                <circle cx="50" cy="50" r="30" stroke="#B95332" strokeWidth="0.75" fill="none" />
                <path d="M50 5 L50 95 M5 50 L95 50 M18 18 L82 82 M18 82 L82 18" stroke="#D9A441" strokeWidth="0.5" />
              </svg>
            </div>

            {/* Header Content */}
            <div className="text-center space-y-3 mb-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-saffron-50 border border-saffron-200/80 text-[11px] font-bold text-saffron-700 uppercase tracking-widest font-sans">
                <Sparkles className="w-3.5 h-3.5 text-saffron-600" />
                Hackathon Demo Onboarding
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold text-maroon-900 font-serif tracking-tight leading-tight">
                Your restaurant. <br className="hidden sm:inline" />
                <span className="text-terracotta-600 italic">Better decisions.</span>
              </h1>

              <p className="text-xs sm:text-sm text-muted-brown max-w-lg mx-auto leading-relaxed">
                Autonomous multi-agent intelligence coordinating daily sales turnover, dish velocity,
                guest sentiment drivers, inventory burn, and culinary SOPs.
              </p>
            </div>

            {/* Input & Action Form */}
            <div className="space-y-4 max-w-lg mx-auto">
              <div>
                <label
                  htmlFor="restaurantNameInput"
                  className="block text-xs font-bold text-maroon-900 mb-1.5 flex items-center gap-1.5"
                >
                  <Store className="w-3.5 h-3.5 text-terracotta-500" />
                  Restaurant or Cafe Name
                </label>
                <div className="relative">
                  <input
                    id="restaurantNameInput"
                    type="text"
                    value={restaurantInput}
                    onChange={(e) => {
                      setRestaurantInput(e.target.value);
                      if (error) setError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleEnterWorkspace();
                      }
                    }}
                    placeholder="e.g. Royal Darbar Bistro, Chai & Co."
                    className="w-full px-4 py-3.5 rounded-2xl bg-sandalwood/60 border border-sand focus:border-terracotta-500 focus:bg-ivory focus:ring-2 focus:ring-terracotta-400/20 text-maroon-900 placeholder:text-muted-brown/60 text-sm font-medium transition-all outline-none"
                    disabled={isSubmitting}
                  />
                </div>

                {/* Validation Error Banner */}
                {error && (
                  <div className="mt-2.5 p-3 rounded-xl bg-maroon-50 border border-maroon-200 text-maroon-800 text-xs flex items-center gap-2 animate-fadeIn">
                    <AlertCircle className="w-4 h-4 text-maroon-600 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>

              {/* Primary Demo Button */}
              <button
                type="button"
                onClick={() => handleEnterWorkspace()}
                disabled={isSubmitting}
                className="w-full py-3.5 px-6 rounded-2xl bg-maroon-800 hover:bg-maroon-900 active:scale-[0.99] text-ivory font-bold text-sm shadow-heritage transition-all flex items-center justify-center gap-2 group cursor-pointer disabled:opacity-60"
              >
                <span>Enter Demo Workspace</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform text-saffron-300" />
              </button>

              {/* Divider */}
              <div className="relative my-4 flex items-center justify-center">
                <div className="border-t border-sand/80 w-full" />
                <span className="bg-ivory px-3 text-[11px] font-medium text-muted-brown uppercase tracking-wider shrink-0">
                  or try pre-configured sample
                </span>
              </div>

              {/* Explore Sample Restaurant Shortcut Card */}
              <button
                type="button"
                onClick={handleSampleRestaurantClick}
                disabled={isSubmitting}
                className="w-full p-4 rounded-2xl bg-sandalwood/50 hover:bg-sandalwood border border-sand hover:border-saffron-400 text-left transition-all group flex items-start gap-3.5 cursor-pointer shadow-sm hover:shadow-heritage"
              >
                <div className="w-9 h-9 rounded-xl bg-saffron-100 text-saffron-800 border border-saffron-200 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-105 transition-transform">
                  <Compass className="w-4 h-4 text-saffron-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-xs font-bold text-maroon-900 font-serif">
                      Explore Sample: Dakshin Heritage Cafe
                    </h3>
                    <span className="text-[10px] font-bold text-terracotta-600 uppercase tracking-wider bg-terracotta-50 border border-terracotta-200/60 px-2 py-0.5 rounded-full shrink-0">
                      1-Click Demo
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-brown mt-0.5 leading-snug">
                    Instant access loaded with synthetic South Indian cafe orders, 40+ menu recipes, guest reviews, and SOPs.
                  </p>
                </div>
              </button>
            </div>

            {/* Clear Demo Mode Indicator */}
            <div className="mt-8 pt-6 border-t border-sand/70 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-muted-brown">
              <div className="flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 text-forest-600 shrink-0" />
                <span>Demo Mode — No account or credit card required</span>
              </div>
              <div className="text-[10px] text-muted-brown/80 font-mono">
                RasaIQ Multi-Agent v1.0
              </div>
            </div>

            {/* Security & Data Safety Disclaimer */}
            <div className="mt-4 p-3 rounded-xl bg-sandalwood/80 border border-sand/80 text-[11px] text-muted-brown flex items-start gap-2 leading-relaxed">
              <Info className="w-4 h-4 text-terracotta-500 shrink-0 mt-0.5" />
              <span>
                <strong>Controlled Demo Notice:</strong> This onboarding is a client-side shortcut for hackathon evaluation with synthetic benchmark data. It does not enforce cryptographic multi-tenant isolation or production authentication.
              </span>
            </div>
          </div>

          {/* Quick Three Feature Pills */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mt-6">
            <div className="p-3.5 rounded-2xl bg-ivory/80 border border-sand/80 text-center shadow-heritage-sm flex flex-col items-center">
              <TrendingUp className="w-4 h-4 text-terracotta-600 mb-1" />
              <h4 className="text-xs font-bold text-maroon-900 font-serif">Sales Intelligence</h4>
              <p className="text-[10px] text-muted-brown mt-0.5">Turnover, AOV & Rush Hours</p>
            </div>
            <div className="p-3.5 rounded-2xl bg-ivory/80 border border-sand/80 text-center shadow-heritage-sm flex flex-col items-center">
              <UtensilsCrossed className="w-4 h-4 text-saffron-600 mb-1" />
              <h4 className="text-xs font-bold text-maroon-900 font-serif">Menu Intelligence</h4>
              <p className="text-[10px] text-muted-brown mt-0.5">Velocity & Margin Insights</p>
            </div>
            <div className="p-3.5 rounded-2xl bg-ivory/80 border border-sand/80 text-center shadow-heritage-sm flex flex-col items-center">
              <Bot className="w-4 h-4 text-forest-600 mb-1" />
              <h4 className="text-xs font-bold text-maroon-900 font-serif">6 Agent Workspace</h4>
              <p className="text-[10px] text-muted-brown mt-0.5">Unified Autonomous Router</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full py-4 text-center text-xs text-muted-brown/80 border-t border-sand/60 bg-ivory/40">
        RasaIQ • Indian-Inspired Restaurant Intelligence SaaS • Hackathon Prototype
      </footer>
    </div>
  );
};
