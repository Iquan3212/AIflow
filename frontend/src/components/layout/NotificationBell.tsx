import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck, Inbox } from "lucide-react";

import { useNotifications } from "../../context/NotificationsContext";
import type { AgencyNotification } from "../../types/notification";
import { NOTIFICATION_TYPE_META, formatRelativeTime, notificationDestination } from "../../utils/notificationDisplay";

function NotificationRow({ notification, onOpen }: { notification: AgencyNotification; onOpen: (n: AgencyNotification) => void }) {
    const meta = NOTIFICATION_TYPE_META[notification.type];
    const Icon = meta?.icon ?? Inbox;
    const unread = notification.read_at === null;

    return (
        <button
            type="button"
            role="menuitem"
            onClick={() => onOpen(notification)}
            className={`w-full flex items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                unread ? "bg-brand-50/70 hover:bg-brand-50" : "hover:bg-slate-50"
            }`}
        >
            <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${meta?.accent ?? "text-slate-500 bg-slate-100"}`}>
                <Icon size={15} aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                    {unread && <span className="w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0" aria-hidden="true" />}
                    <span className={`block text-sm truncate ${unread ? "font-semibold text-ink-950" : "font-medium text-slate-700"}`}>
                        {notification.title}
                    </span>
                </span>
                <span className="block text-xs text-slate-500 mt-0.5 leading-snug line-clamp-2">{notification.message}</span>
                <span className="block text-[11px] text-slate-400 mt-1">{formatRelativeTime(notification.created_at)}</span>
            </span>
        </button>
    );
}

/** Mirrors TopNav.tsx's GroupMenu/AccountMenu dropdown pattern exactly
 * (click-outside + Escape to close, role="menu", the same dark glassy
 * panel styling) - no new popover primitive was introduced. */
export default function NotificationBell() {
    const { unreadCount, recentNotifications, recentLoading, recentError, refreshRecent, markRead, markAllRead } = useNotifications();
    const [open, setOpen] = useState(false);
    const [markingAll, setMarkingAll] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    useEffect(() => {
        function onDocClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        }
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("mousedown", onDocClick);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDocClick);
            document.removeEventListener("keydown", onKey);
        };
    }, []);

    function toggle() {
        setOpen((v) => {
            const next = !v;
            // Opening the dropdown never marks anything read (user
            // control) - it only (re)fetches the latest rows to show.
            if (next) void refreshRecent();
            return next;
        });
    }

    async function handleOpenNotification(notification: AgencyNotification) {
        if (notification.read_at === null) {
            void markRead(notification.id);
        }
        setOpen(false);
        const destination = notificationDestination(notification);
        if (destination) navigate(destination);
    }

    async function handleMarkAllRead() {
        setMarkingAll(true);
        try {
            await markAllRead();
        } catch {
            // markAllRead already reverts its own optimistic update on failure.
        } finally {
            setMarkingAll(false);
        }
    }

    return (
        <div className="relative" ref={ref}>
            <button
                type="button"
                onClick={toggle}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
                className="relative flex items-center justify-center w-9 h-9 rounded-lg text-white/80 hover:text-white hover:bg-white/[0.08] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flare-400"
            >
                <Bell size={19} aria-hidden="true" />
                {unreadCount > 0 && (
                    <span
                        className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-flare-500 text-ink-950 text-[10px] font-bold flex items-center justify-center leading-none"
                        aria-hidden="true"
                    >
                        {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                )}
            </button>

            {open && (
                <div
                    role="menu"
                    aria-label="Notifications"
                    className="absolute right-0 top-full mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-2xl border border-white/10 bg-ink-900/95 backdrop-blur-xl shadow-lifted origin-top-right animate-[menuOpen_0.16s_ease-out] flex flex-col"
                >
                    <div className="flex items-center justify-between px-4 pt-3.5 pb-2">
                        <p className="text-sm font-semibold text-white">Notifications</p>
                        {!!recentNotifications?.length && unreadCount > 0 && (
                            <button
                                type="button"
                                onClick={handleMarkAllRead}
                                disabled={markingAll}
                                className="flex items-center gap-1 text-xs font-medium text-white/60 hover:text-white disabled:opacity-50 transition-colors"
                            >
                                <CheckCheck size={13} aria-hidden="true" />
                                Mark all as read
                            </button>
                        )}
                    </div>

                    <div className="px-2 pb-2 max-h-[22rem] overflow-y-auto thin-scrollbar">
                        {recentLoading && !recentNotifications && (
                            <div className="space-y-1.5 px-1 py-1">
                                {[0, 1, 2].map((i) => (
                                    <div key={i} className="h-14 rounded-xl bg-white/[0.05] animate-pulse" />
                                ))}
                            </div>
                        )}

                        {recentError && !recentLoading && (
                            <div className="px-3 py-6 text-center">
                                <p className="text-xs text-white/60 mb-2">Couldn't load notifications.</p>
                                <button type="button" onClick={() => void refreshRecent()} className="text-xs font-medium text-flare-400 hover:text-flare-300">
                                    Retry
                                </button>
                            </div>
                        )}

                        {!recentLoading && !recentError && recentNotifications?.length === 0 && (
                            <div className="px-3 py-8 text-center">
                                <Inbox size={22} className="mx-auto text-white/25 mb-2" aria-hidden="true" />
                                <p className="text-xs font-medium text-white/70">No notifications yet</p>
                                <p className="text-[11px] text-white/40 mt-1">New leads and callback requests will appear here.</p>
                            </div>
                        )}

                        {!recentError && recentNotifications && recentNotifications.length > 0 && (
                            <div className="space-y-0.5">
                                {recentNotifications.map((n) => (
                                    <NotificationRow key={n.id} notification={n} onOpen={handleOpenNotification} />
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="border-t border-white/10 px-4 py-2.5">
                        <button
                            type="button"
                            onClick={() => {
                                setOpen(false);
                                navigate("/notifications");
                            }}
                            className="text-xs font-medium text-white/70 hover:text-white transition-colors"
                        >
                            View all notifications →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
