import { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { DocumentUpload } from './components/DocumentUpload';
import { DocumentList } from './components/DocumentList';
import { DocumentSummaryModal } from './components/DocumentSummaryModal';
import { ChatPanel } from './components/ChatPanel';
import {
  HealthResponse,
  User,
  DocumentItem,
  DocumentSummary,
  Conversation,
} from './types';
import {
  ShieldCheck,
  Zap,
  BookOpen,
  MessageSquare,
  UserCheck,
  Database,
  FileCheck2,
  LogIn,
} from 'lucide-react';

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [user, setUser] = useState<User | null>(null);

  // Document management state
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState<boolean>(false);
  const [selectedSummaryDoc, setSelectedSummaryDoc] = useState<DocumentItem | null>(null);
  const [documentSummary, setDocumentSummary] = useState<DocumentSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState<boolean>(false);

  // Conversation state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);

  // 1. Fetch system health
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
      } catch {
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

  // 2. Fetch current user session
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

  // 3. Fetch user's documents
  const fetchDocuments = useCallback(async () => {
    if (!user) return;
    setLoadingDocs(true);
    try {
      const res = await fetch('/api/v1/documents');
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error('Failed to fetch documents', err);
    } finally {
      setLoadingDocs(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchDocuments();
    }
  }, [user, fetchDocuments]);

  // Polling when any document is still processing
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'processing' || d.status === 'pending');
    if (!hasProcessing) return;

    const pollInterval = setInterval(() => {
      fetchDocuments();
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [documents, fetchDocuments]);

  // 4. Fetch user's conversations
  const fetchConversations = useCallback(async () => {
    if (!user) return;
    try {
      const res = await fetch('/api/v1/conversations');
      if (res.ok) {
        const data: Conversation[] = await res.json();
        setConversations(data);
        if (data.length > 0 && !activeConversation) {
          setActiveConversation(data[0]);
        }
      }
    } catch (err) {
      console.error('Failed to fetch conversations', err);
    }
  }, [user, activeConversation]);

  useEffect(() => {
    if (user) {
      fetchConversations();
    }
  }, [user, fetchConversations]);

  // 5. Create new conversation thread
  async function handleCreateConversation(): Promise<Conversation | null> {
    try {
      const title = `Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      const res = await fetch('/api/v1/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });

      if (res.ok) {
        const newConv: Conversation = await res.json();
        setConversations((prev) => [newConv, ...prev]);
        setActiveConversation(newConv);
        return newConv;
      }
    } catch (err) {
      console.error('Failed to create conversation', err);
    }
    return null;
  }

  // 6. Delete document
  async function handleDeleteDocument(docId: string) {
    try {
      const res = await fetch(`/api/v1/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== docId));
      }
    } catch (err) {
      console.error('Failed to delete document', err);
    }
  }

  // 7. View structured summary
  async function handleSelectSummary(doc: DocumentItem) {
    setSelectedSummaryDoc(doc);
    setLoadingSummary(true);
    setDocumentSummary(null);

    try {
      const res = await fetch(`/api/v1/documents/${doc.id}/summary`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setDocumentSummary(data);
      }
    } catch (err) {
      console.error('Failed to fetch summary', err);
    } finally {
      setLoadingSummary(false);
    }
  }

  // 8. Handle Google OAuth sign-in redirect
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

  // 9. Handle sign-out
  async function handleLogout() {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST' });
      setUser(null);
      setDocuments([]);
      setConversations([]);
      setActiveConversation(null);
    } catch (err) {
      console.error('Failed to log out', err);
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500/30">
      <Header
        health={health}
        loading={loadingHealth}
        user={user}
        onLogin={handleGoogleLogin}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col gap-6">
        {user ? (
          <>
            {/* Logged in Tenant Status Header */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xl">
              <div className="flex items-center gap-3.5">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={user.name}
                    className="w-11 h-11 rounded-full border border-indigo-500/40 object-cover shadow-sm"
                  />
                ) : (
                  <div className="w-11 h-11 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-lg border border-indigo-500/30">
                    <UserCheck className="w-5 h-5" />
                  </div>
                )}
                <div>
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    Welcome back, {user.name}
                  </h2>
                  <p className="text-xs text-slate-400">
                    Active Multi-Tenant Session: <span className="font-mono text-indigo-300">{user.email}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                  <Database className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="text-slate-400">Knowledge:</span>
                  <span className="font-semibold text-slate-200">{documents.length} docs</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                  <FileCheck2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-slate-400">Chunks:</span>
                  <span className="font-semibold text-emerald-300">pgvector ready</span>
                </div>
              </div>
            </div>

            {/* Core Two-Column Product Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-[620px]">
              {/* Left Column: Document Upload & Knowledge Base (5 of 12 cols) */}
              <div className="lg:col-span-5 flex flex-col gap-6">
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <span>Upload Documents</span>
                  </h3>
                  <DocumentUpload onUploadSuccess={fetchDocuments} />
                </div>

                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl flex-1">
                  <DocumentList
                    documents={documents}
                    loading={loadingDocs}
                    onSelectSummary={handleSelectSummary}
                    onDeleteDocument={handleDeleteDocument}
                  />
                </div>
              </div>

              {/* Right Column: Intelligent Chat with Verifiable Citations (7 of 12 cols) */}
              <div className="lg:col-span-7 flex flex-col min-h-[560px]">
                <ChatPanel
                  conversations={conversations}
                  activeConversation={activeConversation}
                  onSelectConversation={(conv) => setActiveConversation(conv)}
                  onCreateConversation={handleCreateConversation}
                  hasDocuments={documents.some((d) => d.status === 'completed')}
                />
              </div>
            </div>

            {/* Structured Summary Modal */}
            <DocumentSummaryModal
              document={selectedSummaryDoc}
              summary={documentSummary}
              loading={loadingSummary}
              onClose={() => {
                setSelectedSummaryDoc(null);
                setDocumentSummary(null);
              }}
            />
          </>
        ) : (
          /* Logged out: Landing Showcase */
          <div className="flex flex-col gap-10 py-6 max-w-5xl mx-auto w-full">
            <div className="bg-gradient-to-b from-slate-900 to-slate-900/60 border border-slate-800 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden text-center flex flex-col items-center">
              <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

              <div className="inline-flex items-center gap-2 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs font-semibold px-4 py-1.5 rounded-full mb-6">
                <BookOpen className="w-3.5 h-3.5" />
                DocMind • Production-Grade Knowledge Assistant
              </div>

              <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-4 max-w-2xl">
                Chat with your documents with <span className="text-indigo-400">verifiable citations</span>.
              </h1>

              <p className="text-slate-400 max-w-xl text-sm sm:text-base leading-relaxed mb-8">
                DocMind eliminates LLM hallucinations by enforcing sentence-level chunk citations,
                PostgreSQL <code className="text-indigo-400">pgvector</code> search, and strict multi-tenant isolation.
              </p>

              <button
                onClick={handleGoogleLogin}
                className="flex items-center gap-3 px-6 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/30 hover:scale-[1.02]"
              >
                <LogIn className="w-4 h-4" />
                <span>Sign in with Google to Start</span>
              </button>
            </div>

            {/* Architecture Highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 hover:border-slate-700 transition">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-white text-base mb-1">Authentic OAuth & Multi-Tenancy</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Real Google OAuth login with hashed PostgreSQL sessions in HTTP-only cookies. Every vector chunk is filtered strictly by user_id.
                </p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 hover:border-slate-700 transition">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-4">
                  <Zap className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-white text-base mb-1">O(1) Redis Invalidation</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Tenant-scoped document version counter purges stale query caches instantaneously without O(N) scanning.
                </p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 hover:border-slate-700 transition">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-white text-base mb-1">Streaming & Verifiable Citations</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Real-time SSE token streaming paired with clickable citation cards proving the exact document and page number for every claim.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
