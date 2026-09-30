import { 
  AuthResponse, 
  User, 
  DashboardStats, 
  PaginatedResponse, 
  TransactionSummary, 
  TransactionDetail, 
  AlertItem, 
  SARReportSummary, 
  AuditEvent 
} from '../types';

const BASE_URL = '/api/v1';

class ApiClient {
  private getToken(): string | null {
    return localStorage.getItem('fraud_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      localStorage.removeItem('fraud_token');
      localStorage.removeItem('fraud_user');
      window.dispatchEvent(new Event('auth:unauthorized'));
      throw new Error('Session expirée ou non autorisée');
    }

    if (!response.ok) {
      let errorDetail = 'Une erreur est survenue';
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = response.statusText;
      }
      throw new Error(errorDetail);
    }

    return response.json() as Promise<T>;
  }

  // --- Authentification ---
  auth = {
    login: async (username: string, password: string): Promise<AuthResponse> => {
      const res = await this.request<AuthResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem('fraud_token', res.access_token);
      localStorage.setItem('fraud_user', JSON.stringify(res.user));
      return res;
    },
    me: async (): Promise<User> => {
      return this.request<User>('/auth/me');
    },
    logout: () => {
      localStorage.removeItem('fraud_token');
      localStorage.removeItem('fraud_user');
    },
  };

  // --- Dashboard ---
  dashboard = {
    getStats: async (): Promise<DashboardStats> => {
      return this.request<DashboardStats>('/dashboard/stats');
    },
  };

  // --- Transactions ---
  transactions = {
    list: async (params: {
      page?: number;
      limit?: number;
      search?: string;
      client?: string;
      status?: string;
      verdict?: string;
      min_amount?: number;
      max_amount?: number;
      start_date?: string;
      end_date?: string;
      sort_by?: string;
      order?: string;
    } = {}): Promise<PaginatedResponse<TransactionSummary>> => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          query.append(key, String(val));
        }
      });
      return this.request<PaginatedResponse<TransactionSummary>>(`/transactions?${query.toString()}`);
    },
    get: async (id: number): Promise<TransactionDetail> => {
      return this.request<TransactionDetail>(`/transactions/${id}`);
    },
  };

  // --- Alertes ---
  alerts = {
    list: async (statusFilter = 'PENDING'): Promise<AlertItem[]> => {
      return this.request<AlertItem[]>(`/alerts?status_filter=${statusFilter}`);
    },
    patch: async (id: number, payload: {
      status: string;
      analyst_decision?: string;
      notes?: string;
    }): Promise<AlertItem> => {
      return this.request<AlertItem>(`/alerts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
  };

  // --- Rapports SAR & Piste d'Audit ---
  reports = {
    getAuditTrail: async (params: {
      transaction_id?: number;
      stage?: string;
      actor?: string;
      page?: number;
      limit?: number;
    } = {}): Promise<PaginatedResponse<AuditEvent>> => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          query.append(key, String(val));
        }
      });
      return this.request<PaginatedResponse<AuditEvent>>(`/audit-trail?${query.toString()}`);
    },
    listSAR: async (): Promise<SARReportSummary[]> => {
      return this.request<SARReportSummary[]>('/reports/sar');
    },
    getSARContent: async (reference: string): Promise<{ reference: string; json_data: any; markdown_content: string }> => {
      return this.request(`/reports/sar/${reference}`);
    },
    getDownloadUrl: (reference: string, format = 'md'): string => {
      const token = localStorage.getItem('fraud_token');
      return `/api/v1/reports/sar/${reference}/download?format=${format}&token=${token || ''}`;
    },
  };

  // --- Agent IA (Text-to-SQL) ---
  agent = {
    chat: async (message: string, sessionId?: string) => {
      return this.request<{
        session_id: string;
        response: string;
        sql_query: string;
        columns: string[];
        data: any[];
        row_count: number;
        execution_time_ms: number;
      }>('/agent/chat', {
        method: 'POST',
        body: JSON.stringify({ message, session_id: sessionId }),
      });
    },
    getHistory: async (sessionId: string) => {
      return this.request<any[]>(`/agent/history?session_id=${sessionId}`);
    },
  };
}

export const api = new ApiClient();
