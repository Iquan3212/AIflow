import api from "./api";

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    business_name: string;
    industry: string;
    owner_email: string;
    password: string;
}

export async function login(payload: LoginRequest) {

    const response = await api.post(
        "/auth/login",
        payload
    );

    return response.data;
}

export async function register(
    payload: RegisterRequest
) {

    const response = await api.post(
        "/auth/signup",
        payload
    );

    return response.data;
}