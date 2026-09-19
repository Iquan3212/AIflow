// Mirrors backend/app/schemas.py's team schemas.

export type TeamRole = "owner" | "admin" | "member";
export type AssignableRole = "admin" | "member";
export type InviteStatus = "pending" | "accepted" | "revoked";

export interface TeamMember {
    id: string;
    email: string;
    role: TeamRole;
    created_at: string;
}

export interface TeamInvite {
    id: string;
    email: string;
    role: AssignableRole;
    status: InviteStatus;
    expires_at: string;
    created_at: string;
}
