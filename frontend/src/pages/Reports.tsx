import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { SARReportSummary, AuditEvent, PaginatedResponse } from '../types';
import { TableSkeleton } from '../components/ui/Skeleton';
import { 
  FileText, 
  History, 
  Download, 
  Eye, 
  Search, 
  ChevronLeft, 
  ChevronRight, 
  ShieldCheck, 
  X,
  Copy,
  Check
} from 'lucide-react';

export const Reports: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'SAR' | 'AUDIT'>('SAR');

  // État Rapports SAR
  const [sarReports, setSarReports] = useState<SARReportSummary[]>([]);
  const [loadingSar, setLoadingSar] = useState(true);
  const [sarSearch, setSarSearch] = useState('');
  const [previewContent, setPreviewContent] = useState<{ reference: string; markdown: string; json: any } | null>(null);
  const [copied, setCopied] = useState(false);

  // État Piste d'Audit
  const [auditData, setAuditData] = useState<PaginatedResponse<AuditEvent> | null>(null);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditPage, setAuditPage] = useState(1);
  const [stageFilter, setStageFilter] = useState('');
  const [selectedAuditJson, setSelectedAuditJson] = useState<any | null>(null);

  // Chargement des rapports SAR
  useEffect(() => {
    const fetchSAR = async () => {
      setLoadingSar(true);
      try {
        const data = await api.reports.listSAR();
        setSarReports(data);
      } catch (err) {
        console.error('Erreur chargement SAR:', err);
      } finally {
        setLoadingSar(false);
      }
    };
    fetchSAR();
  }, []);

  // Chargement de la piste d'audit
  useEffect(() => {
    if (activeTab === 'AUDIT') {
      const fetchAudit = async () => {
        setLoadingAudit(true);
        try {
          const res = await api.reports.getAuditTrail({
            page: auditPage,
            limit: 20,
            stage: stageFilter || undefined,
          });
          setAuditData(res);
        } catch (err) {
          console.error('Erreur chargement audit:', err);
        } finally {
          setLoadingAudit(false);
        }
      };
      fetchAudit();
    }
  }, [activeTab, auditPage, stageFilter]);

  const handlePreviewSAR = async (ref: string) => {
    try {
      const content = await api.reports.getSARContent(ref);
      setPreviewContent({
        reference: ref,
        markdown: content.markdown_content,
        json: content.json_data,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleCopyMarkdown = () => {
    if (previewContent?.markdown) {
      navigator.clipboard.writeText(previewContent.markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const filteredSar = sarReports.filter((r) => 
    r.reference.toLowerCase().includes(sarSearch.toLowerCase()) ||
    (r.decision && r.decision.toLowerCase().includes(sarSearch.toLowerCase()))
  );

  return (
    <div className="space-y-6 pb-12">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
          <FileText className="w-6 h-6 text-blue-400" />
          Rapports Réglementaires SAR & Piste d'Audit
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Déclarations de soupçon (Suspicious Activity Reports) conformes Tracfin/ACPR et traçabilité inviolable.
        </p>
      </div>

      {/* Onglets */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('SAR')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === 'SAR'
              ? 'bg-amber-600/20 text-amber-300 border border-amber-500/40'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Déclarations de Soupçon (SAR)</span>
          <span className="px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold">
            {sarReports.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('AUDIT')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-2 ${
            activeTab === 'AUDIT'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <History className="w-4 h-4" />
          <span>Piste d'Audit Globale</span>
        </button>
      </div>

      {/* TAB 1 : RAPPORTS SAR */}
      {activeTab === 'SAR' && (
        <div className="space-y-4">
          {/* Recherche */}
          <div className="relative max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              value={sarSearch}
              onChange={(e) => setSarSearch(e.target.value)}
              placeholder="Rechercher par référence SAR ou verdict..."
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Tableau des rapports */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm overflow-hidden">
            {loadingSar ? (
              <TableSkeleton rows={4} cols={6} />
            ) : filteredSar.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Référence SAR</th>
                      <th className="py-3 px-4">Transaction ID</th>
                      <th className="py-3 px-4">Date de Génération</th>
                      <th className="py-3 px-4">Montant Signalé</th>
                      <th className="py-3 px-4">Cadre Réglementaire</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredSar.map((sar) => (
                      <tr key={sar.reference} className="hover:bg-slate-800/40 transition">
                        <td className="py-3 px-4 font-mono font-semibold text-amber-300">
                          {sar.reference}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300">
                          #{sar.transaction_id || 'N/A'}
                        </td>
                        <td className="py-3 px-4 text-slate-400 font-mono">
                          {sar.generated_at ? new Date(sar.generated_at).toLocaleString() : 'N/A'}
                        </td>
                        <td className="py-3 px-4 font-semibold text-white">
                          {sar.amount ? `${Number(sar.amount).toFixed(2)} €` : 'N/A'}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                            {sar.compliance_framework || 'ACPR / TRACFIN'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right space-x-2">
                          <button
                            onClick={() => handlePreviewSAR(sar.reference)}
                            className="px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 transition inline-flex items-center gap-1 font-medium"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>Aperçu</span>
                          </button>

                          <a
                            href={api.reports.getDownloadUrl(sar.reference, 'md')}
                            download
                            className="px-2.5 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/40 transition inline-flex items-center gap-1 font-medium"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>MD</span>
                          </a>

                          <a
                            href={api.reports.getDownloadUrl(sar.reference, 'json')}
                            download
                            className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 transition inline-flex items-center gap-1 font-medium"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>JSON</span>
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-12 text-center text-slate-500 text-xs">
                Aucun rapport SAR généré pour le moment.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2 : PISTE D'AUDIT GLOBALE */}
      {activeTab === 'AUDIT' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <select
              value={stageFilter}
              onChange={(e) => {
                setStageFilter(e.target.value);
                setAuditPage(1);
              }}
              className="px-3 py-2 rounded-xl border border-slate-700 bg-slate-950/70 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">Toutes les Étapes</option>
              <option value="ML_SCORING">ML_SCORING</option>
              <option value="INVESTIGATION">INVESTIGATION</option>
              <option value="DECISION">DECISION</option>
              <option value="ACTION_DISPATCHED">ACTION_DISPATCHED</option>
              <option value="ACTION_EXECUTED">ACTION_EXECUTED</option>
              <option value="SAR_GENERATED">SAR_GENERATED</option>
              <option value="ANALYST_REVIEW">ANALYST_REVIEW</option>
            </select>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm overflow-hidden">
            {loadingAudit ? (
              <TableSkeleton rows={8} cols={5} />
            ) : auditData && auditData.items.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Date / Heure</th>
                      <th className="py-3 px-4">Tx ID</th>
                      <th className="py-3 px-4">Étape</th>
                      <th className="py-3 px-4">Acteur</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4 text-right">Détails</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {auditData.items.map((log) => (
                      <tr key={log.id} className="hover:bg-slate-800/40 transition">
                        <td className="py-3 px-4 text-slate-400">
                          {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                        </td>
                        <td className="py-3 px-4 font-semibold text-white">
                          #{log.transaction_id}
                        </td>
                        <td className="py-3 px-4 text-indigo-300 font-semibold">
                          {log.stage}
                        </td>
                        <td className="py-3 px-4 text-slate-200">
                          {log.actor}
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          {log.action}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedAuditJson(log.details)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition"
                          >
                            Inspecter JSON
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-12 text-center text-slate-500 text-xs">
                Aucun événement d'audit ne correspond aux critères.
              </div>
            )}

            {/* Pagination Audit */}
            {auditData && auditData.total > 0 && (
              <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Total : {auditData.total} événements enregistrés</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setAuditPage((p) => Math.max(1, p - 1))}
                    disabled={auditPage <= 1}
                    className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-40 transition"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="font-semibold text-white">Page {auditPage} sur {auditData.pages}</span>
                  <button
                    onClick={() => setAuditPage((p) => Math.min(auditData.pages, p + 1))}
                    disabled={auditPage >= auditData.pages}
                    className="p-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-40 transition"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal d'Aperçu du Rapport SAR */}
      {previewContent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-3xl max-h-[85vh] flex flex-col p-6 rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-white">
                  Rapport Officiel : {previewContent.reference}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyMarkdown}
                  className="px-2.5 py-1 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs font-medium text-slate-300 flex items-center gap-1.5 transition"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copié !' : 'Copier'}</span>
                </button>
                <button
                  onClick={() => setPreviewContent(null)}
                  className="p-1 text-slate-400 hover:text-white rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto my-4 p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
              {previewContent.markdown || JSON.stringify(previewContent.json, null, 2)}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs text-slate-400">
              <span>Classification : CONFIDENTIAL / RESTRICTED</span>
              <button
                onClick={() => setPreviewContent(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-medium"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal JSON Inspector pour l'audit */}
      {selectedAuditJson && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-xl p-6 rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <History className="w-4 h-4 text-blue-400" />
                Détails JSON de l'Événement d'Audit
              </h3>
              <button onClick={() => setSelectedAuditJson(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 overflow-x-auto max-h-96 font-mono">
              {JSON.stringify(selectedAuditJson, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
