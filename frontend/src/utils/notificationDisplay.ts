import { UserPlus, PhoneCall } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { AgencyNotification, NotificationType } from "../types/notification";

/** Single source of truth for how a notification TYPE renders (icon,
 * accent color) - every surface (bell popover, full /notifications page)
 * reads from here instead of re-implementing per-type styling. Only the
 * types the backend actually creates (app/models.py's NotificationType)
 * are listed - never a fabricated type. */
export const NOTIFICATION_TYPE_META: Record<NotificationType, { icon: LucideIcon; accent: string }> = {
    new_lead: { icon: UserPlus, accent: "text-brand-600 bg-brand-50" },
    callback_requested: { icon: PhoneCall, accent: "text-flare-600 bg-flare-50" },
};

/** Where clicking this notification should navigate - both real
 * notification types today are lead-anchored (a callback request is
 * shown on its lead's own card), so both resolve to the same existing
 * /leads route with a highlight target. No per-lead detail route exists
 * in this app, so this deliberately never links deeper than that. Null
 * means "no known destination" - the caller should still mark it read,
 * just never navigate. */
export function notificationDestination(notification: AgencyNotification): string | null {
    if (notification.lead_id) {
        return `/leads?id=${notification.lead_id}`;
    }
    return null;
}

export function formatRelativeTime(iso: string): string {
    const date = new Date(iso);
    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 10) return "just now";
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
