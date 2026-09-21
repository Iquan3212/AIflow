import {
    createContext,
    useContext,
    useEffect,
    useState,
} from "react";

import type { ReactNode } from "react";
import type { AgencyNotification } from "../types/notification";

import {
    getUnreadNotificationCount,
    listNotifications,
    markAllNotificationsRead,
    markNotificationRead,
} from "../services/notifications";
import { useAuth } from "./AuthContext";

// No React Query/SWR exists in this codebase (every page uses plain
// useState + useEffect) - matching that, this is a lightweight interval
// poll, not a new data-fetching library. Only the unread COUNT is
// polled (a cheap COUNT(*) on the backend); the full recent-notification
// list is fetched on demand (e.g. when the bell popover opens) so idle
// tabs don't keep re-transferring rows nobody is looking at.
const POLL_INTERVAL_MS = 45_000;
const RECENT_LIMIT = 8;

type NotificationsContextType = {
    unreadCount: number;
    recentNotifications: AgencyNotification[] | null;
    recentLoading: boolean;
    recentError: string | null;
    refreshUnreadCount: () => Promise<void>;
    refreshRecent: () => Promise<void>;
    markRead: (id: string) => Promise<void>;
    markAllRead: () => Promise<void>;
};

const NotificationsContext = createContext<NotificationsContextType>({
    unreadCount: 0,
    recentNotifications: null,
    recentLoading: false,
    recentError: null,
    refreshUnreadCount: async () => {},
    refreshRecent: async () => {},
    markRead: async () => {},
    markAllRead: async () => {},
});

export function NotificationsProvider({ children }: { children: ReactNode }) {
    const { token } = useAuth();

    const [unreadCount, setUnreadCount] = useState(0);
    const [recentNotifications, setRecentNotifications] = useState<AgencyNotification[] | null>(null);
    const [recentLoading, setRecentLoading] = useState(false);
    const [recentError, setRecentError] = useState<string | null>(null);

    async function refreshUnreadCount() {
        if (!token) return;
        try {
            setUnreadCount(await getUnreadNotificationCount());
        } catch {
            // A failed background poll shouldn't clobber the last known
            // good count or throw inside an interval callback.
        }
    }

    async function refreshRecent() {
        if (!token) return;
        setRecentLoading(true);
        setRecentError(null);
        try {
            const [rows, count] = await Promise.all([
                listNotifications({ limit: RECENT_LIMIT }),
                getUnreadNotificationCount(),
            ]);
            setRecentNotifications(rows);
            setUnreadCount(count);
        } catch (err) {
            setRecentError(err instanceof Error ? err.message : "Couldn't load notifications.");
        } finally {
            setRecentLoading(false);
        }
    }

    async function markRead(id: string) {
        const target = recentNotifications?.find((n) => n.id === id);
        const wasUnread = !!target && target.read_at === null;

        // Optimistic - the bell/popover should feel instant; reconciled
        // by the real response (and by refreshUnreadCount on failure).
        setRecentNotifications((current) =>
            current?.map((n) => (n.id === id ? { ...n, read_at: n.read_at ?? new Date().toISOString() } : n)) ?? current
        );
        if (wasUnread) setUnreadCount((c) => Math.max(0, c - 1));

        try {
            await markNotificationRead(id);
        } catch {
            // Reconcile with the server rather than trust the optimistic guess.
            await refreshUnreadCount();
        }
    }

    async function markAllRead() {
        const previousNotifications = recentNotifications;
        const previousCount = unreadCount;

        setRecentNotifications((current) =>
            current?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? current
        );
        setUnreadCount(0);

        try {
            await markAllNotificationsRead();
        } catch (err) {
            setRecentNotifications(previousNotifications);
            setUnreadCount(previousCount);
            throw err;
        }
    }

    useEffect(() => {
        if (!token) {
            setUnreadCount(0);
            setRecentNotifications(null);
            return;
        }
        void refreshUnreadCount();
        const interval = setInterval(() => {
            void refreshUnreadCount();
        }, POLL_INTERVAL_MS);
        return () => clearInterval(interval);
        // refreshUnreadCount is a plain (non-useCallback) function that closes
        // over token, so it's intentionally omitted here — including it would
        // recreate the function reference (and the poll interval) every render.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    return (
        <NotificationsContext.Provider
            value={{
                unreadCount,
                recentNotifications,
                recentLoading,
                recentError,
                refreshUnreadCount,
                refreshRecent,
                markRead,
                markAllRead,
            }}
        >
            {children}
        </NotificationsContext.Provider>
    );
}

export function useNotifications() {
    return useContext(NotificationsContext);
}
