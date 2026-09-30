import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { TransactionSummary, PaginatedResponse } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TableSkeleton } from '../components/ui/Skeleton';
import { 
  CreditCard, 
  Search, 
  Filter, 
  ChevronLeft, 
  ChevronRight, 
  ArrowUpDown, 
  Download,
  Calendar,
  X
} from 'lucide-react';

export const Transactions: React.FC = () => {
  const [data, setData] = useState<PaginatedResponse<TransactionSummary> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('');
  const [minAmount, setMinAmount] = useState<string>('');
  const [maxAmount, setMaxAmount] = useState<string>('');
  const [sortBy, setSortBy] = useState('transaction_timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const navigate = useNavigate();

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const res = await api.transactions.list({
        page,
        limit: 15,
        search: search || undefined,
        status: statusFilter || undefined,
        verdict: verdictFilter || undefined,
        min_amount: minAmount ? parseFloat(minAmount) : undefined,
        max_amount: maxAmount ? parseFloat(maxAmount) : undefined,
        sort_by: sortBy,
        order: sortOrder,
      });
      setData(res);
    } catch (err) {
      console.error('Erreur chargement transactions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [page, statusFilter, verdictFilter, sortBy, sortOrder]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTransactions();
  };

  const handleResetFilters = () => {
    setSearch('');
    setStatusFilter('');
    setVerdictFilter('');
    setMinAmount('');
    setMaxAmount('');
    setPage(1);
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* En-tête */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <CreditCard className="w-6 h-6 text-blue-400" />
            Explorateur des Transactions Bancaires
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Données pseudonymisées RGPD (Hash SHA-256) et cartes masquées selon les règles PCI-DSS.
          </p>
        </div>
      </div>

      {/* Barre de Filtres */}
      <div className="p-4 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col lg:flex-row gap-3">
          {/* Recherche textuelle */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Recherche par UUID, Ville, Pays..."
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Filtre Action */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">Toutes les Actions</option>
            <option value="BLOCK_CARD">BLOCK_CARD (Blocage)</option>
            <option value="NOTIFY_CUSTOMER">NOTIFY_CUSTOMER (Notification)</option>
            <option value="FLAG_FOR_REVIEW">FLAG_FOR_REVIEW (En attente)</option>
            <option value="ALLOW">ALLOW (Autorisée)</option>
          </select>

          {/* Filtre Décision */}
          <select
            value={verdictFilter}
            onChange={(e) => {
              setVerdictFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
          >
            <option value="">Tous les Verdicts</option>
            <option value="fraude">Fraude</option>
            <option value="incertain">Incertain</option>
            <option value="legitime">Légitime</option>
          </select>

          {/* Montant Min/Max */}
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={minAmount}
              onChange={(e) => setMinAmount(e.target.value)}
              placeholder="Min DH"
              className="w-24 px-3 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <span className="text-slate-500">-</span>
            <input
              type="number"
              value={maxAmount}
              onChange={(e) => setMaxAmount(e.target.value)}
              placeholder="Max DH"
              className="w-24 px-3 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition"
            >
              Filtrer
            </button>
            <button
              type="button"
              onClick={handleResetFilters}
              className="p-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Réinitialiser les filtres"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>

      {/* Tableau des Transactions */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm overflow-hidden">
        {loading ? (
          <TableSkeleton rows={8} cols={7} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th 
                    className="py-3 px-4 cursor-pointer hover:text-white transition"
                    onClick={() => toggleSort('transaction_timestamp')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Date / Heure</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-500" />
                    </div>
                  </th>
                  <th className="py-3 px-4">Porteur (RGPD)</th>
                  <th className="py-3 px-4">Instrument (PCI-DSS)</th>
                  <th 
                    className="py-3 px-4 cursor-pointer hover:text-white transition"
                    onClick={() => toggleSort('amount')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Montant</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-500" />
                    </div>
                  </th>
                  <th className="py-3 px-4">Localisation</th>
                  <th 
                    className="py-3 px-4 cursor-pointer hover:text-white transition"
                    onClick={() => toggleSort('fraud_probability')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Score ML</span>
                      <ArrowUpDown className="w-3 h-3 text-slate-500" />
                    </div>
                  </th>
                  <th className="py-3 px-4">DSP2</th>
                  <th className="py-3 px-4">Décision IA</th>
                  <th className="py-3 px-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data && data.items.length > 0 ? (
                  data.items.map((tx) => (
                    <tr
                      key={tx.id}
                      onClick={() => navigate(`/transactions/${tx.id}`)}
                      className="hover:bg-slate-800/40 cursor-pointer transition group"
                    >
                      <td className="py-3 px-4 font-mono text-slate-300">
                        {tx.transaction_timestamp
                          ? new Date(tx.transaction_timestamp).toLocaleString('fr-FR', {
                              dateStyle: 'short',
                              timeStyle: 'medium',
                            })
                          : 'N/A'}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-400 group-hover:text-blue-400 transition">
                        {tx.customer_id}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-400">
                        {tx.card_id}
                      </td>
                      <td className="py-3 px-4 font-semibold text-white">
                        {Number(tx.amount).toFixed(2)} DH
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        {tx.city || 'N/A'}, {tx.country || 'N/A'}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        <span
                          className={`font-semibold ${
                            (tx.fraud_probability || 0) > 0.8
                              ? 'text-rose-400'
                              : (tx.fraud_probability || 0) > 0.5
                              ? 'text-amber-400'
                              : 'text-emerald-400'
                          }`}
                        >
                          {((tx.fraud_probability || 0) * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge type="dsp2" value={tx.dsp2_compliant} />
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge type="decision" value={tx.llm_decision} />
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge type="action" value={tx.action_taken} />
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={9} className="py-12 text-center text-slate-500">
                      Aucune transaction ne correspond aux critères de recherche.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {data && data.total > 0 && (
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>
              Affichage de {((page - 1) * 15) + 1} à {Math.min(page * 15, data.total)} sur {data.total} transactions
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-40 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-semibold text-slate-200">
                Page {page} sur {data.pages || 1}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
                className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-40 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};