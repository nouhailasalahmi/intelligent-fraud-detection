import React from 'react';
import { ShieldAlert, ShieldCheck, HelpCircle, BellRing, CheckCircle, Clock, XCircle } from 'lucide-react';

interface StatusBadgeProps {
  type: 'action' | 'decision' | 'review' | 'dsp2';
  value: string | boolean | undefined;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ type, value, size = 'sm' }) => {
  const strVal = String(value || '').toUpperCase();

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 font-medium',
    md: 'text-sm px-2.5 py-1 font-medium',
    lg: 'text-base px-3 py-1.5 font-semibold',
  }[size];

  // Actions automatisées
  if (type === 'action') {
    switch (strVal) {
      case 'BLOCK_CARD':
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-red-950/70 text-red-400 border border-red-800/60 ${sizeClasses}`}>
            <ShieldAlert className="w-3.5 h-3.5" />
            BLOCK_CARD
          </span>
        );
      case 'NOTIFY_CUSTOMER':
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-amber-950/70 text-amber-400 border border-amber-800/60 ${sizeClasses}`}>
            <BellRing className="w-3.5 h-3.5" />
            NOTIFY_CUSTOMER
          </span>
        );
      case 'FLAG_FOR_REVIEW':
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-indigo-950/70 text-indigo-300 border border-indigo-700/60 ${sizeClasses}`}>
            <Clock className="w-3.5 h-3.5" />
            FLAG_FOR_REVIEW
          </span>
        );
      case 'ALLOW':
      default:
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-emerald-950/70 text-emerald-400 border border-emerald-800/60 ${sizeClasses}`}>
            <CheckCircle className="w-3.5 h-3.5" />
            ALLOW
          </span>
        );
    }
  }

  // Décisions du Multi-Agent
  if (type === 'decision') {
    switch (strVal) {
      case 'FRAUDE':
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-rose-950/70 text-rose-300 border border-rose-800/60 ${sizeClasses}`}>
            <ShieldAlert className="w-3.5 h-3.5" />
            Fraude
          </span>
        );
      case 'LEGITIME':
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 ${sizeClasses}`}>
            <ShieldCheck className="w-3.5 h-3.5" />
            Légitime
          </span>
        );
      case 'INCERTAIN':
      default:
        return (
          <span className={`inline-flex items-center gap-1 rounded-full bg-amber-950/70 text-amber-300 border border-amber-800/60 ${sizeClasses}`}>
            <HelpCircle className="w-3.5 h-3.5" />
            Incertain
          </span>
        );
    }
  }

  // Statut DSP2
  if (type === 'dsp2') {
    const isCompliant = value === true || strVal === 'TRUE' || strVal === 'CONFORME';
    return isCompliant ? (
      <span className={`inline-flex items-center gap-1 rounded-full bg-emerald-950/70 text-emerald-400 border border-emerald-800/60 ${sizeClasses}`}>
        <CheckCircle className="w-3.5 h-3.5" />
        DSP2 Conforme
      </span>
    ) : (
      <span className={`inline-flex items-center gap-1 rounded-full bg-rose-950/70 text-rose-400 border border-rose-800/60 ${sizeClasses}`}>
        <XCircle className="w-3.5 h-3.5" />
        DSP2 Non-Conforme
      </span>
    );
  }

  // Statut de révision Analyste
  switch (strVal) {
    case 'PENDING':
      return (
        <span className={`inline-flex items-center gap-1 rounded-full bg-amber-950/70 text-amber-300 border border-amber-800/60 ${sizeClasses}`}>
          <Clock className="w-3.5 h-3.5 animate-pulse" />
          En attente
        </span>
      );
    case 'BLOCKED':
      return (
        <span className={`inline-flex items-center gap-1 rounded-full bg-red-950/70 text-red-300 border border-red-800/60 ${sizeClasses}`}>
          <ShieldAlert className="w-3.5 h-3.5" />
          Carte bloquée
        </span>
      );
    case 'FALSE_POSITIVE':
    case 'ALLOWED':
      return (
        <span className={`inline-flex items-center gap-1 rounded-full bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 ${sizeClasses}`}>
          <CheckCircle className="w-3.5 h-3.5" />
          Faux positif validé
        </span>
      );
    case 'RESOLVED':
    default:
      return (
        <span className={`inline-flex items-center gap-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 ${sizeClasses}`}>
          <CheckCircle className="w-3.5 h-3.5" />
          Traitée
        </span>
      );
  }
};
