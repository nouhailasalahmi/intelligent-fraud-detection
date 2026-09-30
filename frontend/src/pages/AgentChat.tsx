import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import { ChatMessage } from '../types';
import { 
  Bot, 
  User, 
  Send, 
  Terminal, 
  Copy, 
  Check, 
  Sparkles, 
  Clock, 
  Database, 
  ShieldCheck, 
  CornerDownLeft,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export const AgentChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => {
    return localStorage.getItem('fraud_chat_session') || `sess-${Date.now()}`;
  });
  const [expandedSqlIdx, setExpandedSqlIdx] = useState<Record<number, boolean>>({});
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const starterQueries = [
    "Quelles sont les 5 dernières transactions frauduleuses ?",
    "Quel est le montant moyen des fraudes comparé aux transactions légitimes ?",
    "Combien d'alertes sont actuellement en attente d'arbitrage ?",
    "Liste les cartes bancaires actuellement bloquées",
    "Donne-moi les transactions non conformes à la DSP2",
  ];

  // Chargement de l'historique existant pour cette session
  useEffect(() => {
    localStorage.setItem('fraud_chat_session', sessionId);
    const loadHistory = async () => {
      try {
        const hist = await api.agent.getHistory(sessionId);
        if (hist && hist.length > 0) {
          const formatted: ChatMessage[] = hist.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            sql_query: m.sql_query,
            data: m.sql_result,
            execution_time_ms: m.execution_time_ms,
            created_at: m.created_at,
          }));
          setMessages(formatted);
        } else {
          // Message d'accueil initial
          setMessages([
            {
              role: 'assistant',
              content: "Bonjour. Je suis votre Agent Analyste IA connecté à la base de détection de fraudes. Posez-moi vos questions en français sur les transactions, les alertes, les cartes bloquées ou les pistes d'audit : je traduis vos demandes en requêtes SQL sécurisées en lecture seule et vous présente les résultats vérifiés.",
            }
          ]);
        }
      } catch {
        setMessages([
          {
            role: 'assistant',
            content: "Bonjour. Je suis votre Agent Analyste IA connecté à la base de détection de fraudes. Posez-moi vos questions en langage naturel.",
          }
        ]);
      }
    };
    loadHistory();
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInput('');
    setLoading(true);

    try {
      const res = await api.agent.chat(textToSend, sessionId);
      const botMsg: ChatMessage = {
        role: 'assistant',
        content: res.response,
        sql_query: res.sql_query,
        columns: res.columns,
        data: res.data,
        row_count: res.row_count,
        execution_time_ms: res.execution_time_ms,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ ${err.message || 'Impossible d\'exécuter la requête demandée.'}`,
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleCopySql = (sql: string, idx: number) => {
    navigator.clipboard.writeText(sql);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const toggleSql = (idx: number) => {
    setExpandedSqlIdx((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6.5rem)] max-h-[850px] space-y-4">
      {/* En-tête */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            Agent IA Text-to-SQL (Enquête Conversationnelle)
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Traduction sécurisée du langage naturel en requêtes PostgreSQL en lecture seule (Transactions, Action Log, Audit).
          </p>
        </div>

        <button
          onClick={() => {
            const newSess = `sess-${Date.now()}`;
            setSessionId(newSess);
            setMessages([
              {
                role: 'assistant',
                content: "Nouvelle session démarrée. Quelle analyse souhaitez-vous mener ?",
              }
            ]);
          }}
          className="text-xs px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 transition"
        >
          Nouvelle conversation
        </button>
      </div>

      {/* Zone de Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, idx) => {
          const isUser = msg.role === 'user';
          const isSqlOpen = expandedSqlIdx[idx] ?? true;

          return (
            <div
              key={idx}
              className={`flex gap-3 max-w-4xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-xs font-semibold ${
                  isUser
                    ? 'bg-blue-600 text-white'
                    : 'bg-indigo-950/80 border border-indigo-700/60 text-indigo-300'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Contenu Message */}
              <div className="space-y-3 min-w-0 max-w-full">
                <div
                  className={`p-4 rounded-2xl text-xs leading-relaxed ${
                    isUser
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-none shadow-md'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>

                {/* Bloc Requête SQL Générée (pour messages de l'assistant) */}
                {msg.sql_query && (
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/90 overflow-hidden shadow-lg">
                    <div 
                      onClick={() => toggleSql(idx)}
                      className="flex items-center justify-between px-3.5 py-2 bg-slate-900/70 border-b border-slate-800 cursor-pointer hover:bg-slate-850 transition"
                    >
                      <div className="flex items-center gap-2 text-xs font-mono text-indigo-300 font-semibold">
                        <Terminal className="w-3.5 h-3.5" />
                        <span>Requête SQL générée (PostgreSQL READ ONLY)</span>
                      </div>

                      <div className="flex items-center gap-2">
                        {msg.execution_time_ms !== undefined && (
                          <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {msg.execution_time_ms} ms
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCopySql(msg.sql_query!, idx);
                          }}
                          className="p-1 text-slate-400 hover:text-white rounded transition"
                          title="Copier le code SQL"
                        >
                          {copiedIdx === idx ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                        {isSqlOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
                      </div>
                    </div>

                    {isSqlOpen && (
                      <div className="p-3 text-[11px] font-mono text-emerald-300 bg-slate-950 overflow-x-auto selection:bg-indigo-600">
                        <code>{msg.sql_query}</code>
                      </div>
                    )}

                    {/* Tableau des résultats SQL */}
                    {msg.data && msg.data.length > 0 && (
                      <div className="border-t border-slate-800 overflow-x-auto max-h-60">
                        <table className="w-full text-left text-[11px] font-mono">
                          <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider sticky top-0">
                            <tr>
                              {Object.keys(msg.data[0]).map((col) => (
                                <th key={col} className="py-1.5 px-3 border-b border-slate-800">{col}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-850">
                            {msg.data.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-slate-900/40">
                                {Object.values(row).map((val: any, cIdx) => (
                                  <td key={cIdx} className="py-1.5 px-3 text-slate-300 whitespace-nowrap">
                                    {val === null || val === undefined ? 'NULL' : typeof val === 'object' ? JSON.stringify(val) : String(val)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3 max-w-md mr-auto">
            <div className="w-8 h-8 rounded-xl bg-indigo-950/80 border border-indigo-700/60 text-indigo-300 flex items-center justify-center">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="p-3.5 rounded-2xl bg-slate-900/90 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:0.4s]" />
              </div>
              <span>Génération de la requête SQL et exécution sécurisée...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Questions suggérées en chips */}
      <div className="pt-2 border-t border-slate-800/80 flex-shrink-0 space-y-2">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {starterQueries.map((q, idx) => (
            <button
              key={idx}
              disabled={loading}
              onClick={() => handleSend(q)}
              className="text-[11px] px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900 hover:bg-slate-800 hover:border-slate-700 text-slate-300 whitespace-nowrap transition disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Input d'envoi */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="relative flex items-center"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez une question sur les fraudes, transactions, cartes ou conformité DSP2..."
            disabled={loading}
            className="w-full pl-4 pr-12 py-3 rounded-2xl border border-slate-700 bg-slate-900/80 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition shadow-inner"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-2 p-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition disabled:opacity-40"
            title="Envoyer la question"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
