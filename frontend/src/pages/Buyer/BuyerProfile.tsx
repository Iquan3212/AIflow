import { useEffect, useState, type FormEvent } from "react";
import { Bell, CheckCircle2, MonitorSmartphone, Sliders, User } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Input, { Label } from "../../components/ui/Input";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getBuyerProfile, updateBuyerProfile } from "../../services/buyerProfile";
import { listBuyerSessions, revokeBuyerSession, type BuyerSession } from "../../services/buyerAuth";
import { FURNISHINGS, PROPERTY_TYPES } from "../../types/marketplace";
import type { BuyerProfile as BuyerProfileType } from "../../types/buyerProfile";

const TABS = [
    { id: "personal", label: "Personal info", icon: User },
    { id: "preferences", label: "Preferences", icon: Sliders },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "security", label: "Security", icon: MonitorSmartphone },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function BuyerProfile() {
    const [tab, setTab] = useState<TabId>("personal");
    const [profile, setProfile] = useState<BuyerProfileType | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setProfile(await getBuyerProfile());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    return (
        <BuyerLayout>
            <div className="mb-7">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Your account</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Profile</h1>
            </div>

            {error && <ErrorState message={error} onRetry={load} />}
            {!error && !profile && <LoadingState label="Loading profile…" />}

            {!error && profile && (
                <div className="grid grid-cols-1 lg:grid-cols-[13rem_1fr] gap-8">
                    <nav aria-label="Profile sections" className="flex lg:flex-col gap-1 overflow-x-auto">
                        {TABS.map(({ id, label, icon: Icon }) => (
                            <button
                                key={id}
                                onClick={() => setTab(id)}
                                aria-current={tab === id ? "page" : undefined}
                                className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-sm font-medium text-left whitespace-nowrap transition-colors ${
                                    tab === id ? "bg-ink-950 text-white" : "text-slate-600 hover:bg-stone-100"
                                }`}
                            >
                                <Icon size={15} aria-hidden="true" /> {label}
                            </button>
                        ))}
                    </nav>

                    <div className="min-w-0">
                        {tab === "personal" && <PersonalInfoTab profile={profile} onSaved={setProfile} />}
                        {tab === "preferences" && <PreferencesTab profile={profile} onSaved={setProfile} />}
                        {tab === "notifications" && <NotificationsTab profile={profile} onSaved={setProfile} />}
                        {tab === "security" && <SecurityTab />}
                    </div>
                </div>
            )}
        </BuyerLayout>
    );
}

function SaveBar({ saving, saved }: { saving: boolean; saved: boolean }) {
    return (
        <div className="flex items-center gap-3 mt-5">
            <Button type="submit" loading={saving}>Save changes</Button>
            {saved && (
                <span className="inline-flex items-center gap-1.5 text-sm text-emerald-700">
                    <CheckCircle2 size={15} aria-hidden="true" /> Saved
                </span>
            )}
        </div>
    );
}

function PersonalInfoTab({ profile, onSaved }: { profile: BuyerProfileType; onSaved: (p: BuyerProfileType) => void }) {
    const [name, setName] = useState(profile.name ?? "");
    const [phone, setPhone] = useState(profile.phone ?? "");
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSaving(true);
        setSaved(false);
        setError("");
        try {
            const updated = await updateBuyerProfile({ name: name || null, phone: phone || null });
            onSaved(updated);
            setSaved(true);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Card className="p-6 max-w-lg">
            <h2 className="text-sm font-semibold text-ink-950 mb-4">Personal information</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
                <div>
                    <Label htmlFor="p-name">Full name</Label>
                    <Input id="p-name" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div>
                    <Label htmlFor="p-email">Email</Label>
                    <Input id="p-email" value={profile.email} disabled />
                    <p className="text-xs text-slate-400 mt-1.5">Your email is your sign-in identity and can't be changed here.</p>
                </div>
                <div>
                    <Label htmlFor="p-phone">Phone</Label>
                    <Input id="p-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Optional" />
                </div>
                <SaveBar saving={saving} saved={saved} />
            </form>
        </Card>
    );
}

function PreferencesTab({ profile, onSaved }: { profile: BuyerProfileType; onSaved: (p: BuyerProfileType) => void }) {
    const [city, setCity] = useState(profile.preferred_city ?? "");
    const [locality, setLocality] = useState(profile.preferred_locality ?? "");
    const [bhk, setBhk] = useState(profile.preferred_bhk?.toString() ?? "");
    const [minBudget, setMinBudget] = useState(profile.budget_min ?? "");
    const [maxBudget, setMaxBudget] = useState(profile.budget_max ?? "");
    const [propertyType, setPropertyType] = useState(profile.preferred_property_type ?? "");
    const [furnishing, setFurnishing] = useState(profile.preferred_furnishing ?? "");
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSaving(true);
        setSaved(false);
        setError("");
        try {
            const updated = await updateBuyerProfile({
                preferred_city: city || null,
                preferred_locality: locality || null,
                preferred_bhk: bhk ? Number(bhk) : null,
                budget_min: minBudget || null,
                budget_max: maxBudget || null,
                preferred_property_type: (propertyType || null) as BuyerProfileType["preferred_property_type"],
                preferred_furnishing: (furnishing || null) as BuyerProfileType["preferred_furnishing"],
            });
            onSaved(updated);
            setSaved(true);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Card className="p-6 max-w-lg">
            <h2 className="text-sm font-semibold text-ink-950 mb-1.5">Search preferences</h2>
            <p className="text-xs text-slate-400 mb-4">
                Tell us what you're looking for - this powers better matches as recommendations roll out.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <Label htmlFor="pr-city">Preferred city</Label>
                        <Input id="pr-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Bengaluru" />
                    </div>
                    <div>
                        <Label htmlFor="pr-locality">Preferred locality</Label>
                        <Input id="pr-locality" value={locality} onChange={(e) => setLocality(e.target.value)} placeholder="Whitefield" />
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <Label htmlFor="pr-bhk">BHK</Label>
                        <select
                            id="pr-bhk"
                            value={bhk}
                            onChange={(e) => setBhk(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            <option value="">Any</option>
                            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} BHK</option>)}
                        </select>
                    </div>
                    <div>
                        <Label htmlFor="pr-type">Property type</Label>
                        <select
                            id="pr-type"
                            value={propertyType}
                            onChange={(e) => setPropertyType(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            <option value="">Any</option>
                            {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>
                </div>
                <div>
                    <Label htmlFor="pr-min">Budget (₹)</Label>
                    <div className="grid grid-cols-2 gap-3">
                        <Input id="pr-min" type="number" placeholder="Min" value={minBudget} onChange={(e) => setMinBudget(e.target.value)} />
                        <Input type="number" placeholder="Max" value={maxBudget} onChange={(e) => setMaxBudget(e.target.value)} />
                    </div>
                </div>
                <div>
                    <Label htmlFor="pr-furnishing">Furnishing</Label>
                    <select
                        id="pr-furnishing"
                        value={furnishing}
                        onChange={(e) => setFurnishing(e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    >
                        <option value="">Any</option>
                        {FURNISHINGS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                </div>
                <SaveBar saving={saving} saved={saved} />
            </form>
        </Card>
    );
}

function NotificationsTab({ profile, onSaved }: { profile: BuyerProfileType; onSaved: (p: BuyerProfileType) => void }) {
    const [saving, setSaving] = useState<string | null>(null);
    const [error, setError] = useState("");

    const TOGGLES = [
        { key: "notify_site_visit_updates" as const, label: "Site visit updates", description: "When a site visit is confirmed, rescheduled, or cancelled." },
        { key: "notify_inquiry_updates" as const, label: "Inquiry updates", description: "When an agency responds to something you inquired about." },
        { key: "notify_booking_updates" as const, label: "Booking updates", description: "When your booking status changes." },
        { key: "notify_property_alerts" as const, label: "Property alerts", description: "Important updates about properties you've saved." },
    ];

    async function handleToggle(key: (typeof TOGGLES)[number]["key"], value: boolean) {
        setSaving(key);
        setError("");
        try {
            const updated = await updateBuyerProfile({ [key]: value });
            onSaved(updated);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(null);
        }
    }

    return (
        <Card className="p-6 max-w-lg">
            <h2 className="text-sm font-semibold text-ink-950 mb-4">Notifications</h2>
            {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm mb-4">{error}</div>}
            <ul className="divide-y divide-slate-100">
                {TOGGLES.map(({ key, label, description }) => (
                    <li key={key} className="py-4 flex items-center justify-between gap-4">
                        <div className="min-w-0">
                            <p className="text-sm font-medium text-ink-950">{label}</p>
                            <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                        </div>
                        <button
                            type="button"
                            role="switch"
                            aria-checked={profile[key]}
                            aria-label={label}
                            disabled={saving === key}
                            onClick={() => handleToggle(key, !profile[key])}
                            className={`shrink-0 w-11 h-6 rounded-full relative transition-colors disabled:opacity-50 ${
                                profile[key] ? "bg-brand-600" : "bg-slate-200"
                            }`}
                        >
                            <span
                                className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-soft transition-transform ${
                                    profile[key] ? "translate-x-5" : "translate-x-0"
                                }`}
                            />
                        </button>
                    </li>
                ))}
            </ul>
        </Card>
    );
}

function SecurityTab() {
    const [sessions, setSessions] = useState<BuyerSession[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setSessions(await listBuyerSessions());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleRevoke(id: string) {
        try {
            await revokeBuyerSession(id);
            setSessions((current) => current?.filter((s) => s.id !== id) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    return (
        <Card className="p-6 max-w-lg">
            <h2 className="text-sm font-semibold text-ink-950 mb-4">Signed-in devices</h2>
            {error && <ErrorState message={error} onRetry={load} />}
            {!error && !sessions && <LoadingState label="Loading sessions…" />}
            {!error && sessions && sessions.length === 0 && (
                <EmptyState title="No other sessions" description="This device is the only one signed in." />
            )}
            {!error && sessions && sessions.length > 0 && (
                <ul className="divide-y divide-slate-100">
                    {sessions.map((s) => (
                        <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-sm font-medium text-slate-800 truncate">{s.device_name ?? "Unknown device"}</p>
                                <p className="text-xs text-slate-400">Last used {new Date(s.last_used_at).toLocaleString()}</p>
                            </div>
                            <Button variant="ghost" size="sm" onClick={() => handleRevoke(s.id)}>Sign out</Button>
                        </li>
                    ))}
                </ul>
            )}
        </Card>
    );
}
