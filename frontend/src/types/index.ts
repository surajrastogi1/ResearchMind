export interface User {
  id: number;
  email: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Project {
  id: number;
  title: string;
  description?: string;
  created_at: string;
  user_id: number;
}