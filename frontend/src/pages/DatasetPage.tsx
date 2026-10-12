import React, { useState, useRef } from 'react';
import {
  Database,
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Layers,
  FileCheck,
  Check,
  ArrowRight,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { DatasetPreviewResponse, DatasetIngestResponse } from '../api/types';
import { useDataset } from '../context/DatasetContext';
import { Badge } from '../components/common/Badge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { formatIndianNumber } from '../utils/formatters';

export const DatasetPage: React.FC = () => {
  const {
    selectedDatasetId,
    setSelectedDatasetId,
    restaurantId,
    datasets,
    refreshDatasets,
    loadingDatasets,
  } = useDataset();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState<string>('');
  const [previewData, setPreviewData] = useState<DatasetPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [ingestLoading, setIngestLoading] = useState<boolean>(false);
  const [ingestResult, setIngestResult] = useState<DatasetIngestResponse | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setDatasetName(file.name.replace(/\.[^/.]+$/, ''));
      setPreviewData(null);
      setPreviewError(null);
      setIngestResult(null);
      setIngestError(null);
    }
  };

  const handlePreview = async () => {
    if (!selectedFile || previewLoading) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await apiClient.previewDataset(selectedFile, restaurantId);
      setPreviewData(res);
    } catch (err: any) {
      setPreviewError(err?.message || 'Failed to preview dataset.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleIngest = async () => {
    if (!selectedFile || ingestLoading) return;
    setIngestLoading(true);
    setIngestError(null);
    try {
      const res = await apiClient.ingestDataset(
        selectedFile,
        datasetName.trim() || undefined,
        restaurantId
      );
      setIngestResult(res);
      if (res.dataset_id) {
        setSelectedDatasetId(res.dataset_id);
      }
      refreshDatasets();
    } catch (err: any) {
      setIngestError(err?.message || 'Failed to import and ingest dataset into database.');
    } finally {
      setIngestLoading(false);
    }
  };

  const currentStep = ingestResult ? 4 : previewData?.is_valid ? 3 : selectedFile ? 2 : 1;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-5 rounded-2xl heritage-card flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-2.5 rounded-xl bg-forest-50 text-forest-700 border border-forest-200">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-maroon-900 font-serif flex items-center gap-2">
              Restaurant Dataset Ingestion & Validation
              <Badge variant="success" size="sm">
                Multi-Tenant Scoped
              </Badge>
            </h2>
            <p className="text-xs text-muted-brown">
              Upload CSV POS exports or multi-table ZIP archives with automated schema validation
            </p>
          </div>
        </div>

        <button
          onClick={() => refreshDatasets()}
          disabled={loadingDatasets}
          className="p-2.5 rounded-xl bg-ivory hover:bg-sandalwood text-maroon-800 border border-sand transition-colors flex items-center gap-1.5 text-xs font-bold shadow-heritage-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingDatasets ? 'animate-spin' : ''}`} />
          Refresh Datasets
        </button>
      </div>

      {/* Visual Step-Based Progress Bar */}
      <div className="p-4 rounded-2xl heritage-card flex items-center justify-between overflow-x-auto text-xs">
        {[
          { step: 1, label: '1. Select File' },
          { step: 2, label: '2. Schema Preview' },
          { step: 3, label: '3. Validation' },
          { step: 4, label: '4. Ingest & Scope' },
        ].map((s, idx) => (
          <React.Fragment key={s.step}>
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                  currentStep >= s.step
                    ? 'bg-maroon-800 text-ivory'
                    : 'bg-sand text-muted-brown'
                }`}
              >
                {s.step}
              </span>
              <span
                className={`font-semibold ${
                  currentStep >= s.step ? 'text-maroon-900 font-bold' : 'text-muted-brown'
                }`}
              >
                {s.label}
              </span>
            </div>
            {idx < 3 && <ArrowRight className="w-4 h-4 text-sand shrink-0 mx-2" />}
          </React.Fragment>
        ))}
      </div>

      {/* Upload & Dry-Run Preview Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload & Configure Card */}
        <div className="heritage-card p-6 space-y-4">
          <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
            <Upload className="w-4 h-4 text-terracotta-500" />
            Upload Dataset File
          </h3>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-sand hover:border-terracotta-500 rounded-2xl p-6 text-center cursor-pointer transition-all bg-sandalwood/40 hover:bg-sandalwood/70 flex flex-col items-center justify-center gap-2"
          >
            <div className="w-12 h-12 rounded-2xl bg-ivory flex items-center justify-center text-terracotta-500 shadow-sm border border-sand">
              <FileSpreadsheet className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-bold text-maroon-900">
                {selectedFile ? selectedFile.name : 'Select CSV or ZIP archive'}
              </p>
              <p className="text-[10px] text-muted-brown mt-0.5">
                {selectedFile
                  ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                  : 'Supports sales, menu, feedback, or inventory exports'}
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.zip"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          {selectedFile && (
            <div className="space-y-3 pt-3 border-t border-sand">
              <div>
                <label className="block text-[11px] font-bold text-muted-brown uppercase mb-1">
                  Dataset Label
                </label>
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g. Diwali Weekend Sales & Inventory"
                  className="w-full px-3.5 py-2 rounded-xl bg-sandalwood/50 border border-sand text-xs text-ink focus:outline-none focus:border-terracotta-500 font-medium"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handlePreview}
                  disabled={previewLoading}
                  className="flex-1 py-2 px-3 rounded-xl text-xs font-bold bg-ivory hover:bg-sandalwood text-maroon-900 border border-sand transition-all flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <FileCheck className="w-3.5 h-3.5 text-terracotta-600" />
                  {previewLoading ? 'Verifying...' : 'Dry-Run Preview'}
                </button>

                <button
                  onClick={handleIngest}
                  disabled={ingestLoading || (previewData ? !previewData.is_valid : false)}
                  className="flex-1 py-2 px-3 rounded-xl text-xs font-bold bg-terracotta-500 hover:bg-terracotta-600 disabled:opacity-50 text-ivory transition-all shadow-md shadow-terracotta-500/20 flex items-center justify-center gap-1.5"
                >
                  <Database className="w-3.5 h-3.5" />
                  {ingestLoading ? 'Ingesting...' : 'Ingest to DB'}
                </button>
              </div>
            </div>
          )}

          {previewError && <ErrorAlert title="Validation Notice" message={previewError} />}
          {ingestError && <ErrorAlert title="Ingestion Notice" message={ingestError} />}

          {ingestResult && (
            <div className="p-4 rounded-xl bg-forest-50 border border-forest-200 text-forest-700 text-xs space-y-1.5 shadow-heritage-sm">
              <div className="flex items-center gap-1.5 font-bold">
                <CheckCircle2 className="w-4 h-4 text-forest-600" />
                Ingestion Completed Successfully!
              </div>
              <p className="text-[11px] text-muted-brown">
                Dataset ID: <code className="font-mono text-forest-700 font-bold">{ingestResult.dataset_id}</code>
              </p>
              <p className="text-[11px] text-muted-brown">
                Imported <strong className="text-maroon-900">{formatIndianNumber(ingestResult.rows_ingested)}</strong> records across{' '}
                {ingestResult.detected_sections?.join(', ')}.
              </p>
            </div>
          )}
        </div>

        {/* Validation & Preview Output */}
        <div className="lg:col-span-2 heritage-card p-6 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
                Schema Dry-Run & Column Mapping Output
              </h3>
              <p className="text-xs text-muted-brown">
                Non-mutating verification of columns, types, and required table attributes
              </p>
            </div>
            {previewData && (
              <Badge variant={previewData.is_valid ? 'success' : 'error'} size="sm">
                {previewData.is_valid ? 'Validation Passed' : 'Validation Failed'}
              </Badge>
            )}
          </div>

          {previewLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <LoadingSpinner message="Parsing column headers, normalizing aliases, and checking integrity..." />
            </div>
          ) : previewData ? (
            <div className="space-y-4 overflow-y-auto max-h-[460px]">
              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                  <span className="text-muted-brown text-[10px] font-bold uppercase">Total Rows</span>
                  <div className="font-mono font-bold text-maroon-900 text-base">{formatIndianNumber(previewData.total_rows)}</div>
                </div>
                <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                  <span className="text-muted-brown text-[10px] font-bold uppercase">Detected Sections</span>
                  <div className="font-bold text-forest-700 text-xs truncate">
                    {previewData.detected_sections.join(', ')}
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-sandalwood/50 border border-sand text-xs">
                  <span className="text-muted-brown text-[10px] font-bold uppercase">Duplicate Check</span>
                  <div className="font-mono text-xs text-ink font-semibold">
                    {previewData.is_duplicate ? 'Existing Hash' : 'Unique Content'}
                  </div>
                </div>
              </div>

              {/* Warnings or Errors */}
              {previewData.validation_errors.length > 0 && (
                <div className="p-3.5 rounded-xl bg-maroon-50 border border-maroon-200 text-maroon-900 text-xs">
                  <span className="font-bold flex items-center gap-1 mb-1 text-maroon-800">
                    <AlertTriangle className="w-3.5 h-3.5 text-maroon-600" /> Validation Errors:
                  </span>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                    {previewData.validation_errors.map((err, eidx) => (
                      <li key={eidx}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}

              {previewData.warnings.length > 0 && (
                <div className="p-3.5 rounded-xl bg-saffron-50 border border-saffron-200 text-saffron-800 text-xs">
                  <span className="font-bold flex items-center gap-1 mb-1 text-saffron-700">
                    <AlertTriangle className="w-3.5 h-3.5 text-saffron-600" /> Schema Warnings:
                  </span>
                  <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                    {previewData.warnings.map((w, widx) => (
                      <li key={widx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Files / Sections Breakdown */}
              {previewData.files_summary.map((f, fidx) => (
                <div key={fidx} className="p-4 rounded-xl bg-sandalwood/40 border border-sand space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-bold text-maroon-900">
                    <span className="flex items-center gap-1.5 font-serif">
                      <Layers className="w-3.5 h-3.5 text-terracotta-600" />
                      {f.filename} ({f.detected_section})
                    </span>
                    <span className="font-mono text-forest-700 font-bold">{formatIndianNumber(f.row_count)} rows</span>
                  </div>

                  {f.column_mapping && Object.keys(f.column_mapping).length > 0 && (
                    <div className="text-[11px] text-muted-brown">
                      <span className="font-bold text-ink">Column Mapping:</span>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {Object.entries(f.column_mapping).map(([col, target], cidx) => (
                          <span
                            key={cidx}
                            className="px-2 py-0.5 rounded-md bg-ivory font-mono text-[10px] text-ink border border-sand shadow-sm"
                          >
                            {col} &rarr; <strong className="text-terracotta-700">{target}</strong>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Sample Records Table */}
                  {f.sample_records && f.sample_records.length > 0 && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-left text-[10px] font-mono">
                        <thead>
                          <tr className="border-b border-sand text-muted-brown font-bold">
                            {Object.keys(f.sample_records[0]).slice(0, 5).map((k) => (
                              <th key={k} className="pb-1 pr-2">{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-sand/50 text-ink">
                          {f.sample_records.slice(0, 3).map((rec, ridx) => (
                            <tr key={ridx}>
                              {Object.values(rec).slice(0, 5).map((val: any, vidx) => (
                                <td key={vidx} className="py-1 pr-2 truncate max-w-[120px]">
                                  {String(val)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-muted-brown text-xs">
              <FileSpreadsheet className="w-10 h-10 text-sand mb-2" />
              <p>Select a CSV or ZIP file on the left and click &quot;Dry-Run Preview&quot; to inspect column mapping.</p>
            </div>
          )}
        </div>
      </div>

      {/* Uploaded Datasets List & Switcher */}
      <div className="heritage-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-maroon-900 font-serif flex items-center gap-2">
              <Database className="w-4 h-4 text-forest-600" />
              Active Restaurant Datasets
            </h3>
            <p className="text-xs text-muted-brown">
              Scoped datasets saved in Supabase dataset_records ledger
            </p>
          </div>
          <Badge variant="purple" size="sm">
            {datasets.length} Datasets Available
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Baseline Option */}
          <div
            onClick={() => setSelectedDatasetId(null)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              selectedDatasetId === null
                ? 'border-terracotta-500 bg-sandalwood/60 ring-1 ring-terracotta-500/20 shadow-heritage'
                : 'border-sand bg-ivory hover:border-saffron-300'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-maroon-900 font-serif">Default Baseline</span>
              {selectedDatasetId === null && (
                <span className="flex items-center gap-1 text-[11px] font-bold text-forest-700">
                  <Check className="w-3.5 h-3.5" /> Selected
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-brown mb-2 font-sans">
              Integrated synthetic restaurant baseline data across all core endpoints.
            </p>
            <Badge variant="synthetic" size="sm">
              Origin: SYNTHETIC
            </Badge>
          </div>

          {/* Ingested Datasets */}
          {datasets.map((d) => {
            const isSelected = selectedDatasetId === d.dataset_id;
            return (
              <div
                key={d.dataset_id}
                onClick={() => setSelectedDatasetId(d.dataset_id)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? 'border-terracotta-500 bg-sandalwood/60 ring-1 ring-terracotta-500/20 shadow-heritage'
                    : 'border-sand bg-ivory hover:border-saffron-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-maroon-900 font-serif truncate max-w-[180px]">
                    {d.dataset_name || d.original_filename}
                  </span>
                  {isSelected && (
                    <span className="flex items-center gap-1 text-[11px] font-bold text-forest-700">
                      <Check className="w-3.5 h-3.5" /> Selected
                    </span>
                  )}
                </div>
                <div className="font-mono text-[10px] text-muted-brown mb-2 truncate">
                  ID: {d.dataset_id}
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-brown">
                  <span className="font-semibold">{formatIndianNumber(d.row_count)} rows</span>
                  <Badge variant="purple" size="sm">
                    {d.detected_section}
                  </Badge>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
