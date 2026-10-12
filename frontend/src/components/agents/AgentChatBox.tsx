import React, { useState } from 'react';
import {
  Send,
  Bot,
  User,
  Wrench,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Database,
  Info,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import { Badge } from '../common/Badge';

export type AgentMode =
  | 'unified'
  | 'sales'
  | 'menu'
  | 'feedback'
  | 'inventory'
  | 'recommendations'
  | 'general';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  agentName?: string;
  text: string;
  timestamp: string;
  dataOrigin?: string;
  datasetId?: string;
  evidenceSources?: string[];
  limitations?: string[];
  executedTools?: Array<Record<string, any>>;
  selectedAgents?: string[];
  route?: string[];
  isError?: boolean;
}

interface AgentChatBoxProps {
  initialMode?: AgentMode;
  allowAgentSwitch?: boolean;
  placeholder?: string;
  suggestedPrompts?: string[];
}

export const AgentChatBox: React.FC<AgentChatBoxProps> = ({
  initialMode = 'unified',
  allowAgentSwitch = true,
  placeholder = 'Ask a question across sales, menu engineering, guest feedback, or inventory...',
  suggestedPrompts = [
    'What was our top performing item and total revenue today?',
    'Which items are currently below minimum reorder thresholds?',
    'What are the most common customer complaints and rating trends?',
    'Provide prioritized operational recommendations to increase margins.',
  ],
}) => {
  const { selectedDatasetId, restaurantId } = useDataset();
  const [mode, setMode] = useState<AgentMode>(initialMode);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      agentName: 'RasaIQ Orchestrator',
      text: 'Namaste! I am your Restaurant Intelligence Advisor. You can query sales figures, menu metrics, inventory health, review sentiment, and strategic recommendations grounded directly in your database.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      dataOrigin: 'SYSTEM',
    },
  ]);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const toggleTools = (msgId: string) => {
    setExpandedTools((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      if (mode === 'unified') {
        const res = await apiClient.sendUnifiedChat({
          message: query,
          restaurant_id: restaurantId,
          dataset_id: selectedDatasetId || undefined,
        });

        const agentMsg: ChatMessage = {
          id: `agent-${Date.now()}`,
          sender: 'agent',
          agentName: 'Unified Orchestrator',
          text: res.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          dataOrigin: res.data_origin,
          datasetId: res.dataset_id,
          evidenceSources: res.evidence_sources,
          limitations: res.limitations,
          selectedAgents: res.selected_agents,
          route: res.route,
        };
        setMessages((prev) => [...prev, agentMsg]);
      } else {
        const res = await apiClient.sendAgentChat(mode, query);
        const agentMsg: ChatMessage = {
          id: `agent-${Date.now()}`,
          sender: 'agent',
          agentName: res.agent || `${mode.toUpperCase()} Agent`,
          text: res.answer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          dataOrigin: 'SYNTHETIC BASELINE',
          executedTools: res.executed_tools,
        };
        setMessages((prev) => [...prev, agentMsg]);
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        sender: 'agent',
        agentName: 'System Notice',
        text: err?.message || 'Failed to complete agent execution. Please check your backend connection.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full heritage-card overflow-hidden">
      {/* Agent Selector Header */}
      <div className="p-4 border-b border-sand bg-sandalwood/50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-terracotta-50 text-terracotta-500 border border-sand">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-bold text-maroon-900 font-serif">Active Intelligence Router</span>
            <p className="text-[10px] text-muted-brown">
              {mode === 'unified'
                ? selectedDatasetId
                  ? `Scope: Uploaded Dataset (${selectedDatasetId})`
                  : 'Scope: Baseline Database (Unified Routing)'
                : selectedDatasetId
                ? `Scope: Baseline Database (Direct ${mode} agent queries baseline POS; use Unified Router for uploaded datasets)`
                : `Scope: Baseline Database (Direct ${mode} agent)`}
            </p>
          </div>
        </div>

        {allowAgentSwitch && (
          <div className="flex items-center gap-1 bg-ivory p-1 rounded-xl border border-sand shadow-inner">
            {[
              { id: 'unified', label: 'Unified Router' },
              { id: 'sales', label: 'Sales' },
              { id: 'menu', label: 'Menu' },
              { id: 'feedback', label: 'Feedback' },
              { id: 'inventory', label: 'Inventory' },
              { id: 'recommendations', label: 'Recommendations' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id as AgentMode)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                  mode === m.id
                    ? 'bg-maroon-800 text-ivory shadow-sm'
                    : 'text-muted-brown hover:text-maroon-900 hover:bg-sand/30'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-ivory/60 jali-subtle-overlay">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div
              key={msg.id}
              className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-xl shrink-0 flex items-center justify-center text-xs font-bold shadow-sm ${
                  isUser
                    ? 'bg-maroon-800 text-ivory'
                    : msg.isError
                    ? 'bg-maroon-100 text-maroon-800 border border-maroon-200'
                    : 'bg-terracotta-50 text-terracotta-600 border border-sand'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`rounded-2xl p-4 text-xs leading-relaxed space-y-2 shadow-heritage-sm ${
                  isUser
                    ? 'bg-maroon-800 text-ivory rounded-tr-none'
                    : msg.isError
                    ? 'bg-maroon-50 border border-maroon-200 text-maroon-900 rounded-tl-none'
                    : 'bg-ivory border border-sand text-ink rounded-tl-none'
                }`}
              >
                <div className="flex items-center justify-between gap-4 text-[11px] pb-1 border-b border-sand/40">
                  <span className={`font-bold ${isUser ? 'text-saffron-300' : 'text-maroon-800 font-serif'}`}>
                    {msg.agentName || 'You'}
                  </span>
                  <span className={isUser ? 'text-sand/80' : 'text-muted-brown'}>{msg.timestamp}</span>
                </div>

                <div className="whitespace-pre-line break-words text-[13px] leading-relaxed font-sans">
                  {msg.text}
                </div>

                {/* Evidence & Provenance Chips */}
                {!isUser && (
                  <div className="pt-2 border-t border-sand/60 flex flex-wrap items-center gap-1.5">
                    {msg.dataOrigin && (
                      <Badge variant={msg.dataOrigin === 'SYNTHETIC' ? 'synthetic' : 'success'} size="sm">
                        <Database className="w-3 h-3 mr-1 text-saffron-600" />
                        Origin: {msg.dataOrigin}
                      </Badge>
                    )}

                    {msg.datasetId && (
                      <Badge variant="purple" size="sm">
                        Dataset: {msg.datasetId}
                      </Badge>
                    )}

                    {msg.selectedAgents && msg.selectedAgents.length > 0 && (
                      <Badge variant="info" size="sm">
                        Agents: {msg.selectedAgents.join(', ')}
                      </Badge>
                    )}

                    {msg.evidenceSources && msg.evidenceSources.length > 0 && (
                      <Badge variant="neutral" size="sm">
                        Sources: {msg.evidenceSources.join(', ')}
                      </Badge>
                    )}
                  </div>
                )}

                {/* Limitations */}
                {msg.limitations && msg.limitations.length > 0 && (
                  <div className="mt-2 p-2.5 rounded-xl bg-saffron-50 border border-saffron-200 text-[11px] text-saffron-800 flex items-start gap-1.5">
                    <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-saffron-600" />
                    <div>
                      <span className="font-bold">Operational Limitations:</span>
                      <ul className="list-disc pl-4 mt-0.5 space-y-0.5">
                        {msg.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* Executed Tools Collapsible */}
                {msg.executedTools && msg.executedTools.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-sand/60">
                    <button
                      onClick={() => toggleTools(msg.id)}
                      className="flex items-center gap-1.5 text-[11px] text-terracotta-600 hover:text-terracotta-700 font-bold"
                    >
                      <Wrench className="w-3 h-3" />
                      <span>{msg.executedTools.length} tool executions inspected</span>
                      {expandedTools[msg.id] ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                    </button>
                    {expandedTools[msg.id] && (
                      <div className="mt-2 p-2.5 rounded-xl bg-sandalwood font-mono text-[10px] text-ink max-h-40 overflow-y-auto space-y-1 border border-sand">
                        {msg.executedTools.map((t, tidx) => (
                          <div key={tidx} className="pb-1 border-b border-sand/60 last:border-0">
                            <span className="text-maroon-800 font-bold">{t.tool || t.tool_name}</span>
                            <pre className="text-muted-brown overflow-x-auto mt-0.5">
                              {JSON.stringify(t.args || t.result || t, null, 2)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-xl bg-terracotta-50 text-terracotta-600 border border-sand flex items-center justify-center">
              <Bot className="w-4 h-4 animate-bounce" />
            </div>
            <div className="rounded-2xl p-4 bg-ivory border border-sand text-muted-brown text-xs flex items-center gap-2 shadow-heritage-sm">
              <span className="w-2 h-2 rounded-full bg-terracotta-500 animate-ping" />
              <span>Orchestrating agents and retrieving verified database records...</span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Prompts */}
      {messages.length <= 2 && suggestedPrompts.length > 0 && (
        <div className="px-4 py-2.5 bg-sandalwood/70 border-t border-sand flex items-center gap-2 overflow-x-auto">
          <span className="text-[10px] uppercase font-bold text-muted-brown whitespace-nowrap">
            Suggested:
          </span>
          {suggestedPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(p)}
              className="text-xs px-2.5 py-1 rounded-xl bg-ivory hover:bg-sand/40 text-maroon-800 whitespace-nowrap border border-sand transition-colors font-medium shadow-heritage-sm"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="p-3 bg-ivory border-t border-sand flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          disabled={loading}
          className="flex-1 bg-sandalwood/50 border border-sand focus:border-terracotta-500 rounded-xl px-4 py-2.5 text-xs text-ink placeholder-muted-brown focus:outline-none transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-2.5 bg-terracotta-500 hover:bg-terracotta-600 disabled:opacity-50 text-ivory font-bold text-xs rounded-xl flex items-center gap-1.5 transition-all shadow-md shadow-terracotta-500/20"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Consult</span>
        </button>
      </form>
    </div>
  );
};
