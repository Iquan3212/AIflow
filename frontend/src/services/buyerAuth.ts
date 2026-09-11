import buyerApi from "./buyerApi";

export interface BuyerLoginRequest {
    email: string;
    password: string;
}

export interface BuyerSignupRequest {
    name?: string;
    email: string;
    password: string;
    phone?: string;
}

export interface BuyerTokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
    buyer_id: string;
}

export async function buyerLogin(payload: BuyerLoginRequest): Promise<BuyerTokenResponse> {
    const response = await buyerApi.post<BuyerTokenResponse>("/buyer/auth/login", payload);
    return response.data;
}

export async function buyerSignup(payload: BuyerSignupRequest): Promise<BuyerTokenResponse> {
    const response = await buyerApi.post<BuyerTokenResponse>("/buyer/auth/signup", payload);
    return response.data;
}
