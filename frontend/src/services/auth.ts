import api from "./api";

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    agency_name: string;
    industry: string;
    owner_email: string;
    password: string;
}

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    agency_id: string;
    agency_slug: string;
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>("/auth/login", payload);
    return response.data;
}

export async function register(payload: RegisterRequest): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>("/auth/signup", payload);
    return response.data;
}
