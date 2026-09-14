import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bookmark, Compass, MonitorSmartphone } from "lucide-react";

import BuyerShell from "../../components/layout/BuyerShell";
import PropertyCard from "../../components/marketplace/PropertyCard";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listBuyerSessions, revokeBuyerSession, type BuyerSession } from "../../services/buyerAuth";
import { listSavedProperties, removeSavedProperty } from "../../services/marketplace";
import type { MarketplaceProperty } from "../../types/marketplace";

export default function BuyerHome() {
    const navigate = useNavigate();
    const [sessions, setSessions] = useState<BuyerSession[] | null>(null);
    const [saved, setSaved] = useState<MarketplaceProperty[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            const [sess, savedProps] = await Promise.all([listBuyerSessions(), listSavedProperties()]);
            setSessions(sess);
            setSaved(savedProps);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    async function handleRevoke(id: string) {
        try {
            await revokeBuyerSession(id);
            setSessions((current) => current?.filter((s) => s.id !== id) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleUnsave(propertyId: string) {
        const previous = saved;
        setSaved((current) => current?.filter((p) => p.id !== propertyId) ?? current);
        try {
            await removeSavedProperty(propertyId);
        } catch (err) {
            setSaved(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    return (
        <BuyerShell>
            <div className="mb-9">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Buyer account</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Welcome back</h1>
                <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
                    Your saved properties and account settings, all in one place.
                </p>
            </div>

            <div className="mb-9">
                <div className="flex items-center gap-2 mb-4">
                    <Bookmark size={16} className="text-slate-400" aria-hidden="true" />
                    <h2 className="text-sm font-semibold text-slate-700">Saved properties</h2>
                </div>

                {!saved && !error && <LoadingState label="Loading saved properties…" />}
                {error && <ErrorState message={error} onRetry={load} />}
                {saved && !error && saved.length === 0 && (
                    <EmptyState
                        icon={<Compass size={26} />}
                        title="No saved properties yet"
                        description="Browse the marketplace and tap the bookmark icon on a listing to save it here."
                        action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                    />
                )}
                {saved && !error && saved.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                        {saved.map((property) => (
                            <PropertyCard
                                key={property.id}
                                property={property}
                                saved
                                onToggleSave={() => handleUnsave(property.id)}
                                onClick={() => navigate(`/discover/properties/${property.id}`)}
                            />
                        ))}
                    </div>
                )}
            </div>

            <Card className="p-7">
                <div className="flex items-center gap-2 mb-4">
                    <MonitorSmartphone size={16} className="text-slate-400" aria-hidden="true" />
                    <h2 className="text-sm font-semibold text-slate-700">Signed-in devices</h2>
                </div>

                {!sessions && !error && <LoadingState label="Loading sessions…" />}
                {sessions && !error && sessions.length === 0 && (
                    <EmptyState title="No other sessions" description="This device is the only one signed in." />
                )}
                {sessions && !error && sessions.length > 0 && (
                    <ul className="divide-y divide-slate-100">
                        {sessions.map((s) => (
                            <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="text-sm font-medium text-slate-800 truncate">
                                        {s.device_name ?? "Unknown device"}
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        Last used {new Date(s.last_used_at).toLocaleString()}
                                    </p>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => handleRevoke(s.id)}>
                                    Sign out
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
            </Card>
        </BuyerShell>
    );
}
