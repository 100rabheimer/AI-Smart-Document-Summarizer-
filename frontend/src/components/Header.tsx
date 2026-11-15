import React from 'react';
import { HealthResponse, User } from '../types';
import { Database, Server, Cpu, LogIn, LogOut, Terminal } from 'lucide-react';

interface HeaderProps {
  health: HealthResponse | null;
  loading: boolean;
  user: User | null;
  onLogin: () => void;
  onLogout: () => void;
  onDevLogin?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  loading,
  user,
  onLogin,
  onLogout,
  onDevLogin,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-indigo-500/20">
          🧠
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            DocMind <span className="text-xs bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-full font-medium">v1.0 MVP</span>
          </h1>
          <p className="text-xs text-slate-400">Grounded RAG Assistant with Verifiable Citations</p>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {/* Backend Status Pill */}
        <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700/60 px-3 py-1.5 rounded-lg">
          <Server className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-300 font-medium">API:</span>
          {loading ? (
            <span className="text-amber-400 animate-pulse">Connecting...</span>
          ) : health?.status === 'ok' ? (
            <span className="inline-flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              Online
            </span>
          ) : (
            <span className="text-rose-400 font-medium">Degraded</span>
          )}
        </div>

        {/* Database Status */}
        <div className="flex items-center gap-1.5 text-slate-400 bg-slate-800/40 px-2.5 py-1.5 rounded-lg border border-slate-700/40">
          <Database className="w-3.5 h-3.5" />
          <span>pgvector:</span>
          <span className={health?.dependencies.database ? "text-emerald-400" : "text-rose-400"}>
            {health?.dependencies.database ? "Active" : "Offline"}
          </span>
        </div>

        {/* Redis Status */}
        <div className="flex items-center gap-1.5 text-slate-400 bg-slate-800/40 px-2.5 py-1.5 rounded-lg border border-slate-700/40">
          <Cpu className="w-3.5 h-3.5" />
          <span>Redis:</span>
          <span className={health?.dependencies.redis ? "text-emerald-400" : "text-rose-400"}>
            {health?.dependencies.redis ? "Active" : "Offline"}
          </span>
        </div>

        {/* Auth Section */}
        {user ? (
          <div className="flex items-center gap-3 pl-2 border-l border-slate-800">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name}
                className="w-7 h-7 rounded-full border border-slate-700"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-indigo-500/20 text-indigo-400 font-bold flex items-center justify-center border border-indigo-500/40">
                {user.name.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="text-left hidden sm:block">
              <p className="text-xs font-semibold text-white leading-tight">{user.name}</p>
              <p className="text-[10px] text-slate-400 truncate max-w-[120px]">{user.email}</p>
            </div>
            <button
              onClick={onLogout}
              className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1.5 rounded-lg border border-slate-700 transition"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Exit</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            {onDevLogin && (
              <button
                onClick={onDevLogin}
                className="flex items-center gap-1.5 bg-emerald-700/80 hover:bg-emerald-600 text-white font-medium px-3 py-1.5 rounded-lg shadow-sm transition text-xs border border-emerald-600/50"
                title="Bypasses Google OAuth for local development & testing"
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>Dev Login</span>
              </button>
            )}
            <button
              onClick={onLogin}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-3.5 py-1.5 rounded-lg shadow-md shadow-indigo-600/30 transition text-xs"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign in with Google</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
