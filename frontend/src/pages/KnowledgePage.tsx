import React, { useState } from 'react';
import {
  BookOpen,
  Search,
  UploadCloud,
  FileText,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { KnowledgeSearchResponse } from '../api/types';
import { useDataset } from '../context/DatasetContext';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';

export const KnowledgePage: React.FC = () => {
  const { restaurantId } = useDataset();
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(3);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Ingestion State
  const [showIngestModal, setShowIngestModal] = useState(false);
  const [docTitle, setDocTitle] = useState('');
  const [docType, setDocType] = useState('sop');
  const [docVersion, setDocVersion] = useState('1.0');
  const [docContent, setDocContent] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestSuccess, setIngestSuccess] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || searching) return;

    setSearching(true);
    setSearchError(null);
    try {
      const res = await apiClient.searchKnowledge({
        query: query.trim(),
        top_k: topK,
        restaurant_id: restaurantId,
      });
      setSearchResults(res);
    } catch (err: any) {
      setSearchError(err?.message || 'Failed to search restaurant knowledge base.');
    } finally {
      setSearching(false);
    }
  };

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim() || !docContent.trim() || ingesting) return;

    setIngesting(true);
    setIngestError(null);
    setIngestSuccess(null);
    try {
      const res = await apiClient.ingestKnowledge({
        title: docTitle.trim(),
        content: docContent.trim(),
        document_type: docType,
        version: docVersion,
        restaurant_id: restaurantId,
      });
      setIngestSuccess(
        `Successfully indexed "${res.title}". Generated ${res.chunks_indexed} vector chunks using ${res.embedding_model}.`
      );
      setDocTitle('');
      setDocContent('');
    } catch (err: any) {
      setIngestError(err?.message || 'Failed to ingest knowledge document.');
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-5 rounded-2xl heritage-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-saffron-50 text-saffron-700 border border-saffron-200">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
              Culinary SOPs & Knowledge Retrieval (pgvector)
              <Badge variant="purple" size="sm">
                RAG Grounded
              </Badge>
            </h2>
            <p className="text-xs text-muted-brown">
              Semantic vector search across recipe cards, food safety standards, kitchen hygiene, and operating manuals
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowIngestModal(true)}
          className="px-4 py-2 rounded-xl text-xs font-bold bg-terracotta-500 hover:bg-terracotta-600 text-ivory flex items-center gap-1.5 shadow-md shadow-terracotta-500/20 transition-all"
        >
          <UploadCloud className="w-4 h-4" />
          Ingest Operating SOP
        </button>
      </div>

      {/* Semantic Search Box */}
      <div className="p-6 rounded-2xl heritage-card space-y-4">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-muted-brown absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Query kitchen procedures (e.g. 'What is the standard procedure for dairy storage temperature?')"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink placeholder-muted-brown focus:outline-none focus:border-terracotta-500"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="px-3 py-2.5 rounded-xl bg-sandalwood/70 border border-sand text-xs text-maroon-900 font-semibold focus:outline-none cursor-pointer"
            >
              <option value={3}>Top 3 Passages</option>
              <option value={5}>Top 5 Passages</option>
              <option value={8}>Top 8 Passages</option>
            </select>

            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="px-5 py-2.5 rounded-xl text-xs font-bold bg-maroon-800 hover:bg-maroon-900 disabled:opacity-50 text-ivory transition-all shadow-md shadow-maroon-900/20 flex items-center gap-1.5"
            >
              {searching ? (
                <span>Retrieving...</span>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Retrieve Passages</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Quick Sample Queries */}
        <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-sand text-[11px] text-muted-brown">
          <span className="font-bold text-maroon-900">Standard Queries:</span>
          {[
            'Dairy storage temperature standards',
            'Espresso calibration and extraction parameters',
            'End of shift cash register reconciliation checklist',
            'Customer refund policy on damaged items',
          ].map((sample, sidx) => (
            <button
              key={sidx}
              onClick={() => {
                setQuery(sample);
              }}
              className="px-2.5 py-1 rounded-lg bg-sandalwood/60 hover:bg-sand/40 text-maroon-900 border border-sand transition-colors font-medium shadow-heritage-sm"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>

      {searchError && (
        <ErrorAlert title="Knowledge Search Notice" message={searchError} onRetry={handleSearch} />
      )}

      {/* Search Results Display */}
      {searching ? (
        <LoadingSpinner message="Querying pgvector dense embeddings via cosine similarity..." />
      ) : searchResults ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-muted-brown px-1">
            <span>
              Retrieved <strong className="text-maroon-900">{searchResults.total_results}</strong> relevant passages for query: &quot;
              <span className="text-terracotta-700 font-semibold">{searchResults.query}</span>&quot;
            </span>
            <Badge variant="synthetic" size="sm">
              Origin: {searchResults.data_origin}
            </Badge>
          </div>

          <div className="space-y-3">
            {searchResults.results.map((chunk) => {
              const simPct = (chunk.similarity * 100).toFixed(1);
              return (
                <div
                  key={chunk.chunk_id}
                  className="p-6 rounded-2xl heritage-card heritage-card-hover space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <FileText className="w-4 h-4 text-terracotta-600" />
                      <h4 className="text-xs font-bold text-maroon-900 font-serif">{chunk.source_title}</h4>
                      <span className="text-[10px] text-muted-brown font-mono">v{chunk.source_version}</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-forest-700 font-bold bg-forest-50 px-2.5 py-0.5 rounded-full border border-forest-200">
                        {simPct}% Similarity
                      </span>
                      <span className="text-[10px] text-muted-brown font-mono">
                        Page {chunk.page_number} (Chunk #{chunk.chunk_index})
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-ink leading-relaxed bg-sandalwood/50 p-4 rounded-xl border border-sand font-sans">
                    {chunk.chunk_text}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-muted-brown pt-1 border-t border-sand/40">
                    <span>
                      Citation Reference: <code className="text-maroon-900 bg-sandalwood font-bold px-1.5 py-0.5 rounded border border-sand font-mono">{chunk.citation}</code>
                    </span>
                    {chunk.effective_date && <span>Effective: {chunk.effective_date}</span>}
                  </div>
                </div>
              );
            })}

            {searchResults.results.length === 0 && (
              <div className="p-8 text-center text-xs text-muted-brown heritage-card">
                No matching passages found above the similarity threshold.
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Document Ingestion Modal */}
      {showIngestModal && (
        <div className="fixed inset-0 bg-[#30241F]/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="heritage-card max-w-xl w-full p-6 space-y-4 shadow-heritage-lg border-2 border-sand">
            <div className="flex items-center justify-between border-b border-sand pb-3">
              <h3 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-terracotta-500" />
                Ingest Kitchen & Hospitality SOP
              </h3>
              <button
                onClick={() => {
                  setShowIngestModal(false);
                  setIngestSuccess(null);
                  setIngestError(null);
                }}
                className="text-muted-brown hover:text-maroon-900 text-xs font-bold p-1"
              >
                Close
              </button>
            </div>

            {ingestSuccess && (
              <div className="p-3 rounded-xl bg-forest-50 border border-forest-200 text-forest-700 text-xs flex items-center gap-2 font-semibold">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-forest-600" />
                <span>{ingestSuccess}</span>
              </div>
            )}

            {ingestError && <ErrorAlert title="Ingestion Failed" message={ingestError} />}

            <form onSubmit={handleIngest} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-bold text-muted-brown uppercase mb-1">
                  Manual / Document Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Traditional Tea Steaming & Milk Boiling Protocol"
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  required
                  className="w-full px-3.5 py-2 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink focus:outline-none focus:border-terracotta-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-muted-brown uppercase mb-1">
                    Document Category
                  </label>
                  <select
                    value={docType}
                    onChange={(e) => setDocType(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink focus:outline-none cursor-pointer"
                  >
                    <option value="sop">SOP (Standard Operating Procedure)</option>
                    <option value="manual">Culinary Manual</option>
                    <option value="policy">Food Safety & Hygiene</option>
                    <option value="recipe">Master Recipe Specification</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-muted-brown uppercase mb-1">
                    Version
                  </label>
                  <input
                    type="text"
                    value={docVersion}
                    onChange={(e) => setDocVersion(e.target.value)}
                    placeholder="1.0"
                    className="w-full px-3 py-2 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-muted-brown uppercase mb-1">
                  Manual Body Content (Markdown / Text)
                </label>
                <textarea
                  rows={6}
                  placeholder="Paste complete procedural text and instructions here..."
                  value={docContent}
                  onChange={(e) => setDocContent(e.target.value)}
                  required
                  className="w-full p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink focus:outline-none focus:border-terracotta-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowIngestModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-sandalwood text-muted-brown hover:bg-sand/40 border border-sand"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={ingesting || !docTitle.trim() || !docContent.trim()}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-maroon-800 hover:bg-maroon-900 disabled:opacity-50 text-ivory shadow-md shadow-maroon-900/20"
                >
                  {ingesting ? 'Embedding Chunks...' : 'Vectorize & Index into pgvector'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
