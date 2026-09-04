import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./tokenStorage";

const baseURL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const api = axios.create({ baseURL });

api.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// A separate, un-intercepted client for the refresh call itself, so a
// failed refresh can never recursively trigger another refresh attempt.
const rawClient = axios.create({ baseURL });

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return null;

    if (!refreshInFlight) {
        refreshInFlight = rawClient
            .post("/auth/refresh", { refresh_token: refreshToken })
            .then((res) => {
                setTokens(res.data);
                return res.data.access_token as string;
            })
            .catch(() => {
                clearTokens();
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

api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const config = error.config as RetriableConfig | undefined;

        if (error.response?.status === 401 && config && !config._retried && getRefreshToken()) {
            config._retried = true;
            const newToken = await refreshAccessToken();
            if (newToken) {
                config.headers = config.headers ?? {};
                config.headers.Authorization = `Bearer ${newToken}`;
                return api(config);
            }
        }

        if (error.response?.status === 401) {
            clearTokens();
            if (typeof window !== "undefined" && window.location.pathname !== "/") {
                window.location.assign("/");
            }
        }

        return Promise.reject(error);
    }
);

/** A consistent, user-facing message for any API error - used by every page
 * so error states read the same way across the whole app. */
export function getErrorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === "string") return detail;
        if (!error.response) return "Can't reach the server. Check your connection and try again.";
        switch (error.response.status) {
            case 401:
                return "Your session has expired. Please log in again.";
            case 403:
                return "You don't have permission to do that.";
            case 404:
                return "That couldn't be found.";
            case 422:
                return "Some of the information provided isn't valid.";
            case 500:
                return "Something went wrong on our end. Please try again.";
            default:
                return `Request failed (${error.response.status}).`;
        }
    }
    return "Something went wrong. Please try again.";
}

export default api;
