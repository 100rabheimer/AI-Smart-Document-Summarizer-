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
