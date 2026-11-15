import React, { useState, useEffect, useRef } from 'react';
import { Send, Plus, Bot, User as UserIcon, Loader2, Sparkles, ShieldAlert } from 'lucide-react';
import { Conversation, Message, Citation } from '../types';
import { CitationCard } from './CitationCard';

interface ChatPanelProps {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  onSelectConversation: (conv: Conversation) => void;
  onCreateConversation: () => Promise<Conversation | null>;
  hasDocuments: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  conversations,
  activeConversation,
  onSelectConversation,
  onCreateConversation,
  hasDocuments,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Load messages whenever active conversation changes
  useEffect(() => {
    if (!activeConversation) {
      setMessages([]);
      return;
    }

    async function fetchMessages() {
      setLoadingMessages(true);
      try {
        const res = await fetch(`/api/v1/conversations/${activeConversation?.id}/messages`);
        if (res.ok) {
          const data = await res.json();
          setMessages(data);
        }
      } catch (err) {
        console.error('Failed to load conversation messages', err);
      } finally {
        setLoadingMessages(false);
      }
    }

    fetchMessages();
  }, [activeConversation?.id]);

  // Handle SSE streaming query submission
  async function handleSendMessage(questionToSend?: string) {
    const question = (questionToSend || inputQuestion).trim();
    if (!question || isStreaming) return;

    let targetConversation = activeConversation;
    if (!targetConversation) {
      targetConversation = await onCreateConversation();
      if (!targetConversation) return;
    }

    setInputQuestion('');
    setIsStreaming(true);
    setStreamingContent('');
    setStreamingCitations([]);

    // Optimistically add user question to UI
    const tempUserMessage: Message = {
      id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
      conversation_id: targetConversation.id,
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMessage]);

    try {
      const response = await fetch(`/api/v1/conversations/${targetConversation.id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || `Query failed with HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('ReadableStream not supported on this response.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulatedText = '';
      let gatheredCitations: Citation[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep partial line

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const payload = JSON.parse(jsonStr);
            if (payload.type === 'token') {
              accumulatedText += payload.content;
              setStreamingContent(accumulatedText);
            } else if (payload.type === 'citations') {
              gatheredCitations = payload.citations || [];
              setStreamingCitations(gatheredCitations);
            } else if (payload.type === 'error') {
              accumulatedText += `\n[Error: ${payload.message}]`;
              setStreamingContent(accumulatedText);
            }
          } catch {
            // Ignore parse errors on incomplete chunk
          }
        }
      }

      // Add finalized assistant message
      const finalizedAssistantMessage: Message = {
        id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + 1),
        conversation_id: targetConversation.id,
        role: 'assistant',
        content: accumulatedText,
        citations: gatheredCitations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, finalizedAssistantMessage]);
    } catch (err: any) {
      const errorMessage: Message = {
        id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + 1),
        conversation_id: targetConversation.id,
        role: 'assistant',
        content: `Sorry, an error occurred while processing your query: ${err.message}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
      setStreamingCitations([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }

  const promptSuggestions = [
    'What are the key findings or takeaways from these documents?',
    'Summarize the financial highlights and revenue metrics.',
    'List any risks or constraints mentioned in the text.',
  ];

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
      {/* Conversation Thread Header */}
      <div className="px-5 py-3 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <span>{activeConversation ? activeConversation.title : 'Assistant Chat'}</span>
            </h3>
            <p className="text-[11px] text-slate-400">Verifiable RAG grounded in uploaded knowledge</p>
          </div>
        </div>

        {/* Thread switcher / New Chat */}
        <div className="flex items-center gap-2">
          {conversations.length > 1 && (
            <select
              value={activeConversation?.id || ''}
              onChange={(e) => {
                const found = conversations.find((c) => c.id === e.target.value);
                if (found) onSelectConversation(found);
              }}
              className="bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              {conversations.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={() => onCreateConversation()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-200 bg-indigo-600 hover:bg-indigo-500 rounded-lg transition shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {loadingMessages ? (
          <div className="flex items-center justify-center h-full text-slate-400 gap-2 text-sm">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
            <span>Loading conversation...</span>
          </div>
        ) : messages.length === 0 && !isStreaming ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4 py-8">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mb-3">
              <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-base font-semibold text-slate-200 mb-1">
              Ask questions grounded in your knowledge base
            </h4>
            <p className="text-xs text-slate-400 max-w-sm mb-6">
              DocMind retrieves exact vector chunks and strictly cites every page and document source.
            </p>

            {!hasDocuments && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-amber-300 bg-amber-950/40 border border-amber-800/50 rounded-lg mb-6">
                <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>Upload at least one document on the left to start asking questions.</span>
              </div>
            )}

            {/* Starter prompt chips */}
            {hasDocuments && (
              <div className="w-full max-w-md space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 text-left mb-1">
                  Suggested Questions
                </p>
                {promptSuggestions.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(prompt)}
                    className="w-full text-left text-xs p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-900 text-slate-300 hover:text-white transition"
                  >
                    "{prompt}"
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-2xl p-4 shadow-sm text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-none'
                      : 'bg-slate-950/70 border border-slate-800 text-slate-200 rounded-bl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Verifiable Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/80">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400 mb-1.5">
                        Verified Sources ({msg.citations.length})
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.citations.map((c, i) => (
                          <CitationCard key={i} citation={c} index={i} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {/* Real-time Streaming message */}
            {isStreaming && (
              <div className="flex gap-3 justify-start animate-in fade-in duration-150">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 animate-pulse" />
                </div>
                <div className="max-w-[85%] rounded-2xl rounded-bl-none p-4 bg-slate-950/70 border border-slate-800 text-slate-200 text-sm leading-relaxed shadow-sm">
                  <p className="whitespace-pre-wrap">
                    {streamingContent}
                    <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse" />
                  </p>

                  {streamingCitations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/80">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400 mb-1.5">
                        Verified Sources ({streamingCitations.length})
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {streamingCitations.map((c, i) => (
                          <CitationCard key={i} citation={c} index={i} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Composer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/60">
        <div className="relative flex items-end bg-slate-900 border border-slate-800 focus-within:border-indigo-500 rounded-xl p-2 transition shadow-inner">
          <textarea
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            rows={2}
            placeholder={
              hasDocuments
                ? 'Ask a question about your documents (Shift + Enter for new line)...'
                : 'Upload a document to ask questions...'
            }
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-400 resize-none px-2 py-1 focus:outline-none"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!inputQuestion.trim() || isStreaming}
            className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-30 disabled:cursor-not-allowed transition flex-shrink-0 ml-2"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
        <p className="text-[10px] text-slate-400 text-center mt-2">
          Grounded with pgvector semantic similarity. Answers refuse to fabricate unsupported facts.
        </p>
      </div>
    </div>
  );
};
