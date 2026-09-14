import { useState, type FormEvent } from "react";
import { CheckCircle2 } from "lucide-react";

import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Input, { Label } from "../ui/Input";
import { requestSiteVisit } from "../../services/marketplace";
import { getErrorMessage } from "../../services/api";

/** Real booking through the existing AppointmentService (Step 10 of the
 * Phase 8 spec) - a rejected slot (outside business hours, conflict,
 * etc.) shows the agency's own honest reason, never a fake success. */
export default function SiteVisitModal({
    propertyId,
    defaultName,
    defaultEmail,
    onClose,
}: {
    propertyId: string;
    defaultName?: string;
    defaultEmail?: string;
    onClose: () => void;
}) {
    const [form, setForm] = useState({
        name: defaultName ?? "", phone: "", email: defaultEmail ?? "",
        preferred_date: "", preferred_time: "11:00",
    });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSubmitting(true);
        setError("");
        try {
            const res = await requestSiteVisit(propertyId, form);
            setResult(res);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSubmitting(false);
        }
    }

    if (result) {
        return (
            <Modal title="Site visit request" onClose={onClose}>
                <div className="text-center py-4">
                    {result.ok ? (
                        <CheckCircle2 size={36} className="text-emerald-500 mx-auto mb-3" />
                    ) : null}
                    <p className={`text-sm ${result.ok ? "text-ink-950" : "text-amber-700"}`}>{result.message}</p>
                    <Button className="mt-5" onClick={onClose}>Close</Button>
                </div>
            </Modal>
        );
    }

    return (
        <Modal title="Request a site visit" onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}
                <div>
                    <Label htmlFor="sv-name">Name</Label>
                    <Input id="sv-name" required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="sv-phone">Phone</Label>
                        <Input id="sv-phone" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="sv-email">Email</Label>
                        <Input id="sv-email" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="sv-date">Preferred date</Label>
                        <Input id="sv-date" type="date" required value={form.preferred_date} onChange={(e) => setForm((f) => ({ ...f, preferred_date: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="sv-time">Preferred time</Label>
                        <Input id="sv-time" type="time" required value={form.preferred_time} onChange={(e) => setForm((f) => ({ ...f, preferred_time: e.target.value }))} />
                    </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button type="submit" loading={submitting}>Request visit</Button>
                </div>
            </form>
        </Modal>
    );
}
