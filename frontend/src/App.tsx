import { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { HealthResponse, User } from './types';
import { Layers, ShieldCheck, Zap, BookOpen, MessageSquare, ArrowRight, UserCheck } from 'lucide-react';

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [user, setUser] = useState<User | null>(null);

  // Fetch system health
  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/v1/health');
        if (res.ok) {
          const data = await res.json();
          setHealth(data);
        } else {
          setHealth({
            status: 'degraded',
            environment: 'development',
            dependencies: { database: false, redis: false },
          });
        }
      } catch (err) {
        setHealth({
          status: 'degraded',
          environment: 'development',
          dependencies: { database: false, redis: false },
        });
      } finally {
        setLoadingHealth(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch current user session
  async function fetchCurrentUser() {
    try {
      const res = await fetch('/api/v1/auth/me');
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  // Handle Google OAuth sign-in redirect
  async function handleGoogleLogin() {
    try {
      const res = await fetch('/api/v1/auth/login/google');
      if (res.ok) {
        const data = await res.json();
        window.location.href = data.url;
      }
    } catch (err) {
      console.error('Failed to initiate Google login', err);
    }
  }

  // Handle sign-out
  async function handleLogout() {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
      setUser(null);
    } catch (err) {
      console.error('Failed to log out', err);
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      <Header
        health={health}
        loading={loadingHealth}
        user={user}
        onLogin={handleGoogleLogin}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-12 flex flex-col gap-10">
        {/* User Welcome Banner if logged in */}
        {user ? (
          <div className="bg-emerald-950/30 border border-emerald-800/50 rounded-2xl p-6 flex items-center justify-between shadow-xl">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xl font-bold border border-emerald-500/30">
                <UserCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  Welcome back, {user.name}!
                </h3>
                <p className="text-xs text-emerald-300/80">
                  Authenticated with authentic Google account: <span className="font-mono text-emerald-200">{user.email}</span>
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-medium">
                Tenant ID: {user.id.slice(0, 8)}...
              </span>
            </div>
          </div>
        ) : null}

        {/* Hero Section */}
        <div className="bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          
          <div className="inline-flex items-center gap-2 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs font-semibold px-3 py-1 rounded-full mb-4">
            <Layers className="w-3.5 h-3.5" />
            Phase 2: Authentication & Multi-Tenancy Completed
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-white mb-3">
            Production-Grade RAG Architecture
          </h2>
          <p className="text-slate-400 max-w-2xl text-sm leading-relaxed mb-6">
            DocMind combines PostgreSQL (<code className="text-indigo-400">pgvector</code>), Redis caching,
            and Google OAuth into a high-performance, citation-backed knowledge assistant.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-800/80">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm">
                ✓
              </div>
              <div>
                <p className="text-xs text-slate-400">Authentication</p>
                <p className="text-sm font-semibold text-slate-200">Google OAuth 2.0</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm">
                ✓
              </div>
              <div>
                <p className="text-xs text-slate-400">Session Security</p>
                <p className="text-sm font-semibold text-slate-200">Hashed HTTP-only Cookies</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm">
                ✓
              </div>
              <div>
                <p className="text-xs text-slate-400">Tenant Isolation</p>
                <p className="text-sm font-semibold text-slate-200">Strict user_id Scoping</p>
              </div>
            </div>
          </div>
        </div>

        {/* Next Milestones Preview */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Upcoming Architectural Phases
            </h3>
            <span className="text-xs text-indigo-400 font-medium">Brick by Brick Roadmap</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Card 1 */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700 transition">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h4 className="font-semibold text-white text-sm mb-1">Phase 2: Auth Complete</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Google OAuth, SHA-256 session token hashing, and get_current_user guard.
              </p>
            </div>

            {/* Card 2 */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700 transition">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-3">
                <Zap className="w-4 h-4" />
              </div>
              <h4 className="font-semibold text-white text-sm mb-1">Phase 3: Redis Invalidation</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Sliding-window rate limiting and O(1) document-version cache invalidation.
              </p>
            </div>

            {/* Card 3 */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700 transition">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-3">
                <BookOpen className="w-4 h-4" />
              </div>
              <h4 className="font-semibold text-white text-sm mb-1">Phase 4 & 5: RAG Pipeline</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                PDF/TXT/MD chunking, Gemini embeddings, and cosine vector retrieval.
              </p>
            </div>

            {/* Card 4 */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700 transition">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-3">
                <MessageSquare className="w-4 h-4" />
              </div>
              <h4 className="font-semibold text-white text-sm mb-1">Streaming & Citations</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                SSE streaming chat responses with clickable chunk citation popovers.
              </p>
            </div>
          </div>
        </div>

        {/* Ready indicator */}
        <div className="bg-slate-900/30 border border-slate-800/60 rounded-xl p-4 flex items-center justify-between">
          <p className="text-xs text-slate-400">
            Ready to proceed to Phase 3: Redis Invalidation, Idempotency & Rate Limiting?
          </p>
          <div className="flex items-center gap-1.5 text-xs text-indigo-400 font-semibold cursor-pointer">
            Proceed to Phase 3 <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
