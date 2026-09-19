// Single source of truth for auth persistence. Used by both the AuthContext
// (React state) and the axios interceptors (plain JS, outside React), so it
// can't live inside a context/hook.

const ACCESS_KEY = "aiflow.access_token";
const REFRESH_KEY = "aiflow.refresh_token";
const SLUG_KEY = "aiflow.agency_slug";
const ROLE_KEY = "aiflow.user_role";

export interface StoredTokens {
  access_token: string;
  refresh_token: string;
  agency_slug?: string;
  user_role?: string;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function getAgencySlug(): string | null {
  return localStorage.getItem(SLUG_KEY);
}

export function getUserRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

export function setTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  if (tokens.agency_slug) {
    localStorage.setItem(SLUG_KEY, tokens.agency_slug);
  }
  if (tokens.user_role) {
    localStorage.setItem(ROLE_KEY, tokens.user_role);
  }
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(SLUG_KEY);
  localStorage.removeItem(ROLE_KEY);
}
