import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCheck, Inbox } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listNotifications } from "../../services/notifications";
import { useNotifications } from "../../context/NotificationsContext";
import type { AgencyNotification } from "../../types/notification";
import { NOTIFICATION_TYPE_META, formatRelativeTime, notificationDestination } from "../../utils/notificationDisplay";

const PAGE_SIZE = 20;

function NotificationListItem({ notification, onOpen }: { notification: AgencyNotification; onOpen: (n: AgencyNotification) => void }) {
    const meta = NOTIFICATION_TYPE_META[notification.type];
    const Icon = meta?.icon ?? Inbox;
    const unread = notification.read_at === null;

    return (
        <button
            type="button"
            onClick={() => onOpen(notification)}
            className={`w-full flex items-start gap-3.5 text-left px-4 py-4 sm:px-5 transition-colors border-b border-slate-100 last:border-b-0 ${
                unread ? "bg-brand-50/50 hover:bg-brand-50" : "bg-white hover:bg-slate-50"
            }`}
        >
            <span className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${meta?.accent ?? "text-slate-500 bg-slate-100"}`}>
                <Icon size={17} aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                    {unread && <span className="w-2 h-2 rounded-full bg-brand-600 shrink-0" aria-hidden="true" />}
                    <span className={`block text-sm ${unread ? "font-semibold text-ink-950" : "font-medium text-slate-700"}`}>
                        {notification.title}
                    </span>
                </span>
                <span className="block text-sm text-slate-500 mt-0.5 leading-snug">{notification.message}</span>
                <span className="block text-xs text-slate-400 mt-1.5">{formatRelativeTime(notification.created_at)}</span>
            </span>
        </button>
    );
}

export default function Notifications() {
    const navigate = useNavigate();
    const { unreadCount, markRead, markAllRead } = useNotifications();

    const [filter, setFilter] = useState<"all" | "unread">("all");
    const [items, setItems] = useState<AgencyNotification[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [markingAll, setMarkingAll] = useState(false);

    async function load(reset = true) {
        setError(null);
        if (reset) setItems(null);
        try {
            const rows = await listNotifications({ unreadOnly: filter === "unread", limit: PAGE_SIZE, offset: 0 });
            setItems(rows);
            setHasMore(rows.length === PAGE_SIZE);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filter]);

    async function handleLoadMore() {
        if (!items) return;
        setLoadingMore(true);
        try {
            const rows = await listNotifications({ unreadOnly: filter === "unread", limit: PAGE_SIZE, offset: items.length });
            setItems((current) => (current ? [...current, ...rows] : rows));
            setHasMore(rows.length === PAGE_SIZE);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setLoadingMore(false);
        }
    }

    async function handleOpen(notification: AgencyNotification) {
        if (notification.read_at === null) {
            void markRead(notification.id);
            setItems((current) =>
                current?.map((n) => (n.id === notification.id ? { ...n, read_at: new Date().toISOString() } : n)) ?? current
            );
        }
        const destination = notificationDestination(notification);
        if (destination) navigate(destination);
    }

    async function handleMarkAllRead() {
        setMarkingAll(true);
        try {
            await markAllRead();
            setItems((current) => current?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setMarkingAll(false);
        }
    }

    return (
        <AppShell>
            <PageHeader
                eyebrow="Activity"
                title="Notifications"
                description="New leads, callback requests, and other real-time activity for your agency."
            />

            <div className="max-w-2xl mx-auto">
                <div className="flex items-center justify-between mb-4">
                    <div className="inline-flex items-center bg-white border border-slate-200 rounded-xl p-1">
                        {(["all", "unread"] as const).map((tab) => (
                            <button
                                key={tab}
                                onClick={() => setFilter(tab)}
                                className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors capitalize ${
                                    filter === tab ? "bg-ink-950 text-white" : "text-slate-600"
                                }`}
                            >
                                {tab}
                                {tab === "unread" && unreadCount > 0 && ` (${unreadCount})`}
                            </button>
                        ))}
                    </div>
                    {unreadCount > 0 && (
                        <Button variant="secondary" size="sm" loading={markingAll} onClick={handleMarkAllRead}>
                            <CheckCheck size={14} className="mr-1.5" aria-hidden="true" />
                            Mark all as read
                        </Button>
                    )}
                </div>

                <Card className="p-0 overflow-hidden">
                    {error && <ErrorState message={error} onRetry={() => load(true)} />}

                    {!error && items === null && (
                        <div className="divide-y divide-slate-100">
                            {[0, 1, 2, 3].map((i) => (
                                <div key={i} className="flex items-start gap-3.5 px-5 py-4">
                                    <div className="w-10 h-10 rounded-xl bg-slate-100 animate-pulse shrink-0" />
                                    <div className="flex-1 space-y-2 py-1">
                                        <div className="h-3.5 w-1/3 rounded bg-slate-100 animate-pulse" />
                                        <div className="h-3 w-2/3 rounded bg-slate-100 animate-pulse" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {!error && items && items.length === 0 && (
                        <EmptyState
                            icon={<Inbox size={22} />}
                            title="No notifications yet"
                            description="New leads, callback requests, and important activity will appear here."
                        />
                    )}

                    {!error && items && items.length > 0 && (
                        <>
                            <div>
                                {items.map((n) => (
                                    <NotificationListItem key={n.id} notification={n} onOpen={handleOpen} />
                                ))}
                            </div>
                            {hasMore && (
                                <div className="p-3 text-center border-t border-slate-100">
                                    <Button variant="secondary" size="sm" loading={loadingMore} onClick={handleLoadMore}>
                                        Load more
                                    </Button>
                                </div>
                            )}
                        </>
                    )}
                </Card>
            </div>
        </AppShell>
    );
}
