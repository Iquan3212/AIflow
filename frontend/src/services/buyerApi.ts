// Buyer-side equivalent of api.ts - a genuinely separate axios instance
// (not a parameterized shared client) so agency-dashboard code and
// buyer-marketplace code can never accidentally cross-attach the wrong
// bearer token. Same baseURL, same refresh-on-401/redirect-on-failure
// shape, same getErrorMessage (already generic, reused as-is) - just
// pointed at the buyer token storage and buyer refresh endpoint.

import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { baseURL } from "./api";
import {
    clearBuyerTokens,
    getBuyerAccessToken,
    getBuyerRefreshToken,
    setBuyerTokens,
} from "./buyerTokenStorage";

const buyerApi = axios.create({ baseURL });

buyerApi.interceptors.request.use((config) => {
    const token = getBuyerAccessToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const rawClient = axios.create({ baseURL });

let refreshInFlight: Promise<string | null> | null = null;

async function refreshBuyerAccessToken(): Promise<string | null> {
    const refreshToken = getBuyerRefreshToken();
    if (!refreshToken) return null;

    if (!refreshInFlight) {
        refreshInFlight = rawClient
            .post("/buyer/auth/refresh", { refresh_token: refreshToken })
            .then((res) => {
                setBuyerTokens(res.data);
                return res.data.access_token as string;
            })
            .catch(() => {
                clearBuyerTokens();
                return null;
            })
            .finally(() => {
                refreshInFlight = null;
            });
    }
    return refreshInFlight;
}

interface RetriableConfig extends InternalAxiosRequestConfig {
    _retried?: boolean;
}

buyerApi.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const config = error.config as RetriableConfig | undefined;

        if (error.response?.status === 401 && config && !config._retried && getBuyerRefreshToken()) {
            config._retried = true;
            const newToken = await refreshBuyerAccessToken();
            if (newToken) {
                config.headers = config.headers ?? {};
                config.headers.Authorization = `Bearer ${newToken}`;
                return buyerApi(config);
            }
        }

        if (error.response?.status === 401) {
            clearBuyerTokens();
            if (typeof window !== "undefined" && window.location.pathname !== "/") {
                window.location.assign("/");
            }
        }

        return Promise.reject(error);
    }
);

export default buyerApi;
