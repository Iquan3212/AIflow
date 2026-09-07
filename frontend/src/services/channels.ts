import api from "./api";

export type ChannelName = "whatsapp" | "instagram";

export interface ChannelCredential {
    channel: ChannelName;
    display_name: string | null;
    status: "connected" | "disconnected" | "error";
    connected_at: string | null;
}

export interface ChannelConnectPayload {
    external_account_id: string;
    access_token: string;
    display_name?: string;
}

export async function getChannels(): Promise<ChannelCredential[]> {
    const res = await api.get<ChannelCredential[]>("/channels/");
    return res.data;
}

export async function connectChannel(
    channel: ChannelName,
    payload: ChannelConnectPayload
): Promise<ChannelCredential> {
    const res = await api.put<ChannelCredential>(`/channels/${channel}`, payload);
    return res.data;
}

export async function disconnectChannel(channel: ChannelName): Promise<ChannelCredential> {
    const res = await api.delete<ChannelCredential>(`/channels/${channel}`);
    return res.data;
}
