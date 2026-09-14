import { useState, type FormEvent } from "react";

import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Input, { Label } from "../ui/Input";
import { getErrorMessage } from "../../services/api";
import { createProperty, updateProperty } from "../../services/properties";
import { FACINGS, FURNISHINGS, PROPERTY_TYPES } from "../../types/inventory";
import type { Property, PropertyCreateInput, PropertyType } from "../../types/inventory";

interface PropertyFormModalProps {
    projectId: string;
    property?: Property;
    onClose: () => void;
    onSaved: (property: Property) => void;
}

function toNumberOrNull(value: string): number | null {
    if (value.trim() === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

export default function PropertyFormModal({ projectId, property, onClose, onSaved }: PropertyFormModalProps) {
    const [form, setForm] = useState({
        building: property?.building ?? "",
        floor: property?.floor?.toString() ?? "",
        unit_number: property?.unit_number ?? "",
        property_type: property?.property_type ?? "apartment",
        bhk: property?.bhk?.toString() ?? "",
        carpet_area_sqft: property?.carpet_area_sqft ?? "",
        facing: property?.facing ?? "",
        furnishing: property?.furnishing ?? "",
        price: property?.price ?? "",
        maintenance_amount: property?.maintenance_amount ?? "",
        description: property?.description ?? "",
        rera_number: property?.rera_number ?? "",
        internal_notes: property?.internal_notes ?? "",
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSaving(true);
        setError("");
        try {
            const payload: PropertyCreateInput = {
                project_id: projectId,
                building: form.building || null,
                floor: toNumberOrNull(form.floor),
                unit_number: form.unit_number || null,
                property_type: form.property_type as PropertyCreateInput["property_type"],
                bhk: toNumberOrNull(form.bhk),
                carpet_area_sqft: toNumberOrNull(form.carpet_area_sqft),
                facing: (form.facing || null) as PropertyCreateInput["facing"],
                furnishing: (form.furnishing || null) as PropertyCreateInput["furnishing"],
                price: toNumberOrNull(form.price),
                maintenance_amount: toNumberOrNull(form.maintenance_amount),
                description: form.description || null,
                rera_number: form.rera_number || null,
                internal_notes: form.internal_notes || null,
            };
            const saved = property
                ? await updateProperty(property.id, payload)
                : await createProperty(payload);
            onSaved(saved);
            onClose();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Modal title={property ? "Edit unit" : "New unit"} onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}

                <div className="grid grid-cols-3 gap-4">
                    <div>
                        <Label htmlFor="building">Tower / Block</Label>
                        <Input id="building" value={form.building} onChange={(e) => setForm((f) => ({ ...f, building: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="floor">Floor</Label>
                        <Input id="floor" type="number" value={form.floor} onChange={(e) => setForm((f) => ({ ...f, floor: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="unit_number">Unit number</Label>
                        <Input id="unit_number" value={form.unit_number} onChange={(e) => setForm((f) => ({ ...f, unit_number: e.target.value }))} />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="property_type">Property type</Label>
                        <select
                            id="property_type"
                            value={form.property_type}
                            onChange={(e) => setForm((f) => ({ ...f, property_type: e.target.value as PropertyType }))}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>
                    <div>
                        <Label htmlFor="bhk">BHK</Label>
                        <Input id="bhk" type="number" min={0} value={form.bhk} onChange={(e) => setForm((f) => ({ ...f, bhk: e.target.value }))} />
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                    <div>
                        <Label htmlFor="carpet_area_sqft">Carpet area (sq.ft)</Label>
                        <Input id="carpet_area_sqft" type="number" step="0.01" value={form.carpet_area_sqft ?? ""} onChange={(e) => setForm((f) => ({ ...f, carpet_area_sqft: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="facing">Facing</Label>
                        <select
                            id="facing"
                            value={form.facing ?? ""}
                            onChange={(e) => setForm((f) => ({ ...f, facing: e.target.value }))}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            <option value="">—</option>
                            {FACINGS.map((f) => <option key={f} value={f}>{f}</option>)}
                        </select>
                    </div>
                    <div>
                        <Label htmlFor="furnishing">Furnishing</Label>
                        <select
                            id="furnishing"
                            value={form.furnishing ?? ""}
                            onChange={(e) => setForm((f) => ({ ...f, furnishing: e.target.value }))}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            <option value="">—</option>
                            {FURNISHINGS.map((f) => <option key={f} value={f}>{f}</option>)}
                        </select>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="price">Price (₹)</Label>
                        <Input id="price" type="number" step="0.01" value={form.price ?? ""} onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="maintenance_amount">Monthly maintenance (₹)</Label>
                        <Input id="maintenance_amount" type="number" step="0.01" value={form.maintenance_amount ?? ""} onChange={(e) => setForm((f) => ({ ...f, maintenance_amount: e.target.value }))} />
                    </div>
                </div>

                <div>
                    <Label htmlFor="rera_number">Unit RERA number (if unit-specific)</Label>
                    <Input id="rera_number" value={form.rera_number} onChange={(e) => setForm((f) => ({ ...f, rera_number: e.target.value }))} />
                </div>

                <div>
                    <Label htmlFor="description">Description</Label>
                    <textarea
                        id="description"
                        rows={2}
                        value={form.description}
                        onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    />
                </div>

                <div>
                    <Label htmlFor="internal_notes">Internal notes (never shown to buyers)</Label>
                    <textarea
                        id="internal_notes"
                        rows={2}
                        value={form.internal_notes}
                        onChange={(e) => setForm((f) => ({ ...f, internal_notes: e.target.value }))}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button type="submit" loading={saving}>{property ? "Save changes" : "Create unit"}</Button>
                </div>
            </form>
        </Modal>
    );
}
