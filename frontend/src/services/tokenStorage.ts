// Single source of truth for auth persistence. Used by both the AuthContext
// (React state) and the axios interceptors (plain JS, outside React), so it
// can't live inside a context/hook.

const ACCESS_KEY = "aiflow.access_token";
const REFRESH_KEY = "aiflow.refresh_token";
const SLUG_KEY = "aiflow.business_slug";

export interface StoredTokens {
  access_token: string;
  refresh_token: string;
  business_slug?: string;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function getBusinessSlug(): string | null {
  return localStorage.getItem(SLUG_KEY);
}

export function setTokens(tokens: StoredTokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  if (tokens.business_slug) {
    localStorage.setItem(SLUG_KEY, tokens.business_slug);
  }
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(SLUG_KEY);
}
