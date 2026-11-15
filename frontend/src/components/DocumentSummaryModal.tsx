import React from 'react';
import { X, Sparkles, CheckCircle2, Users, BookOpen } from 'lucide-react';
import { DocumentItem, DocumentSummary } from '../types';

interface DocumentSummaryModalProps {
  document: DocumentItem | null;
  summary: DocumentSummary | null;
  loading: boolean;
  onClose: () => void;
}

export const DocumentSummaryModal: React.FC<DocumentSummaryModalProps> = ({
  document,
  summary,
  loading,
  onClose,
}) => {
  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-100">Document AI Summary</h3>
              <p className="text-xs text-slate-400 truncate max-w-md">{document.filename}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-400">Extracting key concepts & generating structured summary...</p>
            </div>
          ) : summary ? (
            <>
              {/* Executive Overview */}
              <div>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2">
                  <BookOpen className="w-4 h-4" /> Executive Overview
                </h4>
                <p className="text-sm leading-relaxed text-slate-300 bg-slate-950/50 p-4 rounded-xl border border-slate-800/60">
                  {summary.overview}
                </p>
              </div>

              {/* Key Topics */}
              {summary.key_topics && summary.key_topics.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2">
                    Key Topics Covered
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {summary.key_topics.map((topic, i) => (
                      <span
                        key={i}
                        className="px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 border border-indigo-500/20 text-indigo-300"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Critical Insights */}
              {summary.critical_insights && summary.critical_insights.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-2">
                    Critical Insights & Findings
                  </h4>
                  <ul className="space-y-2">
                    {summary.critical_insights.map((insight, i) => (
                      <li key={i} className="flex items-start gap-2.5 text-xs text-slate-300">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Target Audience */}
              {summary.target_audience && (
                <div className="pt-2 border-t border-slate-800/60 flex items-center gap-2 text-xs text-slate-400">
                  <Users className="w-4 h-4 text-slate-400" />
                  <span>
                    <strong className="text-slate-300">Target Audience:</strong> {summary.target_audience}
                  </span>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-8 text-sm text-slate-400">
              No summary available for this document.
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-slate-950/60 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
