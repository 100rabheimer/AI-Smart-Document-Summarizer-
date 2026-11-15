import React, { useState } from 'react';
import { FileText, Sparkles, Trash2, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { DocumentItem } from '../types';

interface DocumentListProps {
  documents: DocumentItem[];
  loading: boolean;
  onSelectSummary: (doc: DocumentItem) => void;
  onDeleteDocument: (docId: string) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  loading,
  onSelectSummary,
  onDeleteDocument,
}) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function formatDate(isoString: string): string {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return '';
    }
  }

  async function handleDelete(docId: string, filename: string) {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? All chunks and embeddings will be removed.`)) {
      return;
    }
    setDeletingId(docId);
    try {
      await onDeleteDocument(docId);
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-slate-400 gap-2 text-sm">
        <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
        <span>Loading knowledge base...</span>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="border border-dashed border-slate-800/80 rounded-xl p-8 text-center text-slate-400 flex flex-col items-center gap-2">
        <FileText className="w-8 h-8 text-slate-400 mb-1" />
        <p className="text-sm font-medium text-slate-300">No documents uploaded yet</p>
        <p className="text-xs text-slate-400 max-w-xs">
          Upload your company reports, technical specs, or research PDFs above to start chatting with them.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
        <span>Knowledge Base ({documents.length})</span>
      </div>

      <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="group flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700 hover:bg-slate-900 transition-all shadow-sm"
          >
            <div className="flex items-center gap-3 min-w-0 pr-2">
              <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center flex-shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate" title={doc.filename}>
                  {doc.filename}
                </p>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span>{formatBytes(doc.file_size)}</span>
                  <span>•</span>
                  <span>{formatDate(doc.created_at)}</span>
                  <span>•</span>
                  {doc.status === 'completed' && (
                    <span className="flex items-center gap-1 text-emerald-400 font-medium">
                      <CheckCircle className="w-3 h-3" /> Ready
                    </span>
                  )}
                  {doc.status === 'processing' && (
                    <span className="flex items-center gap-1 text-amber-400 font-medium">
                      <Loader2 className="w-3 h-3 animate-spin" /> Chunking...
                    </span>
                  )}
                  {doc.status === 'failed' && (
                    <span className="flex items-center gap-1 text-rose-400 font-medium" title={doc.error_message || 'Processing failed'}>
                      <AlertTriangle className="w-3 h-3" /> Failed
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 flex-shrink-0">
              <button
                onClick={() => onSelectSummary(doc)}
                disabled={doc.status !== 'completed'}
                title="View AI Structured Summary"
                className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-300 hover:bg-indigo-500/10 border border-transparent hover:border-indigo-500/20 transition disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleDelete(doc.id, doc.filename)}
                disabled={deletingId === doc.id}
                title="Delete Document"
                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition disabled:opacity-40"
              >
                {deletingId === doc.id ? (
                  <Loader2 className="w-4 h-4 animate-spin text-rose-400" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
