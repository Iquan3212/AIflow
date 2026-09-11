// Buyer-side equivalent of tokenStorage.ts - deliberately separate
// localStorage keys (not shared with the agency dashboard's
// aiflow.access_token/aiflow.refresh_token) so the same browser can hold
// an agency session and a buyer session at once without either clobbering
// the other.

const ACCESS_KEY = "aiflow.buyer_access_token";
const REFRESH_KEY = "aiflow.buyer_refresh_token";

export interface StoredBuyerTokens {
  access_token: string;
  refresh_token: string;
}

export function getBuyerAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getBuyerRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setBuyerTokens(tokens: StoredBuyerTokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearBuyerTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
