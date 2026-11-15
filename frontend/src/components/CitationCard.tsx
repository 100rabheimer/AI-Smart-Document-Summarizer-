import React from 'react';
import { FileText, Bookmark } from 'lucide-react';
import { Citation } from '../types';

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation, index }) => {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-900 border border-slate-700/80 text-slate-300 hover:border-indigo-500/50 hover:bg-indigo-950/30 hover:text-indigo-200 transition-all cursor-default shadow-sm"
      title={`Source Chunk #${citation.chunk_index} in ${citation.document_filename}`}
    >
      <span className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] font-bold">
        {index + 1}
      </span>
      <FileText className="w-3.5 h-3.5 text-indigo-400" />
      <span className="truncate max-w-[140px] font-mono text-[11px]">{citation.document_filename}</span>
      <span className="text-slate-400 font-mono text-[11px] border-l border-slate-700 pl-1.5 flex items-center gap-0.5">
        <Bookmark className="w-2.5 h-2.5 text-slate-400" />
        p.{citation.page_number}
      </span>
    </div>
  );
};
