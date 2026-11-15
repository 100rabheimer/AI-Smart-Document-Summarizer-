export interface DependencyStatus {
  database: boolean;
  redis: boolean;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  environment: string;
  dependencies: DependencyStatus;
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  is_active: boolean;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string | null;
  created_at: string;
}

export interface DocumentSummary {
  overview: string;
  key_topics: string[];
  critical_insights: string[];
  target_audience: string;
}

export interface Citation {
  document_filename: string;
  page_number: number;
  chunk_index: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[] | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}
