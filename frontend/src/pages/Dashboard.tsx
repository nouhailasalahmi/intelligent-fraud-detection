import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { DashboardStats } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { CardSkeleton, Skeleton } from '../components/ui/Skeleton';
import { useNavigate } from 'react-router-dom';
import { 
  ShieldAlert, 
  CreditCard, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  ArrowUpRight, 
  RefreshCw, 
  Activity,
  Layers
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  BarChart, 
  Bar 
} from 'recharts';

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const navigate = useNavigate();

  const fetchStats = async () => {
    try {
      const data = await api.dashboard.getStats();
      setStats(data);
    } catch (err) {
      console.error('Erreur chargement dashboard:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchStats();
  };

  const ACTION_COLORS: Record<string, string> = {
    BLOCK_CARD: '#ef4444',
    NOTIFY_CUSTOMER: '#f59e0b',
    FLAG_FOR_REVIEW: '#8b5cf6',
    ALLOW: '#10b981',
  };

  const actionPieData = stats
    ? Object.entries(stats.action_breakdown).map(([name, value]) => ({
        name,
        value,
        color: ACTION_COLORS[name] || '#64748b',
      }))
    : [];

  const decisionBarData = stats
    ? Object.entries(stats.decision_breakdown).map(([name, count]) => ({
        decision: name.toUpperCase(),
        count,
      }))
    : [];

  return (
    <div className="space-y-6 pb-12">
      {/* En-tête */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <Activity className="w-6 h-6 text-blue-400" />
            Tableau de Bord de Surveillance & KPIs
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Supervision en direct du pipeline Kafka, des scoring XGBoost et de l'arbitrage multi-agents.
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition disabled:opacity-50 self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span>Actualiser</span>
        </button>
      </div>

      {/* Grille des KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : (
        stats && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* KPI 1 : Volume Total */}
            <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Transactions Totales</span>
                <div className="p-2 rounded-xl bg-blue-600/15 text-blue-400 border border-blue-500/20">
                  <CreditCard className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-white">{stats.total_transactions.toLocaleString()}</span>
                <span className="text-xs text-slate-400 font-mono">({stats.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} DH)</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">Traitées par le pipeline Kafka</p>
            </div>

            {/* KPI 2 : Taux de Fraude */}
            <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Taux de Fraude</span>
                <div className="p-2 rounded-xl bg-rose-600/15 text-rose-400 border border-rose-500/20">
                  <ShieldAlert className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-rose-400">{stats.fraud_rate_pct}%</span>
                <span className="text-xs text-slate-400">({stats.fraud_count} fraudes confirmées)</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">Décision Multi-Agents ou BLOCK_CARD</p>
            </div>

            {/* KPI 3 : Alertes en Attente */}
            <div 
              onClick={() => navigate('/alerts')}
              className="p-5 rounded-2xl border border-amber-900/40 bg-amber-950/20 hover:bg-amber-950/30 backdrop-blur-sm relative overflow-hidden cursor-pointer transition group"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">File d'Alertes L2</span>
                <div className="p-2 rounded-xl bg-amber-600/20 text-amber-400 border border-amber-500/30 group-hover:scale-105 transition">
                  <AlertTriangle className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-amber-300">{stats.pending_alerts_count}</span>
                <span className="text-xs text-amber-400/80 font-medium flex items-center gap-0.5">
                  Voir <ArrowUpRight className="w-3.5 h-3.5" />
                </span>
              </div>
              <p className="text-[11px] text-amber-300/70 mt-1">FLAG_FOR_REVIEW nécessitant arbitrage</p>
            </div>

            {/* KPI 4 : Conformité DSP2 */}
            <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Conformité DSP2 (SCA)</span>
                <div className="p-2 rounded-xl bg-emerald-600/15 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-emerald-400">{stats.dsp2_compliance_rate_pct}%</span>
                <span className="text-xs text-slate-400">conf. réglementaire</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">Authentification forte / Exemptions RTS</p>
            </div>
          </div>
        )
      )}

      {/* Grille des Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Graphique 1 : Évolution Temporelle */}
        <div className="lg:col-span-2 p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                Évolution des Volumes & Détections de Fraude
              </h2>
              <p className="text-xs text-slate-400">Transactions totales vs. transactions frauduleuses détectées</p>
            </div>
          </div>

          <div className="h-64 w-full">
            {loading ? (
              <Skeleton className="w-full h-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats?.timeline || []}>
                  <defs>
                    <linearGradient id="totalColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="fraudColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '0.75rem',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="total_transactions"
                    name="Transactions"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#totalColor)"
                  />
                  <Area
                    type="monotone"
                    dataKey="fraud_count"
                    name="Fraudes"
                    stroke="#ef4444"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#fraudColor)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Graphique 2 : Répartition des Actions */}
        <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              Répartition des Actions Automatisées
            </h2>
            <p className="text-xs text-slate-400">Exécution de la matrice décisionnelle</p>
          </div>

          <div className="h-52 w-full my-auto flex items-center justify-center">
            {loading ? (
              <Skeleton className="w-40 h-40 rounded-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={actionPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {actionPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      borderRadius: '0.75rem',
                      fontSize: '12px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs pt-3 border-t border-slate-800">
            {actionPieData.map((item) => (
              <div key={item.name} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-slate-300 truncate">{item.name}</span>
                <span className="font-semibold text-white ml-auto">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Flux d'Activité Récente Suspecte */}
      <div className="p-5 rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              Flux des Dernières Transactions à Risque
            </h2>
            <p className="text-xs text-slate-400">Derniers événements ayant déclenché une alerte ou un blocage</p>
          </div>

          <button
            onClick={() => navigate('/transactions')}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            <span>Toutes les transactions</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Date / Réf</th>
                <th className="py-2.5 px-3">Porteur RGPD</th>
                <th className="py-2.5 px-3">Montant</th>
                <th className="py-2.5 px-3">Localisation</th>
                <th className="py-2.5 px-3">Score ML</th>
                <th className="py-2.5 px-3">Décision IA</th>
                <th className="py-2.5 px-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {stats?.recent_suspicious && stats.recent_suspicious.length > 0 ? (
                stats.recent_suspicious.map((tx: any) => (
                  <tr
                    key={tx.id}
                    onClick={() => navigate(`/transactions/${tx.id}`)}
                    className="hover:bg-slate-800/40 cursor-pointer transition"
                  >
                    <td className="py-2.5 px-3 font-mono text-slate-300">
                      {tx.transaction_timestamp ? new Date(tx.transaction_timestamp).toLocaleTimeString() : 'N/A'}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-400">{tx.customer_id}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{Number(tx.amount).toFixed(2)} DH</td>
                    <td className="py-2.5 px-3 text-slate-300">{tx.city}, {tx.country}</td>
                    <td className="py-2.5 px-3">
                      <span className="font-mono text-rose-400 font-semibold">
                        {(Number(tx.fraud_probability || 0) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge type="decision" value={tx.llm_decision} />
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge type="action" value={tx.action_taken} />
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    Aucune transaction suspecte récente enregistrée.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};