import { createContext, useContext, useState, type ReactNode } from "react";

import buyerApi from "../services/buyerApi";
import {
    clearBuyerTokens,
    getBuyerAccessToken,
    getBuyerRefreshToken,
    setBuyerTokens,
    type StoredBuyerTokens,
} from "../services/buyerTokenStorage";

type BuyerAuthContextType = {
    token: string | null;
    isAuthenticated: boolean;
    login: (tokens: StoredBuyerTokens) => void;
    logout: () => Promise<void>;
};

const BuyerAuthContext = createContext<BuyerAuthContextType>({
    token: null,
    isAuthenticated: false,
    login: () => {},
    logout: async () => {},
});

export function BuyerAuthProvider({ children }: { children: ReactNode }) {
    const [token, setToken] = useState<string | null>(getBuyerAccessToken());

    const login = (tokens: StoredBuyerTokens) => {
        setBuyerTokens(tokens);
        setToken(tokens.access_token);
    };

    const logout = async () => {
        const refreshToken = getBuyerRefreshToken();
        if (refreshToken) {
            try {
                await buyerApi.post("/buyer/auth/logout", { refresh_token: refreshToken });
            } catch {
                // Best-effort: the local session is cleared regardless.
            }
        }
        clearBuyerTokens();
        setToken(null);
    };

    return (
        <BuyerAuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout }}>
            {children}
        </BuyerAuthContext.Provider>
    );
}

export const useBuyerAuth = () => useContext(BuyerAuthContext);
