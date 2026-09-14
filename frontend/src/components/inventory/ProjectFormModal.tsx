import { useState, type FormEvent } from "react";

import Modal from "../ui/Modal";
import Button from "../ui/Button";
import Input, { Label } from "../ui/Input";
import { getErrorMessage } from "../../services/api";
import { createProject, updateProject } from "../../services/projects";
import { AMENITY_LABELS, CANONICAL_AMENITIES, PROPERTY_TYPES } from "../../types/inventory";
import type { Project, ProjectCreateInput, PropertyType } from "../../types/inventory";

interface ProjectFormModalProps {
    project?: Project;
    onClose: () => void;
    onSaved: (project: Project) => void;
}

export default function ProjectFormModal({ project, onClose, onSaved }: ProjectFormModalProps) {
    const [form, setForm] = useState({
        name: project?.name ?? "",
        developer_name: project?.developer_name ?? "",
        description: project?.description ?? "",
        project_type: project?.project_type ?? "apartment",
        address: project?.address ?? "",
        city: project?.city ?? "",
        state: project?.state ?? "",
        locality: project?.locality ?? "",
        postal_code: project?.postal_code ?? "",
        rera_number: project?.rera_number ?? "",
        possession_date: project?.possession_date?.slice(0, 10) ?? "",
    });
    const [amenities, setAmenities] = useState<string[]>(project?.amenities ?? []);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    function toggleAmenity(key: string) {
        setAmenities((current) => (current.includes(key) ? current.filter((a) => a !== key) : [...current, key]));
    }

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSaving(true);
        setError("");
        try {
            const payload: ProjectCreateInput = {
                ...form,
                developer_name: form.developer_name || null,
                description: form.description || null,
                address: form.address || null,
                city: form.city || null,
                state: form.state || null,
                locality: form.locality || null,
                postal_code: form.postal_code || null,
                rera_number: form.rera_number || null,
                possession_date: form.possession_date || null,
                amenities,
            };
            const saved = project ? await updateProject(project.id, payload) : await createProject(payload);
            onSaved(saved);
            onClose();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Modal title={project ? "Edit project" : "New project"} onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}

                <div>
                    <Label htmlFor="name">Project name</Label>
                    <Input id="name" required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="developer_name">Developer</Label>
                        <Input id="developer_name" value={form.developer_name} onChange={(e) => setForm((f) => ({ ...f, developer_name: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="project_type">Project type</Label>
                        <select
                            id="project_type"
                            value={form.project_type}
                            onChange={(e) => setForm((f) => ({ ...f, project_type: e.target.value as PropertyType }))}
                            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                        >
                            {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>
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
                    <Label htmlFor="address">Address</Label>
                    <Input id="address" value={form.address} onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
                </div>

                <div className="grid grid-cols-3 gap-4">
                    <div>
                        <Label htmlFor="locality">Locality</Label>
                        <Input id="locality" value={form.locality} onChange={(e) => setForm((f) => ({ ...f, locality: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="city">City</Label>
                        <Input id="city" value={form.city} onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="state">State</Label>
                        <Input id="state" value={form.state} onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))} />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="rera_number">RERA number</Label>
                        <Input id="rera_number" value={form.rera_number} onChange={(e) => setForm((f) => ({ ...f, rera_number: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="possession_date">Possession date</Label>
                        <Input id="possession_date" type="date" value={form.possession_date} onChange={(e) => setForm((f) => ({ ...f, possession_date: e.target.value }))} />
                    </div>
                </div>

                <div>
                    <Label>Amenities</Label>
                    <div className="flex flex-wrap gap-2">
                        {CANONICAL_AMENITIES.map((key) => (
                            <button
                                type="button"
                                key={key}
                                onClick={() => toggleAmenity(key)}
                                className={`text-xs font-medium rounded-lg px-3 py-1.5 border transition-colors ${
                                    amenities.includes(key)
                                        ? "bg-ink-950 text-white border-ink-950"
                                        : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                                }`}
                            >
                                {AMENITY_LABELS[key]}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button type="submit" loading={saving}>{project ? "Save changes" : "Create project"}</Button>
                </div>
            </form>
        </Modal>
    );
}
