import { createContext, useContext, useState, type ReactNode } from "react";

import api from "../services/api";
import {
    clearTokens,
    getAccessToken,
    getRefreshToken,
    setTokens,
    type StoredTokens,
} from "../services/tokenStorage";

type AuthContextType = {
    token: string | null;
    isAuthenticated: boolean;
    login: (tokens: StoredTokens) => void;
    logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType>({
    token: null,
    isAuthenticated: false,
    login: () => {},
    logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
    const [token, setToken] = useState<string | null>(getAccessToken());

    const login = (tokens: StoredTokens) => {
        setTokens(tokens);
        setToken(tokens.access_token);
    };

    const logout = async () => {
        const refreshToken = getRefreshToken();
        if (refreshToken) {
            try {
                await api.post("/auth/logout", { refresh_token: refreshToken });
            } catch {
                // Best-effort: the local session is cleared regardless.
            }
        }
        clearTokens();
        setToken(null);
    };

    return (
        <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
