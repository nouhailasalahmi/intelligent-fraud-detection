import React from 'react';
import { useAlerts } from '../../context/AlertsContext';
import { ShieldAlert, AlertTriangle, Info, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useAlerts();
  const navigate = useNavigate();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-3 max-w-md w-full pointer-events-none">
      {toasts.map((toast) => {
        const isCritical = toast.severity === 'critical';
        const isWarning = toast.severity === 'warning';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-2xl backdrop-blur-md border transition-all transform animate-in slide-in-from-bottom-5 duration-300 ${
              isCritical
                ? 'bg-red-950/90 border-red-700/80 text-red-100 shadow-red-950/50'
                : isWarning
                ? 'bg-amber-950/90 border-amber-700/80 text-amber-100 shadow-amber-950/50'
                : 'bg-slate-900/90 border-slate-700 text-slate-100 shadow-slate-950/50'
            }`}
          >
            <div className="mt-0.5 flex-shrink-0">
              {isCritical ? (
                <ShieldAlert className="w-5 h-5 text-red-400 animate-bounce" />
              ) : isWarning ? (
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              ) : (
                <Info className="w-5 h-5 text-blue-400" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold truncate">{toast.title}</h4>
                <span className="text-[10px] text-slate-400">{toast.timestamp}</span>
              </div>
              <p className="text-xs mt-1 text-slate-300 leading-relaxed">{toast.message}</p>
              
              <div className="mt-2.5 flex items-center gap-3">
                <button
                  onClick={() => {
                    dismissToast(toast.id);
                    navigate('/alerts');
                  }}
                  className="text-xs font-semibold px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 transition text-white"
                >
                  Examiner la file
                </button>
              </div>
            </div>

            <button
              onClick={() => dismissToast(toast.id)}
              className="text-slate-400 hover:text-white p-1 rounded-md transition"
              aria-label="Fermer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
