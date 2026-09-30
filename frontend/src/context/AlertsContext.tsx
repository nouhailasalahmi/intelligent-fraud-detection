import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { AlertItem } from '../types';
import { api } from '../api/client';
import { useAuth } from './AuthContext';

export interface ToastNotification {
  id: string;
  title: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  timestamp: string;
  alertData?: any;
}

interface AlertsContextType {
  alerts: AlertItem[];
  pendingCount: number;
  isConnected: boolean;
  toasts: ToastNotification[];
  refreshAlerts: () => Promise<void>;
  dismissToast: (id: string) => void;
  resolveAlert: (id: number, payload: { status: string; analyst_decision?: string; notes?: string }) => Promise<void>;
}

const AlertsContext = createContext<AlertsContextType | undefined>(undefined);

export const AlertsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [toasts, setToasts] = useState<ToastNotification[]>([]);

  const refreshAlerts = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const data = await api.alerts.list('PENDING');
      setAlerts(data);
    } catch (e) {
      console.error('Erreur chargement alertes:', e);
    }
  }, [isAuthenticated]);

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const resolveAlert = async (id: number, payload: { status: string; analyst_decision?: string; notes?: string }) => {
    const updated = await api.alerts.patch(id, payload);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    return updated as any;
  };

  // Connexion WebSocket temps réel
  useEffect(() => {
    if (!isAuthenticated) {
      setIsConnected(false);
      return;
    }

    refreshAlerts();

    let socket: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const token = localStorage.getItem('fraud_token') || '';
      
      // En dev, pointer sur le proxy Vite (/ws/alerts)
      const wsUrl = `${protocol}//${host}/ws/alerts?token=${encodeURIComponent(token)}`;

      try {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
          setIsConnected(true);
          console.log('[WS] Connecté au flux temps réel des alertes de fraude.');
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'NEW_ALERT' && data.alert) {
              const newAlert = data.alert;
              
              // Mettre à jour la file des alertes
              setAlerts((prev) => {
                if (prev.some((a) => a.id === newAlert.transaction_id)) return prev;
                return [
                  {
                    id: newAlert.transaction_id,
                    transaction_uuid: newAlert.transaction_uuid,
                    customer_id: newAlert.customer_id_anonymized || newAlert.customer_id,
                    card_id: newAlert.card_masked || newAlert.card_id,
                    amount: newAlert.amount,
                    city: newAlert.city,
                    country: newAlert.country,
                    action_taken: newAlert.action,
                    review_status: 'PENDING',
                    llm_decision: newAlert.decision,
                    llm_confidence: newAlert.confidence,
                    llm_justification: newAlert.reason,
                    created_at: newAlert.timestamp,
                  } as AlertItem,
                  ...prev,
                ];
              });

              // Émettre un Toast d'alerte immédiat
              const toastId = `toast-${Date.now()}`;
              const newToast: ToastNotification = {
                id: toastId,
                title: '🚨 Nouvelle alerte fraude détectée',
                message: `Transaction de ${Number(newAlert.amount).toFixed(2)} DH (${newAlert.city || 'Inconnu'}) mise en attente d'arbitrage.`,
                severity: newAlert.confidence && newAlert.confidence > 0.8 ? 'critical' : 'warning',
                timestamp: new Date().toLocaleTimeString(),
                alertData: newAlert,
              };

              setToasts((prev) => [newToast, ...prev.slice(0, 4)]);

              // Fermeture automatique du toast après 8 secondes
              setTimeout(() => {
                dismissToast(toastId);
              }, 8000);
            }
          } catch (err) {
            console.error('[WS] Erreur parsing message:', err);
          }
        };

        socket.onclose = () => {
          setIsConnected(false);
          // Reconnexion automatique après 4s
          reconnectTimeout = setTimeout(connectWebSocket, 4000);
        };

        socket.onerror = () => {
          setIsConnected(false);
          if (socket) socket.close();
        };
      } catch (err) {
        console.error('[WS] Erreur ouverture socket:', err);
        reconnectTimeout = setTimeout(connectWebSocket, 4000);
      }
    };

    connectWebSocket();

    return () => {
      if (socket) socket.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [isAuthenticated, refreshAlerts]);

  const pendingCount = alerts.filter((a) => a.review_status === 'PENDING' || !a.review_status).length;

  return (
    <AlertsContext.Provider
      value={{
        alerts,
        pendingCount,
        isConnected,
        toasts,
        refreshAlerts,
        dismissToast,
        resolveAlert,
      }}
    >
      {children}
    </AlertsContext.Provider>
  );
};

export const useAlerts = () => {
  const context = useContext(AlertsContext);
  if (!context) {
    throw new Error('useAlerts must be used within an AlertsProvider');
  }
  return context;
};