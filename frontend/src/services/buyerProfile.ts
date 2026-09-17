import buyerApi from "./buyerApi";
import type { BuyerProfile, BuyerProfileUpdate } from "../types/buyerProfile";

export async function getBuyerProfile(): Promise<BuyerProfile> {
    const response = await buyerApi.get<BuyerProfile>("/buyer/profile");
    return response.data;
}

export async function updateBuyerProfile(payload: BuyerProfileUpdate): Promise<BuyerProfile> {
    const response = await buyerApi.patch<BuyerProfile>("/buyer/profile", payload);
    return response.data;
}
