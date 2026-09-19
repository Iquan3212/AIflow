import api from "./api";
import type { TeamInvite, TeamMember, AssignableRole } from "../types/team";
import type { TokenResponse } from "./auth";

export async function listMembers(): Promise<TeamMember[]> {
    const response = await api.get<TeamMember[]>("/team/members");
    return response.data;
}

export async function listInvites(): Promise<TeamInvite[]> {
    const response = await api.get<TeamInvite[]>("/team/invites");
    return response.data;
}

export async function inviteMember(email: string, role: AssignableRole): Promise<TeamInvite> {
    const response = await api.post<TeamInvite>("/team/invites", { email, role });
    return response.data;
}

export async function revokeInvite(inviteId: string): Promise<void> {
    await api.delete(`/team/invites/${inviteId}`);
}

export async function updateMemberRole(userId: string, role: AssignableRole): Promise<TeamMember> {
    const response = await api.patch<TeamMember>(`/team/members/${userId}/role`, { role });
    return response.data;
}

export async function removeMember(userId: string): Promise<void> {
    await api.delete(`/team/members/${userId}`);
}

/** Public - the invitee has no account/token yet. Uses the raw axios
 * instance's baseURL but not its bearer-token interceptor (harmless
 * either way, since the backend endpoint requires no auth). */
export async function acceptInvite(token: string, password: string): Promise<TokenResponse> {
    const response = await api.post<TokenResponse>("/team/invites/accept", { token, password });
    return response.data;
}
