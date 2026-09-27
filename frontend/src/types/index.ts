export type UserRole = 'admin' | 'analyst';

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type ActionType = 'BLOCK_CARD' | 'NOTIFY_CUSTOMER' | 'FLAG_FOR_REVIEW' | 'ALLOW';
export type DecisionType = 'fraude' | 'legitime' | 'incertain';
export type ReviewStatus = 'PENDING' | 'RESOLVED' | 'BLOCKED' | 'ALLOWED' | 'FALSE_POSITIVE';

export interface TransactionSummary {
  id: number;
  transaction_uuid: string;
  customer_id: string; // Pseudonymisé RGPD
  card_id: string;     // Masqué PCI-DSS
  amount: number;
  city?: string;
  country?: string;
  payment_method?: string;
  device_type?: string;
  transaction_timestamp: string;
  fraud_probability?: number;
  iso_anomaly_score?: number;
  is_fraud_alert?: boolean;
  dsp2_compliant?: boolean;
  dsp2_reason?: string;
  llm_decision?: DecisionType;
  llm_confidence?: number;
  llm_justification?: string;
  action_taken?: ActionType;
  review_status?: ReviewStatus;
  sar_generated?: boolean;
  sar_path?: string;
  created_at?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface AuditEvent {
  id: number;
  transaction_id: number;
  stage: string;
  actor: string;
  action: string;
  details?: Record<string, any>;
  created_at: string;
}

export interface ActionLogEntry {
  id: number;
  action: string;
  status: string;
  details?: Record<string, any>;
  executed_at: string;
}

export interface InvestigatorTrace {
  summary?: string;
  anomalies: string[];
  risk_factors: string[];
  mitigating_factors: string[];
  contextual_ratio?: number;
  steps_used: number;
}

export interface DecisionTrace {
  verdict?: string;
  confidence?: number;
  risk_level?: string;
  justification?: string;
  recommended_action?: string;
  steps_used?: number;
}

export interface TransactionDetail {
  transaction: TransactionSummary;
  scoring_ml: {
    fraud_probability: number;
    iso_anomaly_score: number;
    is_fraud_alert: boolean;
    model_supervised: string;
    model_unsupervised: string;
  };
  dsp2: {
    is_compliant: boolean;
    reason: string;
  };
  investigator_trace: InvestigatorTrace;
  decision_trace: DecisionTrace;
  multi_pass_triggered: boolean;
  action_log: ActionLogEntry[];
  audit_trail: AuditEvent[];
  sar_info?: {
    generated: boolean;
    path: string;
    reference: string;
  };
}

export interface AlertItem {
  id: number;
  transaction_uuid?: string;
  customer_id: string;
  card_id: string;
  amount: number;
  city?: string;
  country?: string;
  payment_method?: string;
  device_type?: string;
  transaction_timestamp?: string;
  fraud_probability?: number;
  iso_anomaly_score?: number;
  dsp2_compliant?: boolean;
  dsp2_reason?: string;
  llm_decision?: string;
  llm_confidence?: number;
  llm_justification?: string;
  action_taken: string;
  review_status: string;
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at?: string;
}

export interface DashboardStats {
  total_transactions: number;
  total_amount: number;
  fraud_count: number;
  fraud_rate_pct: number;
  pending_alerts_count: number;
  dsp2_compliance_rate_pct: number;
  avg_llm_confidence: number;
  action_breakdown: Record<string, number>;
  decision_breakdown: Record<string, number>;
  timeline: {
    date: string;
    total_transactions: number;
    fraud_count: number;
    volume: number;
    blocked_count: number;
  }[];
  recent_suspicious: any[];
}

export interface SARReportSummary {
  reference: string;
  transaction_id?: number;
  generated_at?: string;
  classification?: string;
  json_path?: string;
  md_path?: string;
  amount?: number;
  decision?: string;
  compliance_framework?: string;
}

export interface ChatMessage {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  sql_query?: string;
  columns?: string[];
  data?: any[];
  row_count?: number;
  execution_time_ms?: number;
  created_at?: string;
}
