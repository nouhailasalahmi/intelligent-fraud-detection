import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { AlertItem } from '../types';
import { useAlerts } from '../context/AlertsContext';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TableSkeleton } from '../components/ui/Skeleton';
import { useNavigate } from 'react-router-dom';
import { 
  AlertTriangle, 
  Wifi, 
  WifiOff, 
  CheckCircle2, 
  ShieldAlert, 
  Check, 
  X, 
  Eye, 
  Clock, 
  UserCheck, 
  FileText,
  AlertCircle
} from 'lucide-react';

export const Alerts: React.FC = () => {
  const { alerts, isConnected, resolveAlert, refreshAlerts } = useAlerts();
  const [tab, setTab] = useState<'PENDING' | 'RESOLVED'>('PENDING');
  const [resolvedList, setResolvedList] = useState<AlertItem[]>([]);
  const [loadingResolved, setLoadingResolved] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [reviewAction, setReviewAction] = useState<'CONFIRM_FRAUD' | 'FALSE_POSITIVE' | 'RESOLVED'>('CONFIRM_FRAUD');
  const [reviewNotes, setReviewNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (tab === 'RESOLVED') {
      const loadResolved = async () => {
        setLoadingResolved(true);
        try {
          const res = await api.alerts.list('RESOLVED');
          setResolvedList(res);
        } catch (err) {
          console.error(err);
        } finally {
          setLoadingResolved(false);
        }
      };
      loadResolved();
    }
  }, [tab]);

  const handleOpenReviewModal = (alert: AlertItem) => {
    setSelectedAlert(alert);
    setReviewAction('CONFIRM_FRAUD');
    setReviewNotes('');
  };

  const handleCloseReviewModal = () => {
    setSelectedAlert(null);
    setReviewNotes('');
  };

  const handleSubmitReview = async () => {
    if (!selectedAlert) return;
    setSubmitting(true);
    try {
      let newStatus = 'RESOLVED';
      if (reviewAction === 'CONFIRM_FRAUD') newStatus = 'BLOCKED';
      if (reviewAction === 'FALSE_POSITIVE') newStatus = 'FALSE_POSITIVE';

      await resolveAlert(selectedAlert.id, {
        status: newStatus,
        analyst_decision: reviewAction,
        notes: reviewNotes || `Arbitrage effectué : ${reviewAction}`,
      });

      handleCloseReviewModal();
      refreshAlerts();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const currentList = tab === 'PENDING' ? alerts : resolvedList;

  return (
    <div className="space-y-6 pb-12">
      {/* En-tête avec Statut Temps Réel */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            File d'Arbitrage des Alertes Fraude (Desk L2)
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Transactions incertaines ou de score de confiance intermédiaire (&lt; 0.60) nécessitant validation humaine.
          </p>
        </div>

        {/* Indicateur WebSocket Live */}
        <div
          className={`flex items-center gap-2.5 px-3 py-1.5 rounded-xl border text-xs font-mono self-start md:self-auto ${
            isConnected
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 shadow-sm shadow-emerald-950'
              : 'bg-rose-950/40 text-rose-300 border-rose-800/60'
          }`}
        >
          {isConnected ? (
            <>
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span>TEMPS RÉEL ACTIF • ÉCOUTE KAFKA</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-rose-400" />
              <span>DÉCONNECTÉ • RECONNEXION...</span>
            </>
          )}
        </div>
      </div>

      {/* Onglets de filtrage */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
        <button
          onClick={() => setTab('PENDING')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            tab === 'PENDING'
              ? 'bg-amber-600/20 text-amber-400 border border-amber-500/40'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>En attente d'arbitrage</span>
          <span className="px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold">
            {alerts.length}
          </span>
        </button>

        <button
          onClick={() => setTab('RESOLVED')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            tab === 'RESOLVED'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>Alertes Traitées</span>
        </button>
      </div>

      {/* Liste des Alertes */}
      <div className="space-y-3">
        {tab === 'RESOLVED' && loadingResolved ? (
          <TableSkeleton rows={4} cols={5} />
        ) : currentList.length > 0 ? (
          currentList.map((alert) => (
            <div
              key={alert.id}
              className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm hover:border-slate-700 transition space-y-3"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span className="text-base font-bold text-white">
                    {Number(alert.amount).toFixed(2)} €
                  </span>
                  <span className="text-xs font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    Client : {alert.customer_id}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    Carte : {alert.card_id}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <StatusBadge type="review" value={alert.review_status} />
                  <span className="text-xs text-slate-400 font-mono">
                    {alert.transaction_timestamp
                      ? new Date(alert.transaction_timestamp).toLocaleString('fr-FR')
                      : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Justification & Motif */}
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-slate-300 leading-relaxed">
                <span className="font-semibold text-amber-400">Motivation Multi-Agents : </span>
                {alert.llm_justification || 'Transaction mise en attente de vérification par le superviseur.'}
              </div>

              {/* Barre d'Actions de la Carte */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                <div className="flex items-center gap-4 text-slate-400">
                  <span>Ville : <strong className="text-slate-200">{alert.city || 'Inconnue'}</strong></span>
                  <span>Pays : <strong className="text-slate-200">{alert.country || 'Inconnu'}</strong></span>
                  <span>Score ML : <strong className="text-rose-400">{((alert.fraud_probability || 0) * 100).toFixed(0)}%</strong></span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/transactions/${alert.id}`)}
                    className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium transition flex items-center gap-1.5"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Détail complet</span>
                  </button>

                  {tab === 'PENDING' && (
                    <button
                      onClick={() => handleOpenReviewModal(alert)}
                      className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold transition flex items-center gap-1.5 shadow-md shadow-amber-600/20"
                    >
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>Traiter l'alerte</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Notes si déjà traitée */}
              {alert.reviewed_by && (
                <div className="pt-2 text-[11px] text-slate-400 border-t border-slate-800 flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>
                    Arbitré par <strong>{alert.reviewed_by}</strong> le {alert.reviewed_at ? new Date(alert.reviewed_at).toLocaleString() : ''}
                    {alert.review_notes && ` — "${alert.review_notes}"`}
                  </span>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="p-12 text-center rounded-2xl border border-slate-800 bg-slate-900/40 space-y-3">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto opacity-70" />
            <h3 className="text-sm font-bold text-white">File d'attente vide</h3>
            <p className="text-xs text-slate-400">
              Toutes les alertes FLAG_FOR_REVIEW ont été arbitrées ou aucune nouvelle anomalie n'a été reçue.
            </p>
          </div>
        )}
      </div>

      {/* Modal d'Arbitrage de l'Alerte */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg p-6 rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-white font-bold text-base">
                <UserCheck className="w-5 h-5 text-amber-400" />
                <span>Arbitrage de l'Alerte #{selectedAlert.id}</span>
              </div>
              <button
                onClick={handleCloseReviewModal}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1 text-xs">
              <div className="flex justify-between text-slate-300">
                <span>Montant :</span>
                <span className="font-bold text-white">{Number(selectedAlert.amount).toFixed(2)} €</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Client (RGPD) :</span>
                <span className="font-mono">{selectedAlert.customer_id}</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Carte (PCI-DSS) :</span>
                <span className="font-mono">{selectedAlert.card_id}</span>
              </div>
            </div>

            {/* Choix de Décision Analyste */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                Décision de l'analyste :
              </label>

              <div className="grid grid-cols-1 gap-2">
                <label className={`p-3 rounded-xl border flex items-center gap-3 cursor-pointer transition ${
                  reviewAction === 'CONFIRM_FRAUD'
                    ? 'border-red-600 bg-red-950/40 text-red-200'
                    : 'border-slate-800 bg-slate-950/60 text-slate-300 hover:bg-slate-800/40'
                }`}>
                  <input
                    type="radio"
                    name="action"
                    checked={reviewAction === 'CONFIRM_FRAUD'}
                    onChange={() => setReviewAction('CONFIRM_FRAUD')}
                    className="hidden"
                  />
                  <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <div className="text-xs">
                    <p className="font-bold">Confirmer la Fraude (BLOCK_CARD + Rapport SAR)</p>
                    <p className="text-[11px] text-slate-400">Bloque la carte et journalise un rapport officiel Tracfin.</p>
                  </div>
                </label>

                <label className={`p-3 rounded-xl border flex items-center gap-3 cursor-pointer transition ${
                  reviewAction === 'FALSE_POSITIVE'
                    ? 'border-emerald-600 bg-emerald-950/40 text-emerald-200'
                    : 'border-slate-800 bg-slate-950/60 text-slate-300 hover:bg-slate-800/40'
                }`}>
                  <input
                    type="radio"
                    name="action"
                    checked={reviewAction === 'FALSE_POSITIVE'}
                    onChange={() => setReviewAction('FALSE_POSITIVE')}
                    className="hidden"
                  />
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <div className="text-xs">
                    <p className="font-bold">Faux Positif (Autoriser la Transaction)</p>
                    <p className="text-[11px] text-slate-400">Transaction confirmée légitime après vérification porteur.</p>
                  </div>
                </label>

                <label className={`p-3 rounded-xl border flex items-center gap-3 cursor-pointer transition ${
                  reviewAction === 'RESOLVED'
                    ? 'border-blue-600 bg-blue-950/40 text-blue-200'
                    : 'border-slate-800 bg-slate-950/60 text-slate-300 hover:bg-slate-800/40'
                }`}>
                  <input
                    type="radio"
                    name="action"
                    checked={reviewAction === 'RESOLVED'}
                    onChange={() => setReviewAction('RESOLVED')}
                    className="hidden"
                  />
                  <Check className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <div className="text-xs">
                    <p className="font-bold">Clôturer avec Annotation</p>
                    <p className="text-[11px] text-slate-400">Archiver l'alerte sans bloquer la carte.</p>
                  </div>
                </label>
              </div>
            </div>

            {/* Notes d'arbitrage */}
            <div>
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block mb-1">
                Commentaires & Justification Analyste :
              </label>
              <textarea
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Ex: Contact téléphonique effectué avec le client, achat validé..."
                rows={3}
                className="w-full p-2.5 rounded-xl border border-slate-700 bg-slate-950 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            {/* Boutons d'action */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={handleCloseReviewModal}
                className="px-4 py-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-xs font-semibold text-slate-300 transition"
              >
                Annuler
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmitReview}
                className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition disabled:opacity-50"
              >
                {submitting ? 'Validation...' : 'Valider l\'arbitrage'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
