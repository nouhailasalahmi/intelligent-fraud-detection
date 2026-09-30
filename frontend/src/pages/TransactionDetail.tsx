import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { TransactionDetail as TransactionDetailType } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { CardSkeleton, Skeleton } from '../components/ui/Skeleton';
import { 
  ArrowLeft, 
  ShieldAlert, 
  ShieldCheck, 
  User, 
  CreditCard, 
  MapPin, 
  Cpu, 
  FileText, 
  Clock, 
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  History,
  Layers,
  Sparkles,
  Download
} from 'lucide-react';

export const TransactionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<TransactionDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!id) return;
    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.transactions.get(parseInt(id, 10));
        setDetail(data);
      } catch (err: any) {
        setError(err.message || 'Impossible de charger la transaction.');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-6 pb-12">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="p-8 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Transaction introuvable</h2>
        <p className="text-sm text-slate-400">{error || "La transaction demandée n'existe pas."}</p>
        <button
          onClick={() => navigate('/transactions')}
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sm font-semibold text-white transition"
        >
          Retour aux transactions
        </button>
      </div>
    );
  }

  const { transaction: tx, scoring_ml, dsp2, investigator_trace, decision_trace, audit_trail, action_log, sar_info } = detail;

  const fraudProbPct = Math.round((scoring_ml.fraud_probability || 0) * 100);
  const confidencePct = Math.round((decision_trace.confidence || 0) * 100);

  return (
    <div className="space-y-6 pb-16">
      {/* En-tête Navigation & Statuts */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-800 text-slate-400 hover:text-white transition"
            title="Retour"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-white">
                Transaction #{tx.id}
              </h1>
              {tx.transaction_uuid && (
                <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                  {tx.transaction_uuid}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Horodatage : {new Date(tx.transaction_timestamp).toLocaleString('fr-FR')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge type="decision" value={tx.llm_decision} size="md" />
          <StatusBadge type="action" value={tx.action_taken} size="md" />
          <StatusBadge type="dsp2" value={tx.dsp2_compliant} size="md" />
        </div>
      </div>

      {/* Cartes d'Identité & Montant */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Montant & Instrument */}
        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Montant du Paiement</span>
          <div className="mt-2 text-3xl font-extrabold text-white">
            {Number(tx.amount).toFixed(2)} €
          </div>
          <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Moyen de paiement :</span>
              <span className="font-semibold text-slate-200 capitalize">{tx.payment_method || 'Carte'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Carte (PCI-DSS) :</span>
              <span className="font-mono text-slate-200 font-semibold">{tx.card_id}</span>
            </div>
          </div>
        </div>

        {/* Porteur & Localisation */}
        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Porteur & Géographie</span>
          <div className="mt-2 text-sm font-semibold text-blue-400 font-mono truncate">
            {tx.customer_id}
          </div>
          <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Localisation :</span>
              <span className="font-semibold text-slate-200">{tx.city || 'N/A'}, {tx.country || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Terminal / Appareil :</span>
              <span className="font-semibold text-slate-200">{tx.device_type || 'Inconnu'}</span>
            </div>
          </div>
        </div>

        {/* Conformité DSP2 / SCA */}
        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Conformité DSP2 (RTS / SCA)</span>
          <div className="mt-2 flex items-center gap-2">
            {dsp2.is_compliant ? (
              <span className="text-base font-bold text-emerald-400 flex items-center gap-1.5">
                <ShieldCheck className="w-5 h-5" /> Authentification Conforme
              </span>
            ) : (
              <span className="text-base font-bold text-rose-400 flex items-center gap-1.5">
                <ShieldAlert className="w-5 h-5" /> Manquement DSP2 Détecté
              </span>
            )}
          </div>
          <p className="mt-3 text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
            {dsp2.reason}
          </p>
        </div>
      </div>

      {/* Section Scoring Machine Learning */}
      <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-400" />
          Scoring Machine Learning (XGBoost + Isolation Forest)
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {/* XGBoost Probability Gauge */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-slate-300 font-medium">Probabilité de Fraude (Modèle Supervisé XGBoost)</span>
              <span className={`font-bold font-mono ${fraudProbPct > 80 ? 'text-rose-400' : fraudProbPct > 50 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {fraudProbPct}% ({scoring_ml.fraud_probability?.toFixed(4)})
              </span>
            </div>
            <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  fraudProbPct > 80 ? 'bg-gradient-to-r from-amber-500 to-rose-500' : fraudProbPct > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${fraudProbPct}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Seuil d'alerte configuré : 0.50 • Prédit à partir du profil comportemental.
            </p>
          </div>

          {/* Isolation Forest Anomaly Score */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-slate-300 font-medium">Score d'Anomalie (Non-supervisé Isolation Forest)</span>
              <span className="font-bold font-mono text-indigo-400">
                {scoring_ml.iso_anomaly_score?.toFixed(4)}
              </span>
            </div>
            <div className="w-full bg-slate-950 h-3 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(10, ((scoring_ml.iso_anomaly_score || 0) + 1) * 50))}%` }}
              />
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Score négatif (&lt; 0.0) = divergence anormale par rapport à la distribution standard.
            </p>
          </div>
        </div>
      </div>

      {/* Section Parcours d'Enquête Multi-Agents LLM */}
      <div className="p-6 rounded-2xl border border-indigo-950/60 bg-gradient-to-b from-indigo-950/20 to-slate-900/60 backdrop-blur-sm space-y-6">
        <div className="flex items-center justify-between border-b border-indigo-900/40 pb-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-indigo-400" />
              Parcours d'Enquête Multi-Agents
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Coordination entre l'Agent Investigateur (faits & profils) et l'Agent Décideur (arbitre indépendant).
            </p>
          </div>
          {detail.multi_pass_triggered && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/60 font-medium">
              Deuxième passe d'approfondissement déclenchée (Confiance &lt; 0.60)
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Agent 1 : InvestigatorAgent */}
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/70 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
                <User className="w-4 h-4" /> Agent Investigateur (Factual Profile)
              </span>
              <span className="text-[11px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                {investigator_trace.steps_used} étape(s) d'investigation
              </span>
            </div>

            {/* Anomalies Détectées */}
            <div>
              <span className="text-xs font-semibold text-slate-300">Anomalies & Écarts Relevés :</span>
              {investigator_trace.anomalies && investigator_trace.anomalies.length > 0 ? (
                <ul className="mt-2 space-y-1.5">
                  {investigator_trace.anomalies.map((anom, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-xs text-rose-300 bg-rose-950/30 p-2 rounded-lg border border-rose-900/40">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" />
                      <span>{anom}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 text-xs text-emerald-400 bg-emerald-950/30 p-2 rounded-lg border border-emerald-900/40 flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Aucune anomalie critique relevée sur cette transaction.</span>
                </div>
              )}
            </div>

            {/* Facteurs de Risque / Facteurs Rassurants */}
            {investigator_trace.risk_factors && investigator_trace.risk_factors.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-300">Facteurs de Risque Identifiés :</span>
                <ul className="mt-1.5 space-y-1">
                  {investigator_trace.risk_factors.map((rf, idx) => (
                    <li key={idx} className="text-xs text-slate-300 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                      <span>{rf}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Agent 2 : DecisionAgent */}
          <div className="p-5 rounded-xl border border-slate-800 bg-slate-950/70 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" /> Agent Décideur (Juge Impartial)
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Score de Confiance :</span>
                <span className="font-bold font-mono text-white text-sm bg-indigo-950 px-2 py-0.5 rounded border border-indigo-800">
                  {confidencePct}%
                </span>
              </div>
            </div>

            {/* Verdict */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400 font-medium">Verdict Arbitré :</span>
              <StatusBadge type="decision" value={decision_trace.verdict} size="md" />
            </div>

            {/* Justification Rédigée */}
            <div>
              <span className="text-xs font-semibold text-slate-300">Motivation & Justification du Verdict :</span>
              <div className="mt-2 text-xs text-slate-200 leading-relaxed bg-slate-900/90 p-3.5 rounded-xl border border-slate-800 italic">
                "{decision_trace.justification || tx.llm_justification}"
              </div>
            </div>

            {/* Action Déterminée */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
              <span className="text-slate-400">Action Automatisée Recommandée :</span>
              <StatusBadge type="action" value={decision_trace.recommended_action || tx.action_taken} />
            </div>
          </div>
        </div>
      </div>

      {/* Action Log & Rapport SAR */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Action Log */}
        <div className="lg:col-span-2 p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-4">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-400" />
            Journalisation des Actions Automatisées (action_log)
          </h2>

          <div className="space-y-2.5">
            {action_log && action_log.length > 0 ? (
              action_log.map((act) => (
                <div key={act.id} className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2.5">
                    <StatusBadge type="action" value={act.action} />
                    <span className="text-slate-300 font-mono">Statut : {act.status}</span>
                  </div>
                  <span className="text-slate-400 font-mono">
                    {act.executed_at ? new Date(act.executed_at).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 py-3">Aucune action n'a encore été enregistrée dans action_log.</p>
            )}
          </div>
        </div>

        {/* Carte Rapport SAR */}
        <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" />
              Déclaration de Soupçon (SAR)
            </h2>
            <p className="text-xs text-slate-400 mt-1">Conformité Tracfin / ACPR</p>
          </div>

          <div className="my-4">
            {tx.sar_generated ? (
              <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-800/50 space-y-2">
                <div className="flex items-center gap-2 text-amber-300 text-xs font-semibold">
                  <CheckCircle2 className="w-4 h-4" /> Rapport SAR Généré
                </div>
                <p className="text-[11px] text-slate-400 font-mono truncate">
                  Fichier : {tx.sar_path || `reports/SAR-${tx.id}.md`}
                </p>
                <button
                  onClick={() => navigate('/reports')}
                  className="w-full mt-2 py-2 px-3 rounded-lg bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-600/40 font-semibold text-xs transition flex items-center justify-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" /> Consulter le Rapport SAR
                </button>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-500 text-center">
                Aucun rapport SAR requis ou généré pour cette transaction.
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-500 font-mono text-center">
            Norme ISO 20022 • Tracfin Compliance
          </div>
        </div>
      </div>

      {/* Piste d'Audit Complète (Audit Trail) */}
      <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm space-y-4">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
          <History className="w-4 h-4 text-blue-400" />
          Piste d'Audit Réglementaire ({audit_trail.length} événements enregistrés)
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Date / Heure</th>
                <th className="py-2.5 px-3">Étape (Stage)</th>
                <th className="py-2.5 px-3">Acteur</th>
                <th className="py-2.5 px-3">Action Exécutée</th>
                <th className="py-2.5 px-3">Détails Techniques</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {audit_trail.map((ev) => (
                <tr key={ev.id} className="hover:bg-slate-800/30 transition">
                  <td className="py-2.5 px-3 text-slate-400">
                    {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : 'N/A'}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-indigo-300">{ev.stage}</td>
                  <td className="py-2.5 px-3 text-slate-200">{ev.actor}</td>
                  <td className="py-2.5 px-3 text-slate-300">{ev.action}</td>
                  <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate">
                    {JSON.stringify(ev.details || {})}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
